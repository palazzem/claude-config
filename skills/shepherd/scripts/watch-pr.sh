#!/usr/bin/env bash
# watch-pr.sh — the shepherd skill's one PR watcher. The first read and the
# armed monitor run the same filter, so they can never disagree.
#
# Usage:
#   watch-pr.sh baseline <number>             once per PR per session: print everything
#                                             standing — every unmarked comment, review and
#                                             thread reply, drift, CI, or the terminal — then
#                                             the watermark
#   watch-pr.sh watch <number> '<watermark>'  the monitor: poll until the first events past
#                                             the watermark, print them, then the watermark
#                                             of that pass — arm again with it — and exit
# <number> is the PR number; the repository is the current checkout (or GH_REPO).
#
# Every line is one JSON object on stdout; the last line is always the
# watermark, every other line an event that wakes the session:
#   {"event":"COMMENT","url":…,"login":…,"assoc":…,"at":…}          unmarked PR conversation comment
#   {"event":"REVIEW","url":…,"login":…,"assoc":…,"at":…,"state":…}  unmarked submitted review, body-less approvals included
#   {"event":"THREAD_REPLY","url":…,"login":…,"assoc":…,"at":…}     unmarked review-thread comment
#   {"event":"MERGED"} | {"event":"CLOSED"}                           the PR reached a terminal; no other event prints for that pass
#   {"event":"BEHIND"} | {"event":"DIRTY"}                            merge readiness drifted (base moved / conflicts)
#   {"event":"CI_FAILED"}                                             a check on the PR head failed or was cancelled
#   {"comment":…,"review":…,"reply":…,"merge":…,"ci":…,"state":…}    the watermark: newest updatedAt per activity
#                                                                     surface, merge state, CI state, PR state
#
# Never fires: marked bodies (first line <!-- claude -->, leading whitespace
# ignored); body-less COMMENTED reviews — GitHub wraps every API thread reply in
# one under our own account; pending reviews and their thread comments; UNKNOWN
# merge state; pending or passing checks. Activity is compared on updatedAt, so
# an edited comment fires again. BEHIND is read from the base-to-head comparison
# (refs/pull/<number>/head against the base branch), because mergeStateStatus
# reports it only when the base branch rule requires up-to-date heads. baseline
# reads activity from the epoch and drift and CI from current state; watch fires
# on activity newer than the watermark and on drift or CI that differs from it,
# so a state the session already handled stays quiet until it changes.
# Diagnostics go to stderr.
#
# One GraphQL request per pass (query.graphql) reads every surface; watermark
# and events come from the same response, and nothing prints unless the whole
# response parsed, so a pass is never partial. The read covers the last 50
# comments, reviews, and threads (20 comments each) and 100 checks. The filters
# live in jq/.
#
# Exit codes: 0 printed (baseline: read complete; watch: events); 1 read
# failed (baseline) or MAX_FAILURES consecutive failed reads (watch);
# 2 invocation error.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKER='<!-- claude -->'
EPOCH='1970-01-01T00:00:00Z'
INTERVAL="${WATCH_PR_INTERVAL:-30}"
MAX_FAILURES="${WATCH_PR_MAX_FAILURES:-20}"

usage() {
  echo "usage: watch-pr.sh baseline <number> | watch <number> '<watermark>'" >&2
  exit 2
}

cmd="${1:-}"
pr="${2:-}"
[[ -z "$cmd" || -z "$pr" ]] && usage
[[ "$pr" =~ ^[0-9]+$ ]] || { echo "watch-pr: <number> must be the PR number" >&2; exit 2; }
[[ "$INTERVAL" =~ ^[0-9]+$ && "$MAX_FAILURES" =~ ^[0-9]+$ ]] || {
  echo "watch-pr: WATCH_PR_INTERVAL and WATCH_PR_MAX_FAILURES must be integers" >&2
  exit 2
}

fetch() {
  gh api graphql -F owner='{owner}' -F name='{repo}' -F pr="$pr" -F head="refs/pull/$pr/head" -f query="$(cat "$DIR/query.graphql")" \
    | jq -e '.data.repository.pullRequest | select(. != null)'
}
filter() {
  jq -L "$DIR/jq" --arg epoch "$EPOCH" --arg marker "$MARKER" "$@"
}
event() { printf '{"event":"%s"}\n' "$1"; }

# One pass over a response: the terminal event alone, or drift and CI that
# differ from last_merge/last_ci plus activity newer than b_comment, b_review
# and b_reply. Leaves the event lines in out, the pass watermark in wm, and the
# observed states in last_merge/last_ci. Fails when the response did not parse.
pass() {
  local parsed events state merge ci
  parsed=$(filter -r -f "$DIR/jq/pass.jq" <<<"$1") || return 1
  events=$(filter -c --arg comment "$b_comment" --arg review "$b_review" --arg reply "$b_reply" -f "$DIR/jq/events.jq" <<<"$1") || return 1
  wm=$(filter -c -f "$DIR/jq/baseline.jq" <<<"$1") || return 1
  read -r state merge ci <<<"$parsed"
  out=""
  if [[ "$state" == "MERGED" || "$state" == "CLOSED" ]]; then
    out="$(event "$state")"$'\n'
  else
    if [[ "$merge" == "BEHIND" || "$merge" == "DIRTY" ]] && [[ "$merge" != "$last_merge" ]]; then
      out+="$(event "$merge")"$'\n'
    fi
    if [[ "$ci" == "FAILED" && "$ci" != "$last_ci" ]]; then
      out+="$(event CI_FAILED)"$'\n'
    fi
    if [[ -n "$events" ]]; then
      out+="$events"$'\n'
    fi
  fi
  last_merge=$merge
  last_ci=$ci
}

case "$cmd" in
  baseline)
    [[ $# -eq 2 ]] || usage
    b_comment=$EPOCH; b_review=$EPOCH; b_reply=$EPOCH; last_merge=""; last_ci=""
    if ! { p=$(fetch) && pass "$p"; }; then
      echo "watch-pr: read failed; run it again" >&2
      exit 1
    fi
    printf '%s%s\n' "$out" "$wm"
    exit 0
    ;;
  watch)
    [[ $# -eq 3 ]] || usage
    ;;
  *)
    echo "watch-pr: unknown command: $cmd" >&2
    exit 2
    ;;
esac

parsed=$(jq -er '"\(.comment|strings) \(.review|strings) \(.reply|strings) \(.merge|strings) \(.ci|strings)"' <<<"$3" 2>/dev/null) || {
  echo "watch-pr: malformed watermark: $3" >&2
  exit 2
}
read -r b_comment b_review b_reply last_merge last_ci <<<"$parsed"
echo "watch-pr: pr=$pr watermark=$3" >&2

failures=0
while :; do
  if p=$(fetch) && pass "$p"; then
    failures=0
  else
    failures=$((failures + 1))
    if (( failures >= MAX_FAILURES )); then
      echo "watch-pr: $failures consecutive failed reads; giving up" >&2
      exit 1
    fi
    echo "watch-pr: incomplete read ($failures/$MAX_FAILURES); retrying" >&2
    sleep "$INTERVAL"
    continue
  fi
  if [[ -n "$out" ]]; then
    printf '%s%s\n' "$out" "$wm"
    exit 0
  fi
  sleep "$INTERVAL"
done
