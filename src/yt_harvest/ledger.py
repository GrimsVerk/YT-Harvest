"""The failure ledger and the halt triggers that read it.

Every video that could not be fetched lands in `<data_root>/failures.jsonl`
with its class, detail and how many runs have tried it. The triggers stop a run
that has stopped working instead of grinding through thousands of videos.

Failure classes:

- `no_captions`: YouTube answered; the video has no English track. Not retried.
- `unavailable`: private, members-only, removed, age-gated, not yet aired. Not retried.
- `fetch_error`: anything else. Retried on the next run; counts towards the triggers.
- `bot_check`: YouTube asked us to sign in to prove we are not a bot, or rate
  limited us. The run stops at once (owner rule: never work around it).

The file is rewritten on every record, so a halt or crash still leaves the
evidence on disk. Entries from earlier runs that this run did not retry are kept.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from yt_harvest.config import Config

NO_CAPTIONS = "no_captions"
UNAVAILABLE = "unavailable"
FETCH_ERROR = "fetch_error"
BOT_CHECK = "bot_check"

# Classes that are a definitive answer from YouTube: never retried.
PERMANENT = frozenset({NO_CAPTIONS, UNAVAILABLE})

# Lower-cased fragments of yt-dlp error messages. Age gating also says "sign in
# to confirm", so it is matched (as unavailable) before the bot check.
_UNAVAILABLE_MARKERS = (
    "confirm your age",
    "age-restricted",
    "private video",
    "members-only",
    "members only",
    "join this channel",
    "video unavailable",
    "has been removed",
    "no longer available",
    "this live event will begin",
    "premieres in",
    "is not available",
    "copyright",
)
_BOT_MARKERS = (
    "not a bot",
    "sign in to confirm",
    "http error 429",
    "too many requests",
)


def classify_error(message: str) -> str:
    """Map a fetch exception's message to a failure class."""
    lowered = message.lower()
    if any(marker in lowered for marker in _UNAVAILABLE_MARKERS):
        return UNAVAILABLE
    if any(marker in lowered for marker in _BOT_MARKERS):
        return BOT_CHECK
    return FETCH_ERROR


@dataclass(frozen=True)
class FetchFailure:
    channel: str
    video_id: str
    title: str
    upload_date: date
    failure_class: str
    detail: str
    attempts: int


class HaltTriggered(Exception):
    """A halt trigger fired: the run stops, with its evidence on disk."""

    def __init__(self, trigger: str) -> None:
        super().__init__(f"halt trigger fired: {trigger}")
        self.trigger = trigger


class Ledger:
    """Failures across runs, and the triggers over this run's share of them.

    `attempting` is how many videos this run will try: the denominator of the
    rate triggers (a zero never divides).
    """

    def __init__(self, path: Path, config: Config, attempting: int) -> None:
        self._path = path
        self._config = config
        self._attempting = attempting
        self._entries: dict[str, FetchFailure] = {f.video_id: f for f in _read(path)}
        self._this_run: list[FetchFailure] = []
        self._consecutive_errors = 0

    def permanent_ids(self) -> frozenset[str]:
        """Ids whose earlier failure was definitive: skip them."""
        return frozenset(
            video_id for video_id, f in self._entries.items() if f.failure_class in PERMANENT
        )

    def record(self, failure: FetchFailure) -> None:
        previous = self._entries.get(failure.video_id)
        counted = replace(failure, attempts=(previous.attempts if previous else 0) + 1)
        self._entries[failure.video_id] = counted
        self._this_run.append(counted)
        if counted.failure_class == FETCH_ERROR:
            self._consecutive_errors += 1
        else:
            self._consecutive_errors = 0
        self._write()

    def record_success(self, video_id: str) -> None:
        self._consecutive_errors = 0
        if self._entries.pop(video_id, None) is not None:
            self._write()

    def check_triggers(self) -> str | None:
        """Name the trigger that fired, or None while the run is healthy."""
        if self._this_run and self._this_run[-1].failure_class == BOT_CHECK:
            return BOT_CHECK
        if self._consecutive_errors >= self._config.consecutive_fetch_error_limit:
            return "consecutive_fetch_errors"
        if self._rate(FETCH_ERROR) > self._config.fetch_error_rate_limit:
            return "fetch_error_rate"
        if self._rate(NO_CAPTIONS) > self._config.missing_caption_rate_limit:
            return "missing_caption_rate"
        return None

    def this_run(self) -> tuple[FetchFailure, ...]:
        return tuple(self._this_run)

    def all_entries(self) -> tuple[FetchFailure, ...]:
        return tuple(self._entries.values())

    def _rate(self, failure_class: str) -> float:
        # Rates need some volume behind them before they mean anything; the
        # consecutive trigger covers a dead network early on.
        if self._attempting <= 0 or len(self._this_run) < 10:
            return 0.0
        count = sum(1 for f in self._this_run if f.failure_class == failure_class)
        return count / self._attempting

    def _write(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(self._entries.values(), key=lambda f: (f.channel, f.video_id))
        tmp = self._path.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as handle:
            for failure in ordered:
                record: dict[str, Any] = asdict(failure)
                record["upload_date"] = failure.upload_date.isoformat()
                handle.write(json.dumps(record, sort_keys=True))
                handle.write("\n")
        tmp.replace(self._path)


def _read(path: Path) -> tuple[FetchFailure, ...]:
    """A missing or damaged file reads as empty; a bad line is skipped."""
    if not path.exists():
        return ()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ()
    failures: list[FetchFailure] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            failures.append(
                FetchFailure(
                    channel=str(record.get("channel", "")),
                    video_id=str(record["video_id"]),
                    title=str(record.get("title", "")),
                    upload_date=date.fromisoformat(record["upload_date"]),
                    failure_class=str(record["failure_class"]),
                    detail=str(record.get("detail", "")),
                    attempts=int(record.get("attempts", 1)),
                )
            )
        except (ValueError, KeyError, TypeError):
            continue
    return tuple(failures)
