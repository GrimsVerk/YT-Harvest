"""Every lever, declared once.

Two files feed it. `config.toml` (committed) holds the channel list and the
levers. `local.toml` (gitignored; copy `local.toml.example`) holds what is
machine-specific: today only `data_root`, where the index, transcripts, ledger,
log and PID file live. Transcripts are copyrighted and never enter git, which is
why the data root defaults to a folder outside the repo.

A missing key falls back to its default; a missing file reads as empty.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

DEFAULT_DATA_ROOT = "~/data/yt-harvest"


@dataclass(frozen=True)
class Channel:
    """One channel to harvest. `slug` names its index file and tags its videos."""

    slug: str
    name: str
    url: str


@dataclass(frozen=True)
class Config:
    data_root: Path
    channels: tuple[Channel, ...] = ()
    # At or below this many seconds a video is a Short and is not fetched.
    shorts_max_seconds: int = 180
    # Optional: videos before this date are recorded as out of range. None = all.
    start_date: date | None = None
    # Seconds to wait between per-video requests (polite pacing).
    fetch_delay_seconds: float = 6.0
    # Halt triggers (network health). Unavailable and caption-less videos never
    # extend the error streak.
    consecutive_fetch_error_limit: int = 3
    fetch_error_rate_limit: float = 0.03
    missing_caption_rate_limit: float = 1.0
    # Selection: topic words or phrases, matched case-insensitively on whole words.
    topic_keywords: tuple[str, ...] = ()
    mention_threshold: int = 3
    # Fetch priority and picks: per channel, this many most-viewed and most-recent.
    pick_top: int = 10
    pick_recent: int = 10

    def channel(self, slug: str) -> Channel:
        for channel in self.channels:
            if channel.slug == slug:
                return channel
        raise KeyError(f"no channel with slug {slug!r} in the config")


def slugify(name: str) -> str:
    """`EC Krown (2nd)` -> `ec-krown-2nd`."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def load_config(path: Path, local_path: Path | None = None) -> Config:
    """Read `config.toml` and, if present, the local override file.

    `local_path` defaults to `local.toml` next to `path`. Keys in the local file
    override the committed ones.
    """
    raw = _read_toml(path)
    local = _read_toml(local_path if local_path is not None else path.parent / "local.toml")
    merged = {**raw, **local}
    channels = tuple(_channel(entry) for entry in merged.get("channels", []))
    slugs = [channel.slug for channel in channels]
    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        raise ValueError(f"duplicate channel slugs in config: {', '.join(duplicates)}")
    start = merged.get("start_date")
    return Config(
        data_root=Path(str(merged.get("data_root", DEFAULT_DATA_ROOT))).expanduser(),
        channels=channels,
        shorts_max_seconds=int(merged.get("shorts_max_seconds", 180)),
        start_date=None if start in (None, "") else _as_date(start),
        fetch_delay_seconds=float(merged.get("fetch_delay_seconds", 6.0)),
        consecutive_fetch_error_limit=int(merged.get("consecutive_fetch_error_limit", 3)),
        fetch_error_rate_limit=float(merged.get("fetch_error_rate_limit", 0.03)),
        missing_caption_rate_limit=float(merged.get("missing_caption_rate_limit", 1.0)),
        topic_keywords=tuple(str(word) for word in merged.get("topic_keywords", [])),
        mention_threshold=int(merged.get("mention_threshold", 3)),
        pick_top=int(merged.get("pick_top", 10)),
        pick_recent=int(merged.get("pick_recent", 10)),
    )


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _channel(entry: Any) -> Channel:
    if not isinstance(entry, dict) or "url" not in entry or "name" not in entry:
        raise ValueError(f"each [[channels]] entry needs `name` and `url`: {entry!r}")
    name = str(entry["name"])
    return Channel(slug=str(entry.get("slug") or slugify(name)), name=name, url=str(entry["url"]))


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
