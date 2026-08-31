#!/usr/bin/env bash
# watch-pr.sh — the shepherd skill's one PR watcher. The pre-arm read and the
# armed monitor both run this filter, so they can never disagree.
#
# Usage:
#   watch-pr.sh baseline <pr>                    print the watermark JSON
#   watch-pr.sh watch <pr> '<watermark>'         poll; print the first
#                                                qualifying events, then exit
#   watch-pr.sh watch <pr> '<watermark>' --once  one pass: print everything
#                                                qualifying right now, then exit
#
# Events (stdout — every line wakes the session):
#   COMMENT <id> <login>        unmarked PR conversation comment
#   REVIEW <id> <login>         unmarked review submission, non-empty body
#   THREAD_REPLY <id> <login>   unmarked review-thread / inline comment
#   MERGED | CLOSED             the PR reached a terminal
#   BEHIND | DIRTY              merge readiness drifted (base moved / conflicts)
#
# Never fires: marked bodies (first line **Claude Harness**); empty-body
# reviews — GitHub wraps every API thread reply in one under our own account,
# and a human's body-less approval lands in the same skip (stderr-logged);
# CI; UNKNOWN merge state. Drift is transition-relative to the watermark in
# watch mode, current-state in --once mode. Diagnostics go to stderr.

set -u  # deliberately not -e: one failed gh call must not kill the watch

MARKER='**Claude Harness**'
INTERVAL=30

cmd="${1:-}"
pr="${2:-}"
[[ -z "$cmd" || -z "$pr" ]] && {
  echo "usage: watch-pr.sh baseline|watch <pr> ['<watermark>'] [--once]" >&2
  exit 2
}

api() { gh api "repos/{owner}/{repo}/$1" --paginate 2>/dev/null; }
max_id() { jq -r '.[].id' | sort -n | tail -1; }

if [[ "$cmd" == "baseline" ]]; then
  view=$(gh pr view "$pr" --json state,mergeStateStatus) || exit 1
  c=$(api "issues/$pr/comments" | max_id)
  r=$(api "pulls/$pr/reviews" | max_id)
  t=$(api "pulls/$pr/comments" | max_id)
  jq -n --argjson c "${c:-0}" --argjson r "${r:-0}" --argjson t "${t:-0}" \
    --arg merge "$(jq -r '.mergeStateStatus' <<<"$view")" \
    --arg state "$(jq -r '.state' <<<"$view")" \
    '{comment: $c, review: $r, reply: $t, merge: $merge, state: $state}'
  exit $?
fi

[[ "$cmd" != "watch" ]] && { echo "unknown command: $cmd" >&2; exit 2; }
wm="${3:-}"
[[ -z "$wm" ]] && { echo "watch needs the watermark from 'watch-pr.sh baseline'" >&2; exit 2; }
once=false; [[ "${4:-}" == "--once" ]] && once=true

b_comment=$(jq -r '.comment' <<<"$wm") || exit 2
b_review=$(jq -r '.review' <<<"$wm")
b_reply=$(jq -r '.reply' <<<"$wm")
b_merge=$(jq -r '.merge' <<<"$wm")
echo "watch-pr: pr=$pr once=$once baseline=$wm" >&2

# SKIP lines are diagnostics for the empty-body-review carve-out; everything
# else is a qualifying event. Returns success iff anything fired.
emit() {
  local any=1 line
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    if [[ "$line" == SKIP* ]]; then
      echo "watch-pr: skipped empty-body review ${line#SKIP }" >&2
    else
      printf '%s\n' "$line"
      any=0
    fi
  done
  return $any
}

while :; do
  fired=false

  view=$(gh pr view "$pr" --json state,mergeStateStatus 2>/dev/null)
  if [[ -n "$view" ]]; then
    state=$(jq -r '.state' <<<"$view")
    merge=$(jq -r '.mergeStateStatus' <<<"$view")
    [[ "$state" == "MERGED" ]] && { echo "MERGED"; exit 0; }
    [[ "$state" == "CLOSED" ]] && { echo "CLOSED"; exit 0; }
    if [[ "$merge" == "BEHIND" || "$merge" == "DIRTY" ]]; then
      if $once || [[ "$merge" != "$b_merge" ]]; then
        echo "$merge"
        fired=true
      fi
    fi
  else
    echo "watch-pr: gh pr view failed; retrying" >&2
  fi

  api "issues/$pr/comments" | jq -r --arg m "$MARKER" --argjson b "$b_comment" '
    .[] | select(.id > $b)
        | select((.body // "" | startswith($m)) | not)
        | "COMMENT \(.id) \(.user.login)"' | emit && fired=true

  api "pulls/$pr/reviews" | jq -r --arg m "$MARKER" --argjson b "$b_review" '
    .[] | select(.id > $b)
        | if (.body // "") == "" then "SKIP \(.id) \(.user.login) \(.state)"
          elif (.body | startswith($m)) then empty
          else "REVIEW \(.id) \(.user.login)" end' | emit && fired=true

  api "pulls/$pr/comments" | jq -r --arg m "$MARKER" --argjson b "$b_reply" '
    .[] | select(.id > $b)
        | select((.body // "" | startswith($m)) | not)
        | "THREAD_REPLY \(.id) \(.user.login)"' | emit && fired=true

  $once && exit 0
  $fired && exit 0
  sleep "$INTERVAL"
done
