# Vision: yt-harvest

What matters when two reasonable choices disagree. Not requirements (those are in `DESIGN.md`).
Drafted by an agent from the Chief of Staff's brief (2026-11-13); the owner may change it.

## What this is for

Turn chosen YouTube channels into a local, searchable pile of transcripts that agents can read
for ideas. First use: trading and investing ideas for GrimsTrade (a paper-trading agent), mined
from 12 finance channels. Transcripts are inspiration, not a product.

## Priorities, in order

1. Respect YouTube and the creators: captions only (no audio, no speech-to-text), polite pacing,
   and stop at the first bot check. Never cookies, proxies, fake User-Agents or other workarounds.
2. Copyright: transcripts and title-bearing index files stay local, never in git. Only short ideas
   in our own words, with the video id as source, may be committed.
3. Nothing silently lost: every listed video gets a record with a reason; every failure lands in
   the ledger.
4. Resumable from any point and any computer: a cache that is never refetched, paths from config.
5. Simple, offline-tested code over features.

## Not doing

- No `claude -p` or model SDK calls in this repo. Agents read the transcripts themselves.
- No audio download, no transcription, no comments or community posts.
- No accounts, keys or payments.
