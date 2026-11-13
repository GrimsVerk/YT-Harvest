# Next steps

Work in flight. Write a task here before starting it; delete it when done.
Keep this short enough to read in one go.

Branch `harvest-1`, draft PR #1 (brief: `chief-of-staff/briefs/yt-harvest-1.md`).

- Done: harvester ported (index, fetch, ledger, picks, select, text); docs filled; all 12
  channels indexed (10,431 pending videos, Shorts and members-only excluded).
- **Blocked, owner's call:** the first fetch got HTTP 429 (Too Many Requests) from YouTube after
  8 transcripts, 2026-11-13 01:33 UTC, straight after indexing all channels. It halted as
  designed and wrote `<data_root>/STOPPED-bot-check.txt`. Per the brief no retry and no
  workaround. To resume (owner decides when, ideally after a day): delete the stop file, then
  `scripts/harvest-bg.sh --no-index` (pacing is now 15 s per video, ~2 days for everything; the
  10 most-viewed + 10 most-recent per channel come first, ~1 h).
- Doing: ideas from the 9 transcripts we have into `docs/ideas/grimstrade-ideas.md`.
- Next, once picks are cached: read each channel's 10 most-viewed + 10 most-recent
  (`uv run yt-harvest picks`) and extend the ideas file. A reader brief for subagents is in
  `docs/ideas/reader-brief.md`; per-channel notes go to `<data_root>/notes/<slug>.md`.
- Owner: EC Krown's second channel `@ECKrown4` returns 404; need the right URL.
