"""Shared builders for tests. Synthetic data only: no real transcripts in git."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from yt_harvest.config import Channel, Config
from yt_harvest.index import PENDING, Video

FIXTURES = Path(__file__).parent / "fixtures"


def make_config(tmp_path: Path, **overrides: object) -> Config:
    values: dict[str, object] = {
        "data_root": tmp_path / "data",
        "channels": (
            Channel("alpha", "Alpha", "https://www.youtube.com/@alpha"),
            Channel("beta", "Beta", "https://www.youtube.com/@beta"),
        ),
        "fetch_delay_seconds": 0.0,
        "pick_top": 2,
        "pick_recent": 2,
    }
    values.update(overrides)
    return Config(**values)  # type: ignore[arg-type]


def video(
    video_id: str,
    *,
    channel: str = "alpha",
    day: date = date(2025, 1, 1),
    views: int = 100,
    title: str = "",
    inclusion: str = PENDING,
) -> Video:
    return Video(
        channel=channel,
        video_id=video_id,
        title=title or f"Video {video_id}",
        upload_date=day,
        duration_seconds=600,
        view_count=views,
        was_live=False,
        inclusion=inclusion,
    )
