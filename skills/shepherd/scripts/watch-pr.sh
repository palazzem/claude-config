#!/usr/bin/env bash
# watch-pr.sh — the shepherd skill's one PR watcher. The pre-arm read and the
# armed monitor both run this filter, so they can never disagree.
#
# Usage:
#   watch-pr.sh baseline <number>                    print the watermark JSON
#   watch-pr.sh watch <number> '<watermark>'         poll; print the first
#                                                    qualifying events, then exit
#   watch-pr.sh watch <number> '<watermark>' --once  one pass: print everything
#                                                    qualifying right now, then exit
# <number> is the PR number; the repository is the current checkout (or GH_REPO).
#
# Events — one JSON object per line on stdout; every line wakes the session:
#   {"event":"COMMENT","url":…,"login":…,"assoc":…,"at":…}          unmarked PR conversation comment
#   {"event":"REVIEW","url":…,"login":…,"assoc":…,"at":…,"state":…}  unmarked submitted review, body-less approvals included
#   {"event":"THREAD_REPLY","url":…,"login":…,"assoc":…,"at":…}     unmarked review-thread comment
#   {"event":"MERGED"} | {"event":"CLOSED"}                           the PR reached a terminal; nothing else prints for that pass
#   {"event":"BEHIND"} | {"event":"DIRTY"}                            merge readiness drifted (base moved / conflicts)
#   {"event":"CI_FAILED"}                                             a check on the PR head failed or was cancelled
#
# Never fires: marked bodies (first line <!-- claude -->, leading whitespace
# ignored); body-less COMMENTED reviews — GitHub wraps every API thread reply in
# one under our own account; pending reviews; UNKNOWN merge state; pending or
# passing checks. Surfaces watermark on updatedAt, so an edited comment fires
# again. Drift and CI fire on a transition from the last observed state
# (initially the watermark) in watch mode, on current state in --once mode.
# Diagnostics go to stderr.
#
# One GraphQL request per pass (query.graphql) reads every surface, and nothing
# prints unless the whole response parsed, so a pass is never partial. The read
# covers the last 50 comments, reviews, and threads (20 comments each) and 100
# checks. The filters live in jq/.
#
# Exit codes: 0 events printed (watch) or read complete (--once); 1 read
# incomplete (--once) or MAX_FAILURES consecutive failed reads (watch);
# 2 invocation error.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKER='<!-- claude -->'
EPOCH='1970-01-01T00:00:00Z'
INTERVAL="${WATCH_PR_INTERVAL:-30}"
MAX_FAILURES="${WATCH_PR_MAX_FAILURES:-20}"

cmd="${1:-}"
pr="${2:-}"
[[ -z "$cmd" || -z "$pr" ]] && {
  echo "usage: watch-pr.sh baseline|watch <number> ['<watermark>'] [--once]" >&2
  exit 2
}
[[ "$pr" =~ ^[0-9]+$ ]] || { echo "watch-pr: <number> must be the PR number" >&2; exit 2; }
[[ "$INTERVAL" =~ ^[0-9]+$ && "$MAX_FAILURES" =~ ^[0-9]+$ ]] || {
  echo "watch-pr: WATCH_PR_INTERVAL and WATCH_PR_MAX_FAILURES must be integers" >&2
  exit 2
}

fetch() {
  gh api graphql -F owner='{owner}' -F name='{repo}' -F pr="$pr" -f query="$(cat "$DIR/query.graphql")" \
    | jq -e '.data.repository.pullRequest | select(. != null)'
}
filter() {
  jq -L "$DIR/jq" --arg epoch "$EPOCH" --arg marker "$MARKER" "$@"
}
event() { printf '{"event":"%s"}\n' "$1"; }

if [[ "$cmd" == "baseline" ]]; then
  p=$(fetch) || { echo "watch-pr: read failed" >&2; exit 1; }
  filter -c -f "$DIR/jq/baseline.jq" <<<"$p"
  exit 0
fi

[[ "$cmd" != "watch" ]] && { echo "watch-pr: unknown command: $cmd" >&2; exit 2; }
wm="${3:-}"
[[ -z "$wm" ]] && { echo "watch-pr: watch needs the watermark from 'watch-pr.sh baseline'" >&2; exit 2; }
once=false; [[ "${4:-}" == "--once" ]] && once=true

parsed=$(jq -er '"\(.comment|strings) \(.review|strings) \(.reply|strings) \(.merge|strings) \(.ci|strings)"' <<<"$wm" 2>/dev/null) || {
  echo "watch-pr: malformed watermark: $wm" >&2
  exit 2
}
read -r b_comment b_review b_reply b_merge b_ci <<<"$parsed"
echo "watch-pr: pr=$pr once=$once baseline=$wm" >&2

last_merge=$b_merge
last_ci=$b_ci
failures=0
while :; do
  if p=$(fetch) \
     && parsed=$(filter -r -f "$DIR/jq/pass.jq" <<<"$p") \
     && events=$(filter -c --arg comment "$b_comment" --arg review "$b_review" --arg reply "$b_reply" -f "$DIR/jq/events.jq" <<<"$p"); then
    failures=0
  else
    if $once; then
      echo "watch-pr: incomplete read; re-run it before arming" >&2
      exit 1
    fi
    failures=$((failures + 1))
    if (( failures >= MAX_FAILURES )); then
      echo "watch-pr: $failures consecutive failed reads; giving up" >&2
      exit 1
    fi
    echo "watch-pr: incomplete read ($failures/$MAX_FAILURES); retrying" >&2
    sleep "$INTERVAL"
    continue
  fi

  read -r state merge ci <<<"$parsed"
  [[ "$state" == "MERGED" ]] && { event MERGED; exit 0; }
  [[ "$state" == "CLOSED" ]] && { event CLOSED; exit 0; }

  out=""
  if [[ "$merge" == "BEHIND" || "$merge" == "DIRTY" ]] && { $once || [[ "$merge" != "$last_merge" ]]; }; then
    out+="$(event "$merge")"$'\n'
  fi
  if [[ "$ci" == "FAILED" ]] && { $once || [[ "$ci" != "$last_ci" ]]; }; then
    out+="$(event CI_FAILED)"$'\n'
  fi
  out+="$events"
  last_merge=$merge
  last_ci=$ci

  if [[ -n "${out//$'\n'/}" ]]; then
    printf '%s\n' "${out%$'\n'}"
    exit 0
  fi
  $once && exit 0
  sleep "$INTERVAL"
done
