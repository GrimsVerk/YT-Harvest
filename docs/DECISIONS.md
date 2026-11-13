# Decisions: yt-harvest

Settled decisions and why, newest first. Don't relitigate; update an entry if the owner changes it.

- 2026-11-13: Dependency `yt-dlp` (Unlicense). Why: listing channels and reading caption tracks
  needs YouTube's internal API, which yt-dlp maintains; the stdlib cannot. Carried over from
  `find_best_mobo`, where it was approved; the brief asks for this port.
- 2026-11-13: Channel handles not given in the brief were found by trying the obvious handle
  with yt-dlp and checking the returned channel name and size: George Gammon `@GeorgeGammon`,
  Mark Tilbury `@marktilbury`, MoneyZG `@MoneyZG`, How Money Works `@HowMoneyWorks`. Real Vision
  and Raoul Pal are used by the channel ids the owner gave (they resolve to `@RealVisionFinance`
  and `@RaoulPalTJM`). `@ECKrown4` returns 404 and a YouTube channel search for "EC Krown" found
  no second channel of his, so it is left out until the owner gives a URL.
- 2026-11-13: Shorts (≤ 180 s, or no duration in the listing) are indexed but not fetched. Why:
  too short to carry a testable rule; YouTube Shorts can be up to 3 minutes.
- 2026-11-13: No date cut-off by default (`start_date` unset): the brief asks for all videos.
- 2026-11-13: Fetch order: each channel's 10 most-viewed and 10 most-recent first (round-robin
  across channels), then everything else newest first. Why: idea mining starts with exactly those.
- 2026-11-13: Pacing 15 s between videos, one fetcher at a time (lock file). Why: the first
  run at 6 s, started straight after indexing all 12 channels (thousands of listing pages), got
  HTTP 429 after 8 videos. At 15 s the ~10.4k pending videos take ~2 days in the background.
  Index and fetch should not run back to back; `scripts/harvest-bg.sh --no-index` fetches only.
- 2026-11-13: HTTP 429 counts as a bot check (halt + stop file). Why: it is YouTube telling an
  automated client to back off; the owner's rule is to stop, not to push through.
- 2026-11-13: A bot check ("sign in to confirm you're not a bot", HTTP 429) halts the fetch and
  leaves `STOPPED-bot-check.txt`; fetch refuses until a human deletes it. Age-gated videos also
  say "sign in to confirm (your age)" and are classed `unavailable` instead. Why: owner rule, no
  workarounds.
- 2026-11-13: Test fixtures are synthetic. Why: real transcripts are copyrighted and stay local.
