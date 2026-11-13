"""Command-line entry point: `yt-harvest <command>`.

Commands:
  index [--channel SLUG ...]   list each channel's uploads into the index
  fetch [--limit N]            cache transcripts: picks first, then newest first
  status                       per-channel counts: indexed, pending, cached, failed
  picks [--channel SLUG]       each channel's most-viewed and most-recent videos
  select                       topic selection over cached transcripts
  text VIDEO_ID                print one cached transcript as plain reading text
  where                        print the data root
"""

from __future__ import annotations

import fcntl
import os
import sys
from argparse import ArgumentParser, Namespace
from collections import Counter
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from yt_harvest.config import Config, load_config
from yt_harvest.index import (
    PENDING,
    Video,
    enumerate_channel,
    index_path,
    read_all,
    write_index,
)
from yt_harvest.ledger import BOT_CHECK, HaltTriggered, Ledger
from yt_harvest.select import fetch_order, picks, select_all, write_selected
from yt_harvest.transcripts import cache_path, fetch_all, load_cached, render_text

STOP_FILE = "STOPPED-bot-check.txt"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = load_config(args.config)
    command: str = args.command
    handler = {
        "index": _index,
        "fetch": _fetch,
        "status": _status,
        "picks": _picks,
        "select": _select,
        "text": _text,
        "where": _where,
    }[command]
    return handler(config, args)


def _parser() -> ArgumentParser:
    parser = ArgumentParser(prog="yt-harvest", description="Harvest YouTube transcripts.")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    sub = parser.add_subparsers(dest="command", required=True)
    index = sub.add_parser("index", help="list each channel's uploads into the index")
    index.add_argument("--channel", action="append", default=[], help="only this slug")
    fetch = sub.add_parser("fetch", help="cache transcripts (picks first, then newest)")
    fetch.add_argument("--limit", type=int, default=0, help="stop after N fetches (0 = all)")
    sub.add_parser("status", help="per-channel counts")
    picks_cmd = sub.add_parser("picks", help="most-viewed and most-recent per channel")
    picks_cmd.add_argument("--channel", default="", help="only this slug")
    sub.add_parser("select", help="topic selection over cached transcripts")
    text = sub.add_parser("text", help="print one cached transcript")
    text.add_argument("video_id")
    sub.add_parser("where", help="print the data root")
    return parser


