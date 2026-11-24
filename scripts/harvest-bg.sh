#!/usr/bin/env bash
# Run `index` (all channels) then `fetch`, detached, so it survives the session.
#
#   scripts/harvest-bg.sh [--channels FILE]             index + fetch
#   scripts/harvest-bg.sh [--channels FILE] --no-index  fetch only (resume)
#
# Without --channels, the list comes from `channels_file` in local.toml.
# Log: <data_root>/harvest.log. The fetcher writes its own PID to
# <data_root>/fetch.pid while it runs, and this wrapper's PID goes to
# <data_root>/harvest.pid. Stop it by that PID only:  kill "$(cat <data_root>/harvest.pid)"
# Resumable: cached transcripts are never fetched again.
set -euo pipefail
index=1
opts=()
while [ $# -gt 0 ]; do
  case "$1" in
    --no-index) index=0; shift ;;
    --channels)
      [ $# -ge 2 ] || { echo "--channels needs a file" >&2; exit 2; }
      opts+=(--channels "$(realpath -- "$2")"); shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
cd "$(dirname "$0")/.."
bin=.venv/bin/yt-harvest
[ -x "$bin" ] || uv sync
# Fail here, not in the detached run, when no channel list is given.
"$bin" "${opts[@]}" channels > /dev/null
root=$("$bin" "${opts[@]}" where)
mkdir -p "$root"
setsid -f bash -c '
  root=$1 bin=$2 index=$3
  shift 3
  echo $$ > "$root/harvest.pid"
  {
    echo "=== harvest start $(date -u +%FT%TZ) pid $$"
    if [ "$index" = 1 ]; then "$bin" "$@" index || echo "index had failures (see above); fetching anyway"; fi
    "$bin" "$@" fetch
    rc=$?
    echo "=== harvest end $(date -u +%FT%TZ) fetch exit $rc"
  } >> "$root/harvest.log" 2>&1 < /dev/null
  rm -f "$root/harvest.pid"
' _ "$root" "$PWD/$bin" "$index" "${opts[@]}"
echo "started; log: $root/harvest.log"
