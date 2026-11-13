"""Narrowing the corpus: topic selection, per-channel picks, and fetch order.

Topic selection (`select_video`, `select_all`): a topic keyword in the TITLE or
the DESCRIPTION is an automatic include; otherwise a video is included when its
transcript mentions at least `mention_threshold` DISTINCT keywords (three
different topics in one video is a discussion; one word said ten times is not).
Every pending video gets a record with its reason, excluded ones included.

Picks (`picks`): per channel, the `pick_top` most-viewed and `pick_recent` most
recent pending videos, each with the reason it was picked. The fetch runs those
first (`fetch_order`), so agents can start reading before the whole back
catalogue is in.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from yt_harvest.config import Config
from yt_harvest.index import PENDING, Video
from yt_harvest.transcripts import Transcript, load_cached

TITLE_HIT = "title_hit"
DESCRIPTION_HIT = "description_hit"
THRESHOLD = "threshold"
EXCLUDED = "excluded_below_threshold"
NO_KEYWORDS = "excluded_no_keywords_configured"

MOST_VIEWED = "most_viewed"
MOST_RECENT = "most_recent"


@dataclass(frozen=True)
class Selection:
    video: Video
    reason: str
    keywords_found: tuple[str, ...]  # distinct keywords in the transcript, sorted
    has_transcript: bool


def compile_matcher(keywords: Sequence[str]) -> re.Pattern[str] | None:
    """One case-insensitive whole-word pattern for every keyword; None if none."""
    words = sorted({word.strip().lower() for word in keywords if word.strip()}, key=len)
    if not words:
        return None
    alternatives = "|".join(re.escape(word) for word in reversed(words))
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)


def select_video(
    video: Video,
    transcript: Transcript | None,
    matcher: re.Pattern[str] | None,
    threshold: int,
) -> Selection:
    """Decide one video's fate. Pure."""
    has_transcript = transcript is not None
    if matcher is None:
        return Selection(video, NO_KEYWORDS, (), has_transcript)
    body = " ".join(cue.text for cue in transcript.cues) if transcript else ""
    found = tuple(sorted({match.group(0).lower() for match in matcher.finditer(body)}))
    description = transcript.description if transcript else ""
    if matcher.search(video.title):
        reason = TITLE_HIT
    elif matcher.search(description):
        reason = DESCRIPTION_HIT
    elif len(found) >= threshold:
        reason = THRESHOLD
    else:
        reason = EXCLUDED
    return Selection(video, reason, found, has_transcript)


def select_all(videos: Iterable[Video], config: Config) -> list[Selection]:
    """Select over every pending video, one transcript in memory at a time."""
    matcher = compile_matcher(config.topic_keywords)
    return [
        select_video(video, load_cached(video.video_id, config), matcher, config.mention_threshold)
        for video in videos
        if video.inclusion == PENDING
    ]


def write_selected(selections: Iterable[Selection], path: Path) -> int:
    """One JSON record per line, in the given order, deterministic."""
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for s in selections:
            record = {
                "channel": s.video.channel,
                "video_id": s.video.video_id,
                "reason": s.reason,
                "keywords_found": list(s.keywords_found),
                "has_transcript": s.has_transcript,
            }
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
            written += 1
    return written


@dataclass(frozen=True)
class Pick:
    video: Video
    reasons: tuple[str, ...]  # MOST_VIEWED and/or MOST_RECENT


def _newest_first(video: Video) -> tuple[int, str]:
    return (-video.upload_date.toordinal(), video.video_id)


def picks(videos: Iterable[Video], config: Config) -> list[Pick]:
    """Per channel (config order), the most-viewed then the most-recent pending videos.

    A video in both lists appears once with both reasons. Videos without a
    view count never count as most-viewed.
    """
    by_channel: dict[str, list[Video]] = {}
    for video in videos:
        if video.inclusion == PENDING:
            by_channel.setdefault(video.channel, []).append(video)
    order = [c.slug for c in config.channels] + sorted(
        set(by_channel) - {c.slug for c in config.channels}
    )
    result: list[Pick] = []
    for slug in order:
        pool = by_channel.get(slug, [])
        viewed = sorted(
            (v for v in pool if v.view_count >= 0), key=lambda v: (-v.view_count, v.video_id)
        )[: config.pick_top]
        recent = sorted(pool, key=_newest_first)[: config.pick_recent]
        reasons: dict[str, list[str]] = {}
        chosen: dict[str, Video] = {}
        for label, group in ((MOST_VIEWED, viewed), (MOST_RECENT, recent)):
            for video in group:
                chosen.setdefault(video.video_id, video)
                reasons.setdefault(video.video_id, []).append(label)
        result.extend(Pick(chosen[vid], tuple(reasons[vid])) for vid in chosen)
    return result


def fetch_order(videos: Sequence[Video], config: Config) -> list[Video]:
    """Pending videos in the order to fetch them.

    First the picks, round-robin across channels so every channel gets some
    early; then everything else, newest first.
    """
    chosen = picks(videos, config)
    queues: dict[str, list[Video]] = {}
    for pick in chosen:
        queues.setdefault(pick.video.channel, []).append(pick.video)
    first: list[Video] = []
    while any(queues.values()):
        for queue in queues.values():
            if queue:
                first.append(queue.pop(0))
    picked = {video.video_id for video in first}
    rest = sorted(
        (v for v in videos if v.inclusion == PENDING and v.video_id not in picked),
        key=_newest_first,
    )
    return first + rest
