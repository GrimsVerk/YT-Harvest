#!/usr/bin/env bash
# Create this project's GitHub repo (if there is no origin), push, and set it up.
# Run by the repo owner (needs admin), once per repo; safe to re-run.
#
#   scripts/setup-github.sh [--public]     # default: private
#
# Sets: auto-merge off; merge commits and rebase allowed, squash off; delete
# branches after merge; public repos: PRs from collaborators only; a "protect-main"
# ruleset (no deletion, no force-push, PR required with 0 approvals, no required checks).
set -euo pipefail

VISIBILITY=--private
case "${1:-}" in
  --public) VISIBILITY=--public ;;
  "") ;;
  *) echo "usage: $0 [--public]" >&2; exit 2 ;;
esac

cd "$(git rev-parse --show-toplevel)"
command -v gh >/dev/null || { echo "setup-github: install the GitHub CLI (gh) first" >&2; exit 1; }

NOT_ADMIN="setup-github: the owner must run this (needs repo admin). Agents act as GrimsBot, which is not admin.
  Switch with 'gh auth switch', or: GH_TOKEN=\$(gh auth token -u <owner>) $0"

gh auth status >/dev/null 2>&1 || { echo "setup-github: gh is not logged in (gh auth login)" >&2; exit 1; }

if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create "$(basename "$PWD")" "$VISIBILITY" --source=. --push
fi
REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
ADMIN="$(gh api "repos/$REPO" --jq .permissions.admin)"
[[ "$ADMIN" == "true" ]] || { echo "$NOT_ADMIN" >&2; exit 1; }
IS_PRIVATE="$(gh api "repos/$REPO" --jq .private)"

gh api -X PATCH "repos/$REPO" \
  -F allow_auto_merge=false \
  -F allow_squash_merge=false \
  -F allow_rebase_merge=true \
  -F allow_merge_commit=true \
  -F delete_branch_on_merge=true >/dev/null
if [[ "$IS_PRIVATE" == "false" ]]; then
  gh api -X PATCH "repos/$REPO" -f pull_request_creation_policy=collaborators_only >/dev/null
  PRS="collaborators only"
else
  PRS="not applicable (private)"
fi

# One ruleset on the default branch. Update it in place if it exists.
ID="$(gh api "repos/$REPO/rulesets" --jq '.[] | select(.name == "protect-main") | .id')"
BODY='{"name":"protect-main","target":"branch","enforcement":"active",
  "conditions":{"ref_name":{"include":["~DEFAULT_BRANCH"],"exclude":[]}},
  "rules":[{"type":"deletion"},{"type":"non_fast_forward"},
    {"type":"pull_request","parameters":{
      "required_approving_review_count":0,
      "dismiss_stale_reviews_on_push":false,
      "require_code_owner_review":false,
      "require_last_push_approval":false,
      "required_review_thread_resolution":false,
      "allowed_merge_methods":["merge","rebase"]}}]}'
if [[ -n "$ID" ]]; then
  gh api -X PUT "repos/$REPO/rulesets/$ID" --input - <<<"$BODY" >/dev/null
else
  gh api -X POST "repos/$REPO/rulesets" --input - <<<"$BODY" >/dev/null
fi

cat <<SUMMARY
setup-github: $REPO is set up.
  auto-merge:          off
  merge methods:       rebase + merge commit (squash off)
  delete on merge:     on
  PR creation:         $PRS
  ruleset protect-main (default branch): no deletion, no force-push,
    pull request required (0 approvals, no code-owner review), no required checks
SUMMARY
