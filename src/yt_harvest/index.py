"""The video index: classification rules and the JSONL form on disk.

Every video a channel listing yields becomes exactly one record carrying its
inclusion and therefore the reason it will or will not be fetched: exclusions
are recorded, never implied. Given the same input the file is byte-identical:
records sort by upload date then video id, JSON keys sort.

One index file per channel: `<data_root>/index/<slug>.jsonl`. Index files
carry titles, so they stay in the data root and never enter git.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from yt_harvest.config import Channel, Config
from yt_harvest.ytdlp import list_channel_entries

_LIVE_STATUSES = frozenset({"is_live", "was_live", "post_live"})
_UPCOMING_STATUSES = frozenset({"is_upcoming"})
_MEMBERS_AVAILABILITY = frozenset({"subscriber_only", "premium_only", "needs_auth"})

PENDING = "pending"
EXCLUDED_SHORT = "excluded_short"
EXCLUDED_OUT_OF_RANGE = "excluded_out_of_range"
EXCLUDED_MEMBERS_ONLY = "excluded_members_only"
EXCLUDED_UPCOMING = "excluded_upcoming"


@dataclass(frozen=True)
class Video:
    channel: str  # channel slug
    video_id: str
    title: str
    upload_date: date  # date.min when the listing gave none
    duration_seconds: int
    view_count: int  # -1 when the listing gave none
    was_live: bool
    inclusion: str


def classify(entry: dict[str, object], channel: str, config: Config) -> Video:
    """Turn one raw listing entry into a classified `Video`. Pure.

    Order of rules: upcoming, members-only, Short, out of range, else pending.
    Livestream replays are kept. A missing duration reads as 0 and therefore as
    a Short, which is how the flat listing returns Shorts; a long video that
    lost its duration would land there too, so `status` reports the count of
    dated zero-duration videos.
    """
    duration = _number(entry.get("duration"), 0)
    upload_date = _upload_date(entry.get("upload_date")) or _timestamp_date(entry.get("timestamp"))
    if entry.get("live_status") in _UPCOMING_STATUSES:
        inclusion = EXCLUDED_UPCOMING
    elif entry.get("availability") in _MEMBERS_AVAILABILITY:
        inclusion = EXCLUDED_MEMBERS_ONLY
    elif duration <= config.shorts_max_seconds:
        inclusion = EXCLUDED_SHORT
    elif config.start_date is not None and (upload_date is None or upload_date < config.start_date):
        inclusion = EXCLUDED_OUT_OF_RANGE
    else:
        inclusion = PENDING
    return Video(
        channel=channel,
        video_id=str(entry.get("id", "")),
        title=str(entry.get("title", "")),
        upload_date=upload_date if upload_date is not None else date.min,
        duration_seconds=duration,
        view_count=_number(entry.get("view_count"), -1),
        was_live=bool(entry.get("was_live")) or entry.get("live_status") in _LIVE_STATUSES,
        inclusion=inclusion,
    )


def enumerate_channel(channel: Channel, config: Config) -> list[Video]:
    """Classify every upload on the channel, one record per video id.

    A video listed in two tabs (e.g. a livestream that is also in Videos)
    keeps its first record.
    """
    seen: dict[str, Video] = {}
    for entry in list_channel_entries(channel.url):
        video = classify(entry, channel.slug, config)
        if video.video_id and video.video_id not in seen:
            seen[video.video_id] = video
    return list(seen.values())


def index_path(channel_slug: str, config: Config) -> Path:
    return config.data_root / "index" / f"{channel_slug}.jsonl"


def write_index(videos: Iterable[Video], path: Path) -> int:
    """Write one JSON record per line, sorted; return how many were written."""
    ordered = sorted(videos, key=lambda video: (video.upload_date, video.video_id))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for video in ordered:
            record = asdict(video)
            record["upload_date"] = video.upload_date.isoformat()
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
    tmp.replace(path)
    return len(ordered)


def read_index(path: Path) -> Iterator[Video]:
    """Yield the records of one index file, equal to what went in."""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            yield Video(
                channel=record["channel"],
                video_id=record["video_id"],
                title=record["title"],
                upload_date=date.fromisoformat(record["upload_date"]),
                duration_seconds=record["duration_seconds"],
                view_count=record["view_count"],
                was_live=record["was_live"],
                inclusion=record["inclusion"],
            )


def read_all(config: Config) -> list[Video]:
    """Every video of every configured channel that has an index file."""
    videos: list[Video] = []
    for channel in config.channels:
        path = index_path(channel.slug, config)
        if path.exists():
            videos.extend(read_index(path))
    return videos


def _number(value: object, missing: int) -> int:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return int(value)
    return missing


def _upload_date(value: object) -> date | None:
    """Parse yt-dlp's `YYYYMMDD`; anything unparseable is None."""
    if not isinstance(value, str) or len(value) != 8 or not value.isdigit():
        return None
    try:
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def _timestamp_date(value: object) -> date | None:
    """Epoch seconds as a UTC date."""
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(value, tz=UTC).date()
    except (OverflowError, OSError, ValueError):
        return None
