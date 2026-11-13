from __future__ import annotations

from datetime import date
from pathlib import Path

from helpers import make_config, video

from yt_harvest.index import EXCLUDED_SHORT
from yt_harvest.select import (
    DESCRIPTION_HIT,
    EXCLUDED,
    MOST_RECENT,
    MOST_VIEWED,
    NO_KEYWORDS,
    THRESHOLD,
    TITLE_HIT,
    compile_matcher,
    fetch_order,
    picks,
    select_video,
)
from yt_harvest.transcripts import Cue, Transcript


def _transcript(text: str, description: str = "") -> Transcript:
    return Transcript("v", (Cue(0.0, text),), description)


def test_selection_reasons() -> None:
    matcher = compile_matcher(["RSI", "moving average", "fed"])
    plain = video("v", title="My week")
    assert select_video(video("v", title="The RSI trick"), None, matcher, 2).reason == TITLE_HIT
    assert (
        select_video(plain, _transcript("nothing", "uses a moving average"), matcher, 2).reason
        == DESCRIPTION_HIT
    )
    passed = select_video(plain, _transcript("the Fed and the rsi and the RSI"), matcher, 2)
    assert (passed.reason, passed.keywords_found) == (THRESHOLD, ("fed", "rsi"))
    # Whole words only: "federal" and "first" do not count as "fed" or "rsi".
    assert select_video(plain, _transcript("federal first"), matcher, 1).reason == EXCLUDED
    assert select_video(plain, None, None, 1).reason == NO_KEYWORDS


def test_picks_take_most_viewed_and_most_recent_per_channel_once(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    videos = [
        video("a1", views=900, day=date(2020, 1, 1)),
        video("a2", views=800, day=date(2025, 3, 1)),
        video("a3", views=10, day=date(2025, 2, 1)),
        video("a4", views=5, day=date(2019, 1, 1)),
        video("a5", views=99999, inclusion=EXCLUDED_SHORT),
        video("b1", channel="beta", views=-1, day=date(2024, 1, 1)),
    ]
    result = [(p.video.video_id, p.reasons) for p in picks(videos, config)]
    assert result == [
        ("a1", (MOST_VIEWED,)),
        ("a2", (MOST_VIEWED, MOST_RECENT)),
        ("a3", (MOST_RECENT,)),
        ("b1", (MOST_RECENT,)),  # no view count: never most-viewed
    ]


def test_fetch_order_is_picks_round_robin_then_newest_first(tmp_path: Path) -> None:
    config = make_config(tmp_path, pick_top=1, pick_recent=0)
    videos = [
        video("a1", views=50, day=date(2020, 1, 1)),
        video("a2", views=1, day=date(2025, 1, 1)),
        video("b1", channel="beta", views=70, day=date(2021, 1, 1)),
        video("b2", channel="beta", views=2, day=date(2024, 1, 1)),
        video("s", inclusion=EXCLUDED_SHORT),
    ]
    assert [v.video_id for v in fetch_order(videos, config)] == ["a1", "b1", "a2", "b2"]
