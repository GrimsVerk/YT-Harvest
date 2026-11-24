# Vision: yt-harvest

What matters when two reasonable choices disagree. Not requirements (those are in `DESIGN.md`).
Drafted by an agent from the Chief of Staff's brief (2026-11-13); the owner may change it.

## What this is for

Turn chosen YouTube channels into a local, searchable pile of transcripts that agents can read
for ideas. A general tool: whoever uses it supplies the channel list (and topic words) from their
own project; this repo holds no user's list and no user's ideas. Transcripts are inspiration, not
a product.

## Priorities, in order

1. Respect YouTube and the creators: captions only (no audio, no speech-to-text), polite pacing,
   and stop at the first bot check. Never cookies, proxies, fake User-Agents or other workarounds.
2. Copyright: transcripts and title-bearing index files stay local, never in git. Only short ideas
   in our own words, with the video id as source, may be committed, and only in the project that
   uses them.
3. General and private: no user-specific channel lists, topic words or ideas in this repo. A list
   of followed channels says whose sources they are; it stays with its user.
4. Nothing silently lost: every listed video gets a record with a reason; every failure lands in
   the ledger.
5. Resumable from any point and any computer: a cache that is never refetched, paths from config.
6. Simple, offline-tested code over features.

## Not doing

- No `claude -p` or model SDK calls in this repo. Agents read the transcripts themselves.
- No audio download, no transcription, no comments or community posts.
- No accounts, keys or payments.
