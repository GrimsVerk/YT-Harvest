#!/usr/bin/env bash
# Run `index` (all channels) then `fetch`, detached, so it survives the session.
#
#   scripts/harvest-bg.sh            index + fetch
#   scripts/harvest-bg.sh --no-index fetch only (resume)
#
# Log: <data_root>/harvest.log. The fetcher writes its own PID to
# <data_root>/fetch.pid while it runs, and this wrapper's PID goes to
# <data_root>/harvest.pid. Stop it by that PID only:  kill "$(cat <data_root>/harvest.pid)"
# Resumable: cached transcripts are never fetched again.
set -euo pipefail
cd "$(dirname "$0")/.."
bin=.venv/bin/yt-harvest
[ -x "$bin" ] || uv sync
root=$("$bin" where)
mkdir -p "$root"
index=1
[ "${1:-}" = "--no-index" ] && index=0
setsid -f bash -c '
  echo $$ > "$1/harvest.pid"
  {
    echo "=== harvest start $(date -u +%FT%TZ) pid $$"
    if [ "$3" = 1 ]; then "$2" index || echo "index had failures (see above); fetching anyway"; fi
    "$2" fetch
    rc=$?
    echo "=== harvest end $(date -u +%FT%TZ) fetch exit $rc"
  } >> "$1/harvest.log" 2>&1 < /dev/null
  rm -f "$1/harvest.pid"
' _ "$root" "$PWD/$bin" "$index"
echo "started; log: $root/harvest.log"
