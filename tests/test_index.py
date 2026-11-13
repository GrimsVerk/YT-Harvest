from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from helpers import make_config

from yt_harvest import index
from yt_harvest.index import (
    EXCLUDED_MEMBERS_ONLY,
    EXCLUDED_OUT_OF_RANGE,
    EXCLUDED_SHORT,
    EXCLUDED_UPCOMING,
    PENDING,
    classify,
    enumerate_channel,
    read_index,
    write_index,
)

ENTRIES: list[dict[str, object]] = [
    {"id": "long1", "title": "Macro", "duration": 1200, "timestamp": 1735689600, "view_count": 5},
    {"id": "short1", "title": "Clip", "duration": 40, "upload_date": "20250102"},
    {"id": "nodur1", "title": "Short with no duration", "duration": None},
    {"id": "live1", "title": "Stream", "duration": 7200, "live_status": "was_live"},
    {"id": "soon1", "title": "Premiere", "duration": 0, "live_status": "is_upcoming"},
    {"id": "memb1", "title": "Members", "duration": 900, "availability": "subscriber_only"},
    {"id": "long1", "title": "Macro (listed again in another tab)", "duration": 1200},
]


def test_every_listed_video_gets_one_record_with_a_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_listing(url: str) -> Iterator[dict[str, object]]:
        assert url == "https://www.youtube.com/@alpha"
        yield from ENTRIES

    monkeypatch.setattr(index, "list_channel_entries", fake_listing)
    config = make_config(tmp_path)
    videos = {v.video_id: v for v in enumerate_channel(config.channel("alpha"), config)}
    assert {vid: v.inclusion for vid, v in videos.items()} == {
        "long1": PENDING,
        "short1": EXCLUDED_SHORT,
        "nodur1": EXCLUDED_SHORT,
        "live1": PENDING,
        "soon1": EXCLUDED_UPCOMING,
        "memb1": EXCLUDED_MEMBERS_ONLY,
    }
    assert videos["long1"].title == "Macro"  # first listing wins
    assert videos["long1"].upload_date == date(2025, 1, 1)
    assert videos["long1"].view_count == 5
    assert videos["live1"].was_live
    assert videos["nodur1"].upload_date == date.min
    assert videos["nodur1"].view_count == -1


def test_start_date_excludes_older_videos_when_set(tmp_path: Path) -> None:
    config = make_config(tmp_path, start_date=date(2025, 6, 1))
    old = classify({"id": "x", "duration": 900, "upload_date": "20250101"}, "alpha", config)
    new = classify({"id": "y", "duration": 900, "upload_date": "20250701"}, "alpha", config)
    assert (old.inclusion, new.inclusion) == (EXCLUDED_OUT_OF_RANGE, PENDING)


def test_index_file_is_sorted_byte_stable_and_round_trips(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    videos = [classify(entry, "alpha", config) for entry in ENTRIES[:6]]
    path = tmp_path / "index.jsonl"
    write_index(videos, path)
    first = path.read_bytes()
    write_index(list(reversed(videos)), path)
    assert path.read_bytes() == first
    assert sorted(read_index(path), key=lambda v: v.video_id) == sorted(
        videos, key=lambda v: v.video_id
    )
