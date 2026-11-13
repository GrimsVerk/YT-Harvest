# Next steps

Work in flight. Write a task here before starting it; delete it when done.
Keep this short enough to read in one go.

Branch `harvest-1` (brief: `chief-of-staff/briefs/yt-harvest-1.md`).

- Done: harvester ported (index, fetch, ledger, picks, select, text); docs filled.
- Doing: background harvest of the 12 channels (`scripts/harvest-bg.sh`; check with
  `uv run yt-harvest status` and `<data_root>/harvest.log`). Resume after a stop with
  `scripts/harvest-bg.sh --no-index`. If `<data_root>/STOPPED-bot-check.txt` exists, YouTube
  asked for a bot check: do not work around it; tell the owner.
- Next: mine ideas into `docs/ideas/grimstrade-ideas.md` (per channel: 10 most-viewed + 10 most
  recent first; `uv run yt-harvest picks`).
- Owner: EC Krown's second channel `@ECKrown4` returns 404; need the right URL.
