"""Caption tracks become parsed transcripts in a local cache.

The cache is what makes fetching resumable: a video whose transcript is on disk
is never fetched again. Nothing here imports `yt-dlp`; every byte from YouTube
arrives through `ytdlp.py`.

Cache: `<data_root>/transcripts/<video_id>.json`, one deterministic JSON record
per video. Transcripts are copyrighted: they stay in the data root, never in git.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yt_harvest.config import Config
from yt_harvest.index import Video
from yt_harvest.ledger import NO_CAPTIONS, FetchFailure, HaltTriggered, Ledger, classify_error
from yt_harvest.ytdlp import JSON3, UNKNOWN_FORMAT, fetch_video

# WebVTT inline markup (`<c>`, `<00:00:01.000>`, `<v Roger>`): presentation, not speech.
_TAG = re.compile(r"<[^>]*>")
# `00:01:02.500` or `01:02.500`; commas accepted for SRT-flavoured tracks.
_TIMESTAMP = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
_ARROW = "-->"


class NoCaptions(Exception):
    """The video genuinely has no English caption track (an answer, not a failure)."""


@dataclass(frozen=True)
class Cue:
    start_seconds: float
    text: str


@dataclass(frozen=True)
class Transcript:
    video_id: str
    cues: tuple[Cue, ...]
    description: str = ""
    source_format: str = UNKNOWN_FORMAT


def parse_vtt(raw: str) -> tuple[Cue, ...]:
    """Parse WebVTT into cues. Unparseable blocks are skipped, never raised on."""
    parsed: list[Cue] = []
    for block in re.split(r"\n\s*\n", raw.replace("\r\n", "\n").replace("\r", "\n")):
        cue = _parse_block(block)
        if cue is not None:
            parsed.append(cue)
    return _without_rollup_frames(parsed)


def _without_rollup_frames(cues: list[Cue]) -> tuple[Cue, ...]:
    """Drop the display frames a roll-up (automatic) track repeats.

    Roll-up emits `A`, `A B`, `B`, `B C`, `C`. A cue that extends or is
    contained in the last KEPT cue is a frame and is dropped, leaving `A`, `B`,
    `C`. If the final cue is an extending frame, its new tail is kept so the
    last line is not lost. An ordinary track is untouched.
    """
    kept: list[Cue] = []
    for index, cue in enumerate(cues):
        if not kept:
            kept.append(cue)
            continue
        previous = kept[-1].text
        if cue.text == previous or previous.endswith(f" {cue.text}"):
            continue
        if cue.text.startswith(f"{previous} "):
            if index == len(cues) - 1:
                kept.append(Cue(cue.start_seconds, cue.text[len(previous) + 1 :]))
            continue
        kept.append(cue)
    return tuple(kept)


def parse_json3(raw: str) -> tuple[Cue, ...]:
    """Parse YouTube's json3 captions: one cue per text-bearing event.

    Segment texts are joined verbatim (json3 puts the leading space on the next
    word). Whitespace-only events (`aAppend` line breaks) give no cue. A payload
    that is not a JSON object raises: zero cues from a captioned video would be
    indistinguishable from a video with none.
    """
    try:
        document: Any = json.loads(raw)
    except (ValueError, TypeError) as error:
        raise ValueError(f"not a json3 caption document: {error}") from error
    if not isinstance(document, dict):
        raise ValueError("json3 caption document is not an object")
    cues: list[Cue] = []
    for event in document.get("events") or ():
        if not isinstance(event, dict):
            continue
        text = "".join(
            str(segment.get("utf8", ""))
            for segment in (event.get("segs") or ())
            if isinstance(segment, dict)
        )
        if not text.strip():
            continue
        cues.append(Cue(float(event.get("tStartMs", 0)) / 1000.0, " ".join(text.split())))
    return tuple(cues)


def cache_path(video_id: str, config: Config) -> Path:
    return config.data_root / "transcripts" / f"{video_id}.json"


def load_cached(video_id: str, config: Config) -> Transcript | None:
    """The cached transcript, or None. A corrupt entry reads as absent (refetched)."""
    path = cache_path(video_id, config)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            record: Any = json.load(handle)
        return Transcript(
            video_id=str(record["video_id"]),
            cues=tuple(
                Cue(float(cue["start_seconds"]), str(cue["text"])) for cue in record["cues"]
            ),
            description=str(record.get("description", "")),
            source_format=str(record.get("source_format", UNKNOWN_FORMAT)),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def fetch_transcript(video_id: str) -> Transcript:
    """Fetch and parse one video's captions. Never touches the cache.

    Raises `NoCaptions` when there is no English track; every other exception
    propagates so the caller, which owns the ledger, decides what it means.
    """
    fetched = fetch_video(video_id)
    if fetched.captions is None:
        raise NoCaptions(video_id)
    cues = (
        parse_json3(fetched.captions)
        if fetched.caption_format == JSON3
        else parse_vtt(fetched.captions)
    )
    return Transcript(video_id, cues, fetched.description, fetched.caption_format)


def fetch_all(
    videos: Iterable[Video],
    config: Config,
    ledger: Ledger,
    *,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> int:
    """Fetch and cache, in the given order, every video not cached yet.

    Skips cache hits and videos whose earlier failure was definitive. Waits
    `config.fetch_delay_seconds` after every request. Returns how many were
    fetched; raises `HaltTriggered` as soon as a trigger fires (the ledger is
    already on disk by then).
    """
    skip = ledger.permanent_ids()
    fetched = 0
    for video in videos:
        if video.video_id in skip or load_cached(video.video_id, config) is not None:
            continue
        failure: FetchFailure | None = None
        try:
            transcript = fetch_transcript(video.video_id)
        except NoCaptions:
            failure = _failure(video, NO_CAPTIONS, "")
        except Exception as error:
            # Deliberately broad: whatever the boundary raises is classified
            # and recorded; the triggers decide if the run is still healthy.
            failure = _failure(video, classify_error(str(error)), str(error))
        if failure is None:
            write_cache(transcript, config)
            ledger.record_success(video.video_id)
            fetched += 1
            log(f"ok {video.channel} {video.video_id} {len(transcript.cues)} cues")
        else:
            ledger.record(failure)
            log(f"{failure.failure_class} {video.channel} {video.video_id} {failure.detail[:200]}")
            trigger = ledger.check_triggers()
            if trigger is not None:
                raise HaltTriggered(trigger)
        sleep(config.fetch_delay_seconds)
    return fetched


def _failure(video: Video, failure_class: str, detail: str) -> FetchFailure:
    return FetchFailure(
        channel=video.channel,
        video_id=video.video_id,
        title=video.title,
        upload_date=video.upload_date,
        failure_class=failure_class,
        detail=detail,
        attempts=1,
    )


def write_cache(transcript: Transcript, config: Config) -> None:
    """Write one transcript as deterministic JSON, atomically."""
    path = cache_path(transcript.video_id, config)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "video_id": transcript.video_id,
        "cues": [{"start_seconds": cue.start_seconds, "text": cue.text} for cue in transcript.cues],
        "description": transcript.description,
        "source_format": transcript.source_format,
    }
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, sort_keys=True))
        handle.write("\n")
    tmp.replace(path)


def render_text(transcript: Transcript, every_seconds: float = 60.0) -> str:
    """Plain reading text: cues joined into paragraphs, a `[m:ss]` mark per paragraph."""
    paragraphs: list[str] = []
    current: list[str] = []
    started = 0.0
    for cue in transcript.cues:
        if current and cue.start_seconds - started >= every_seconds:
            paragraphs.append(f"[{_clock(started)}] {' '.join(current)}")
            current = []
        if not current:
            started = cue.start_seconds
        current.append(cue.text)
    if current:
        paragraphs.append(f"[{_clock(started)}] {' '.join(current)}")
    return "\n\n".join(paragraphs) + "\n" if paragraphs else ""


def _clock(seconds: float) -> str:
    whole = int(seconds)
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _parse_block(block: str) -> Cue | None:
    lines = [line for line in block.split("\n") if line.strip()]
    timing_index = next((i for i, line in enumerate(lines) if _ARROW in line), None)
    if timing_index is None:
        return None
    match = _TIMESTAMP.search(lines[timing_index].split(_ARROW)[0])
    if match is None:
        return None
    hours, minutes, seconds, fraction = match.groups()
    start = int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)
    start_seconds = start + int(fraction) / 10 ** len(fraction)
    parts = [_TAG.sub("", line).strip() for line in lines[timing_index + 1 :]]
    text = " ".join(part for part in parts if part).strip()
    if not text:
        return None
    return Cue(start_seconds, text)
