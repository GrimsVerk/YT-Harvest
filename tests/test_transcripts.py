from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import FIXTURES, make_config, video

from yt_harvest import transcripts
from yt_harvest.ledger import BOT_CHECK, NO_CAPTIONS, UNAVAILABLE, HaltTriggered, Ledger
from yt_harvest.transcripts import (
    Cue,
    Transcript,
    fetch_all,
    load_cached,
    parse_json3,
    parse_vtt,
    render_text,
    write_cache,
)
from yt_harvest.ytdlp import JSON3, VideoFetch


def test_rollup_vtt_keeps_each_line_once_with_its_solo_start_and_the_last_line() -> None:
    cues = parse_vtt((FIXTURES / "rollup.vtt").read_text())
    assert [cue.text for cue in cues] == [
        "the market opened lower",
        "then it recovered",
        "by the close",
    ]
    assert cues[0].start_seconds == 1.0
    assert cues[1].start_seconds == 5.0


def test_json3_joins_segments_verbatim_and_drops_line_break_events() -> None:
    cues = parse_json3((FIXTURES / "captions.json3").read_text())
    assert cues == (
        Cue(0.0, "Rates went up"),
        Cue(2.5, "and stocks fell"),
        Cue(61.0, "a minute later"),
    )


def test_json3_that_is_not_json_raises() -> None:
    with pytest.raises(ValueError):
        parse_json3("<html>nope</html>")


def test_cache_round_trips_and_is_byte_stable(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    transcript = Transcript("abc", (Cue(0.0, "hi"), Cue(1.5, "there")), "desc", JSON3)
    write_cache(transcript, config)
    first = (config.data_root / "transcripts" / "abc.json").read_bytes()
    write_cache(transcript, config)
    assert (config.data_root / "transcripts" / "abc.json").read_bytes() == first
    assert load_cached("abc", config) == transcript


def test_corrupt_cache_entry_reads_as_absent(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    path = config.data_root / "transcripts" / "bad.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json")
    assert load_cached("bad", config) is None


def test_render_text_marks_paragraphs_by_time() -> None:
    transcript = Transcript("x", parse_json3((FIXTURES / "captions.json3").read_text()))
    assert render_text(transcript) == (
        "[0:00] Rates went up and stocks fell\n\n[1:01] a minute later\n"
    )


def _fake_boundary(monkeypatch: pytest.MonkeyPatch, outcomes: dict[str, object]) -> list[str]:
    calls: list[str] = []

    def fake(video_id: str) -> VideoFetch:
        calls.append(video_id)
        outcome = outcomes[video_id]
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, VideoFetch)
        return outcome

    monkeypatch.setattr(transcripts, "fetch_video", fake)
    return calls


def _json3(text: str) -> VideoFetch:
    payload = json.dumps({"events": [{"tStartMs": 0, "segs": [{"utf8": text}]}]})
    return VideoFetch(captions=payload, description="d", caption_format=JSON3)


def test_fetch_all_caches_skips_cached_and_records_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = make_config(tmp_path)
    write_cache(Transcript("old", (Cue(0, "cached"),)), config)
    calls = _fake_boundary(
        monkeypatch,
        {
            "new": _json3("fresh"),
            "none": VideoFetch(captions=None, description="", caption_format="unknown"),
            "priv": RuntimeError("ERROR: [youtube] priv: Private video. Sign in if granted"),
        },
    )
    ledger = Ledger(config.data_root / "failures.jsonl", config, 4)
    slept: list[float] = []
    videos = [video("old"), video("new"), video("none"), video("priv")]
    fetched = fetch_all(videos, config, ledger, sleep=slept.append, log=lambda _: None)

    assert fetched == 1
    assert calls == ["new", "none", "priv"]  # the cached one is never requested
    assert len(slept) == 3  # paced after every request
    cached = load_cached("new", config)
    assert cached is not None and cached.cues[0].text == "fresh"
    classes = {f.video_id: f.failure_class for f in ledger.all_entries()}
    assert classes == {"none": NO_CAPTIONS, "priv": UNAVAILABLE}

    # A rerun requests nothing: cached and definitive failures are both skipped.
    calls.clear()
    rerun = Ledger(config.data_root / "failures.jsonl", config, 4)
    fetch_all(videos, config, rerun, sleep=slept.append, log=lambda _: None)
    assert calls == []


def test_bot_check_halts_at_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = make_config(tmp_path)
    calls = _fake_boundary(
        monkeypatch,
        {
            "a": RuntimeError("Sign in to confirm you're not a bot. Use --cookies"),
            "b": _json3("never reached"),
        },
    )
    ledger = Ledger(config.data_root / "failures.jsonl", config, 2)
    with pytest.raises(HaltTriggered) as halt:
        fetch_all([video("a"), video("b")], config, ledger, sleep=lambda _: None, log=print)
    assert halt.value.trigger == BOT_CHECK
    assert calls == ["a"]


def test_age_gate_is_unavailable_not_a_bot_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = make_config(tmp_path)
    _fake_boundary(
        monkeypatch,
        {"a": RuntimeError("Sign in to confirm your age. This video may be inappropriate")},
    )
    ledger = Ledger(config.data_root / "failures.jsonl", config, 1)
    fetch_all([video("a")], config, ledger, sleep=lambda _: None, log=lambda _: None)
    assert ledger.all_entries()[0].failure_class == UNAVAILABLE


def test_consecutive_network_errors_halt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = make_config(tmp_path, consecutive_fetch_error_limit=2)
    _fake_boundary(monkeypatch, {vid: OSError("connection reset") for vid in "abc"})
    ledger = Ledger(config.data_root / "failures.jsonl", config, 3)
    with pytest.raises(HaltTriggered) as halt:
        fetch_all(
            [video(v) for v in "abc"], config, ledger, sleep=lambda _: None, log=lambda _: None
        )
    assert halt.value.trigger == "consecutive_fetch_errors"
    # The evidence is on disk, and a transient error is retried next run.
    reread = Ledger(config.data_root / "failures.jsonl", config, 3)
    assert len(reread.all_entries()) == 2
    assert reread.permanent_ids() == frozenset()
