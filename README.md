# yt-harvest

Farm YouTube channels for ideas: fetch and cache transcripts, filter by topic, hand them to agents to read

Made from [grimsverk-template](https://github.com/GrimsVerk/grimsverk-template).
Agents: start with `AGENTS.md`.

## Use

```sh
cp local.toml.example local.toml   # set data_root (default ~/data/yt-harvest)
uv run yt-harvest index            # list every channel in config.toml
uv run yt-harvest fetch            # cache captions (picks first, then newest first)
scripts/harvest-bg.sh              # or: index + fetch detached, log in <data_root>/harvest.log
uv run yt-harvest status           # progress per channel
uv run yt-harvest picks            # most-viewed and most-recent per channel
uv run yt-harvest text VIDEO_ID    # read one transcript
```

Transcripts and index files are copyrighted material and stay in the data root, never in git.

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
