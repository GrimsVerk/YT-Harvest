# yt-harvest

Farm YouTube channels for ideas: fetch and cache transcripts, filter by topic, hand them to agents to read

Made from [grimsverk-template](https://github.com/GrimsVerk/grimsverk-template).
Agents: start with `AGENTS.md`.

## Use

```sh
cp local.toml.example local.toml   # set data_root (default ~/data/yt-harvest) and channels_file
# Your channel list: copy channels.example.toml to a file of your own (outside this repo),
# then point channels_file in local.toml at it, or pass --channels FILE to every command.
uv run yt-harvest channels         # check which channels are configured
uv run yt-harvest index            # list every channel's uploads
uv run yt-harvest fetch            # cache captions (picks first, then newest first)
scripts/harvest-bg.sh              # or: index + fetch detached (also takes --channels FILE)
uv run yt-harvest status           # progress per channel
uv run yt-harvest picks            # most-viewed and most-recent per channel
uv run yt-harvest text VIDEO_ID    # read one transcript
```

Transcripts and index files are copyrighted material and stay in the data root, never in git.
Channel lists and the ideas mined from them belong to the project that uses the tool, not here.

## Develop

```sh
uv sync                     # install (creates .venv and uv.lock; commit uv.lock)
uv run pytest               # tests
uv run pre-commit install   # checks on every commit
```

## Set up GitHub (once)

After the first commit, the repo owner (admin) runs `scripts/setup-github.sh --public`: it creates the repo, pushes, and sets merge settings and `main` protection.
Pick a license first; this template adds none.

## Template updates

`scripts/update-from-template.sh` pulls in the latest template on a branch and opens a PR.
