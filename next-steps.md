# Next steps

Work in flight. Write a task here before starting it; delete it when done.
Keep this short enough to read in one go.

Branch `harvest-1`, draft PR #1 (brief: `chief-of-staff/briefs/yt-harvest-1.md`).

- Done: harvester ported (index, fetch, ledger, picks, select, text, channels); docs filled.
- Done (2026-11-24): general tool. The channel list and topic words come from the user's
  channels file (`--channels FILE` or `channels_file` in `local.toml`; template
  `channels.example.toml`); no list = clear error. The first user's list and the ideas mined
  from it live with that user, outside this repo.
- First harvest (a dozen channels indexed, 10,431 pending videos), **blocked, owner's call:**
  the first fetch got HTTP 429 (Too Many Requests) from YouTube after 8 transcripts,
  2026-11-13 01:33 UTC, straight after indexing all channels. It halted as designed and wrote
  `<data_root>/STOPPED-bot-check.txt`. Per the brief no retry and no workaround. To resume
  (owner decides when): delete the stop file, then `scripts/harvest-bg.sh --no-index` with the
  list set (`--channels FILE` or `channels_file`). Pacing is 15 s per video, ~2 days for
  everything; the 10 most-viewed + 10 most-recent per channel come first, ~1 h.
- Next, once picks are cached: read each channel's picks (`uv run yt-harvest picks`) with the
  template brief `docs/reader-brief.md`; per-channel notes go to `<data_root>/notes/<slug>.md`,
  ideas to the project that uses them.
