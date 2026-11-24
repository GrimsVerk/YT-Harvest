# Design: yt-harvest

What we are building. Drafted from the 2026-11-13 brief; keep it current.

## Summary

A small CLI (`yt-harvest`) that lists the uploads of the channels in the user's channels file,
fetches their existing English captions through `yt-dlp` into a local cache, and helps pick what
to read (per-channel most-viewed and most-recent; topic keywords). Agents then read the cached
transcripts and write ideas, in their own words, in the project that asked for them
(template brief: `docs/reader-brief.md`).

Ported from the general half of the archived `find_best_mobo` repo (index, transcripts, ledger,
selection, config, CLI); everything motherboard-specific and every model call was left out.

## Users and core flows

Any project and its agents. Each brings its own channels file; this repo holds none.

0. Write a channels file (copy `channels.example.toml`, keep it outside this repo) and pass it
   with `--channels FILE`, or set `channels_file` in `local.toml`. Without one, every command but
   `text` and `where` stops with a clear message.
1. `yt-harvest index`: list every configured channel into `<data_root>/index/<slug>.jsonl`.
2. `yt-harvest fetch` (or `scripts/harvest-bg.sh` detached): cache transcripts, picks first,
   then newest first; resumable; halts on a bot check.
3. `yt-harvest channels`, `status`, `picks`, `select`, `text VIDEO_ID`: check the list, see
   progress, choose, read.

## Approach

- `config.py`: `config.toml` (committed: the tool's levers, no channels), then the channels
  file (the user's: `[[channels]]`, `topic_keywords`, any lever override; template
  `channels.example.toml`), then `local.toml` (gitignored: `data_root`, default
  `~/data/yt-harvest`, and `channels_file`; template `local.toml.example`). A `channels` list in
  `config.toml` or `local.toml` is an error.
- `ytdlp.py`: the only module that touches `yt-dlp` (library, one reused client). Tests fake its
  two functions.
- `index.py`: one record per listed video: `pending`, `excluded_short` (≤ 180 s),
  `excluded_members_only`, `excluded_upcoming`, `excluded_out_of_range` (only if `start_date` set).
  Byte-stable JSONL.
- `transcripts.py`: json3 preferred, WebVTT fallback with roll-up de-duplication; cache at
  `<data_root>/transcripts/<id>.json`; `fetch_all` paces requests (`fetch_delay_seconds`).
- `ledger.py`: `failures.jsonl` with classes `no_captions`, `unavailable` (both final),
  `fetch_error` (retried), `bot_check` (halts at once; `fetch` writes `STOPPED-bot-check.txt` and
  refuses to run until a human deletes it).
- `select.py`: picks, fetch order, and keyword selection (title/description hit, or ≥ N distinct
  keywords in the transcript). Every pending video gets a record with its reason.
- Data root also holds `harvest.log`, `harvest.pid` (wrapper) and `fetch.pid` + `fetch.lock`
  (one fetcher at a time).

## Milestones

1. Port the harvester; take the channel list from the user's file (this branch, `harvest-1`).
