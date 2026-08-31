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
# Events — one JSON object per line on stdout; every line wakes the session:
#   {"event":"COMMENT","id":<n>,"login":"<user>"}       unmarked PR conversation comment
#   {"event":"REVIEW","id":<n>,"login":"<user>"}        unmarked review submission, non-empty body
#   {"event":"THREAD_REPLY","id":<n>,"login":"<user>"}  unmarked review-thread / inline comment
#   {"event":"MERGED"} | {"event":"CLOSED"}             the PR reached a terminal
#   {"event":"BEHIND"} | {"event":"DIRTY"}              merge readiness drifted (base moved / conflicts)
#
# Never fires: marked bodies (first line **Claude Harness**); empty-body
# reviews — GitHub wraps every API thread reply in one under our own account,
# and a human's body-less approval lands in the same skip (stderr-logged);
# CI; UNKNOWN merge state. Drift is transition-relative to the watermark in
# watch mode, current-state in --once mode. Diagnostics go to stderr.
#
# A pass prints only after every surface was read in full. A partial pass would
# exit on the surfaces that fired, and the next baseline would then swallow the
# events of the surface that failed. In --once mode an incomplete read exits 1.

set -euo pipefail

MARKER='**Claude Harness**'
INTERVAL="${WATCH_PR_INTERVAL:-30}"

cmd="${1:-}"
pr="${2:-}"
[[ -z "$cmd" || -z "$pr" ]] && {
  echo "usage: watch-pr.sh baseline|watch <pr> ['<watermark>'] [--once]" >&2
  exit 2
}

api() { gh api "repos/{owner}/{repo}/$1" --paginate; }
max_id() { jq -r '.[].id' | sort -n | tail -1; }
event() { printf '{"event":"%s"}\n' "$1"; }

if [[ "$cmd" == "baseline" ]]; then
  view=$(gh pr view "$pr" --json state,mergeStateStatus)
  c=$(api "issues/$pr/comments" | max_id)
  r=$(api "pulls/$pr/reviews" | max_id)
  t=$(api "pulls/$pr/comments" | max_id)
  jq -n --argjson c "${c:-0}" --argjson r "${r:-0}" --argjson t "${t:-0}" \
    --arg merge "$(jq -r '.mergeStateStatus' <<<"$view")" \
    --arg state "$(jq -r '.state' <<<"$view")" \
    '{comment: $c, review: $r, reply: $t, merge: $merge, state: $state}'
  exit 0
fi

[[ "$cmd" != "watch" ]] && { echo "unknown command: $cmd" >&2; exit 2; }
wm="${3:-}"
[[ -z "$wm" ]] && { echo "watch needs the watermark from 'watch-pr.sh baseline'" >&2; exit 2; }
once=false; [[ "${4:-}" == "--once" ]] && once=true

parsed=$(jq -er '"\(.comment|numbers) \(.review|numbers) \(.reply|numbers) \(.merge|strings)"' <<<"$wm" 2>/dev/null) || {
  echo "watch-pr: malformed watermark: $wm" >&2
  exit 2
}
read -r b_comment b_review b_reply b_merge <<<"$parsed"
echo "watch-pr: pr=$pr once=$once baseline=$wm" >&2

# Skip objects are diagnostics for the empty-body-review carve-out; everything
# else is a qualifying event. Returns success iff anything fired.
emit() {
  local any=1 line
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    if [[ "$line" == '{"skip"'* ]]; then
      echo "watch-pr: skipped empty-body review $line" >&2
    else
      printf '%s\n' "$line"
      any=0
    fi
  done
  return $any
}

filter() {
  local surface=$1 baseline=$2 body=$3
  case "$surface" in
    COMMENT|THREAD_REPLY)
      jq -c --arg m "$MARKER" --argjson b "$baseline" --arg e "$surface" '
        .[] | select(.id > $b)
            | select((.body // "" | startswith($m)) | not)
            | {event: $e, id: .id, login: .user.login}' <<<"$body" | emit ;;
    REVIEW)
      jq -c --arg m "$MARKER" --argjson b "$baseline" '
        .[] | select(.id > $b)
            | if (.body // "") == "" then {skip: {id: .id, login: .user.login, state: .state}}
              elif (.body | startswith($m)) then empty
              else {event: "REVIEW", id: .id, login: .user.login} end' <<<"$body" | emit ;;
  esac
}

while :; do
  if ! { view=$(gh pr view "$pr" --json state,mergeStateStatus) \
      && comments=$(api "issues/$pr/comments") \
      && reviews=$(api "pulls/$pr/reviews") \
      && replies=$(api "pulls/$pr/comments"); }; then
    if $once; then
      echo "watch-pr: incomplete read; re-run it before arming" >&2
      exit 1
    fi
    echo "watch-pr: incomplete read; retrying" >&2
    sleep "$INTERVAL"
    continue
  fi

  fired=false
  state=$(jq -r '.state' <<<"$view")
  merge=$(jq -r '.mergeStateStatus' <<<"$view")
  [[ "$state" == "MERGED" ]] && { event MERGED; exit 0; }
  [[ "$state" == "CLOSED" ]] && { event CLOSED; exit 0; }
  if [[ "$merge" == "BEHIND" || "$merge" == "DIRTY" ]]; then
    if $once || [[ "$merge" != "$b_merge" ]]; then
      event "$merge"
      fired=true
    fi
  fi

  filter COMMENT "$b_comment" "$comments" && fired=true
  filter REVIEW "$b_review" "$reviews" && fired=true
  filter THREAD_REPLY "$b_reply" "$replies" && fired=true

  $once && exit 0
  $fired && exit 0
  sleep "$INTERVAL"
done
