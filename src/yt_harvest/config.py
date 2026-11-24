"""Every lever, declared once.

Three files feed it, later ones overriding earlier ones key by key:

1. `config.toml` (committed): the tool's levers (pacing, halts, picks). No channels.
2. The channels file (supplied by whoever uses the tool, never committed here):
   the `[[channels]]` list and anything specific to that use, typically
   `topic_keywords`. Given by `--channels FILE` on the command line, or by
   `channels_file` in `local.toml` (relative paths are relative to `local.toml`).
   Template: `channels.example.toml`.
3. `local.toml` (gitignored; copy `local.toml.example`): what is machine-specific,
   `data_root` (where the index, transcripts, ledger, log and PID file live) and
   `channels_file`. Transcripts are copyrighted and never enter git, which is why
   the data root defaults to a folder outside the repo.

A missing key falls back to its default; a missing `config.toml` or `local.toml`
reads as empty. A named channels file that does not exist is an error, and so is
a `channels` list in `config.toml` or `local.toml`.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

DEFAULT_DATA_ROOT = "~/data/yt-harvest"
NO_CHANNELS = (
    "no channel list given: pass `--channels FILE` or set `channels_file` in local.toml "
    "(templates: channels.example.toml, local.toml.example)"
)


class ConfigError(ValueError):
    """A config problem the user must fix; the CLI prints it without a traceback."""


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
    # The channels file the list came from (None = no list given).
    channels_file: Path | None = None
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
    """`Some Channel (2nd)` -> `some-channel-2nd`."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def load_config(
    path: Path, local_path: Path | None = None, channels_path: Path | None = None
) -> Config:
    """Read `config.toml`, the channels file and the local override file.

    `local_path` defaults to `local.toml` next to `path`. `channels_path` (from
    `--channels`) wins over `channels_file` in the local file.
    """
    raw = _read_toml(path)
    local_file = local_path if local_path is not None else path.parent / "local.toml"
    local = _read_toml(local_file)
    for source, table in ((path, raw), (local_file, local)):
        if "channels" in table:
            raise ConfigError(
                f"{source}: move the [[channels]] list into its own channels file "
                "(see channels.example.toml) and point to it with --channels or channels_file"
            )
    if "channels_file" in raw:
        raise ConfigError(f"{path}: `channels_file` is machine-specific; set it in local.toml")
    list_file: Path | None = None
    if channels_path is not None:
        list_file = channels_path.expanduser()
    elif local.get("channels_file"):
        list_file = Path(str(local["channels_file"])).expanduser()
        if not list_file.is_absolute():
            list_file = local_file.parent / list_file
    listed: dict[str, Any] = {}
    if list_file is not None:
        if not list_file.is_file():
            raise ConfigError(f"channels file not found: {list_file}")
        listed = _read_toml(list_file)
        if "channels_file" in listed:
            raise ConfigError(f"{list_file}: `channels_file` belongs in local.toml")
    merged = {**raw, **listed, **local}
    channels = tuple(_channel(entry) for entry in listed.get("channels", []))
    slugs = [channel.slug for channel in channels]
    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        raise ConfigError(f"duplicate channel slugs in config: {', '.join(duplicates)}")
    start = merged.get("start_date")
    return Config(
        data_root=Path(str(merged.get("data_root", DEFAULT_DATA_ROOT))).expanduser(),
        channels=channels,
        channels_file=list_file,
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


def require_channels(config: Config) -> None:
    """Raise `ConfigError` unless a channels file with at least one channel was given."""
    if config.channels_file is None:
        raise ConfigError(NO_CHANNELS)
    if not config.channels:
        raise ConfigError(f"{config.channels_file}: no [[channels]] entries")


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _channel(entry: Any) -> Channel:
    if not isinstance(entry, dict) or "url" not in entry or "name" not in entry:
        raise ConfigError(f"each [[channels]] entry needs `name` and `url`: {entry!r}")
    name = str(entry["name"])
    return Channel(slug=str(entry.get("slug") or slugify(name)), name=name, url=str(entry["url"]))


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))