def _index(config: Config, args: Namespace) -> int:
    wanted = set(args.channel)
    unknown = wanted - {c.slug for c in config.channels}
    if unknown:
        print(f"unknown channel slug(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2
    failed = 0
    for channel in config.channels:
        if wanted and channel.slug not in wanted:
            continue
        try:
            videos = enumerate_channel(channel, config)
        except Exception as error:  # one bad channel must not lose the others
            print(f"{channel.slug}: listing failed: {error}", file=sys.stderr)
            failed += 1
            continue
        path = index_path(channel.slug, config)
        write_index(videos, path)
        counts = Counter(video.inclusion for video in videos)
        detail = ", ".join(f"{count} {name}" for name, count in sorted(counts.items()))
        print(f"{channel.slug}: {len(videos)} videos ({detail}) -> {path}", flush=True)
    return 1 if failed else 0


@contextmanager
def _single_fetcher(config: Config) -> Iterator[bool]:
    """Hold `fetch.lock` for the run and keep our PID in `fetch.pid`.

    Yields False if another fetch already holds the lock.
    """
    config.data_root.mkdir(parents=True, exist_ok=True)
    pid_path = config.data_root / "fetch.pid"
    with (config.data_root / "fetch.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
        try:
            yield True
        finally:
            pid_path.unlink(missing_ok=True)


def _fetch(config: Config, args: Namespace) -> int:
    stop = config.data_root / STOP_FILE
    if stop.exists():
        print(f"Refusing to fetch: {stop} exists (YouTube asked for a bot check).")
        print("Read it, wait, and delete it by hand before fetching again.")
        return 1
    videos = read_all(config)
    if not videos:
        print("No index yet: run `yt-harvest index` first.")
        return 1
    with _single_fetcher(config) as alone:
        if not alone:
            print("Another fetch is already running (fetch.lock is held).")
            return 1
        order = fetch_order(videos, config)
        if args.limit > 0:
            uncached = [v for v in order if not cache_path(v.video_id, config).exists()]
            order = uncached[: args.limit]
        ledger = Ledger(config.data_root / "failures.jsonl", config, len(order))
        print(f"{_now()} fetch start: {len(order)} pending videos in order", flush=True)
        try:
            fetched = fetch_all(order, config, ledger, log=_log)
        except HaltTriggered as halt:
            print(f"{_now()} HALTED: {halt.trigger}", flush=True)
            if halt.trigger == BOT_CHECK:
                last = ledger.this_run()[-1]
                stop.write_text(
                    f"{_now()} YouTube asked for a bot check or rate-limited us while\n"
                    f"fetching {last.video_id}: {last.detail}\n"
                    "Fetching stopped. Owner rule: no cookies, proxies or other\n"
                    "workarounds. Delete this file by hand to allow fetching again.\n",
                    encoding="utf-8",
                )
            return 1
        failures = Counter(f.failure_class for f in ledger.this_run())
        print(f"{_now()} fetch done: {fetched} fetched, failures {dict(failures)}", flush=True)
    return 0


def _log(line: str) -> None:
    print(f"{_now()} {line}", flush=True)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _status(config: Config, args: Namespace) -> int:
    videos = read_all(config)
    ledger = Ledger(config.data_root / "failures.jsonl", config, 0)
    failed = Counter(f.channel for f in ledger.all_entries())
    print(f"data root: {config.data_root}")
    print(f"{'channel':28} {'indexed':>8} {'pending':>8} {'cached':>8} {'failed':>8}")
    total = Counter[str]()
    for channel in config.channels:
        mine = [v for v in videos if v.channel == channel.slug]
        pending = [v for v in mine if v.inclusion == PENDING]
        cached = sum(1 for v in pending if cache_path(v.video_id, config).exists())
        row = Counter(
            indexed=len(mine), pending=len(pending), cached=cached, failed=failed[channel.slug]
        )
        total.update(row)
        print(
            f"{channel.slug:28} {row['indexed']:>8} {row['pending']:>8} "
            f"{row['cached']:>8} {row['failed']:>8}"
        )
    print(
        f"{'TOTAL':28} {total['indexed']:>8} {total['pending']:>8} "
        f"{total['cached']:>8} {total['failed']:>8}"
    )
    zero = sum(1 for v in videos if v.duration_seconds == 0 and v.upload_date.year > 1)
    print(f"dated videos with no duration (classed as Shorts): {zero}")
    if (config.data_root / STOP_FILE).exists():
        print(f"STOPPED: {config.data_root / STOP_FILE} exists (bot check)")
    return 0


def _picks(config: Config, args: Namespace) -> int:
    videos: list[Video] = read_all(config)
    if args.channel:
        videos = [v for v in videos if v.channel == args.channel]
    for pick in picks(videos, config):
        v = pick.video
        cached = "cached" if cache_path(v.video_id, config).exists() else "-"
        print(
            f"{v.channel}\t{v.video_id}\t{v.upload_date.isoformat()}\t{v.view_count}\t"
            f"{'+'.join(pick.reasons)}\t{cached}\t{v.title}"
        )
    return 0


def _select(config: Config, args: Namespace) -> int:
    selections = select_all(read_all(config), config)
    path = config.data_root / "selected.jsonl"
    write_selected(selections, path)
    counts = Counter(s.reason for s in selections)
    print(f"{len(selections)} pending videos -> {path}")
    for reason, count in sorted(counts.items()):
        print(f"  {count} {reason}")
    return 0


def _text(config: Config, args: Namespace) -> int:
    transcript = load_cached(args.video_id, config)
    if transcript is None:
        print(f"no cached transcript for {args.video_id}", file=sys.stderr)
        return 1
    sys.stdout.write(render_text(transcript))
    return 0


def _where(config: Config, args: Namespace) -> int:
    print(config.data_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
