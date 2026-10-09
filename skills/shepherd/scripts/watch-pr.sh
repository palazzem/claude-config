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
# watermark, every other line an event that wakes the session. Every event
# carries pr, the number of the PR it happened on:
#   {"event":"COMMENT","pr":…,"url":…,"login":…,"assoc":…,"at":…}          unmarked PR conversation comment
#   {"event":"REVIEW","pr":…,"url":…,"login":…,"assoc":…,"at":…,"state":…}  unmarked submitted review, body-less approvals included
#   {"event":"THREAD_REPLY","pr":…,"url":…,"login":…,"assoc":…,"at":…}     unmarked review-thread comment
#   {"event":"MERGED","pr":…} | {"event":"CLOSED","pr":…}                    the PR reached a terminal; no other event prints for that pass
#   {"event":"BEHIND","pr":…} | {"event":"DIRTY","pr":…}                     merge readiness drifted (base moved / conflicts)
#   {"event":"CI_FAILED","pr":…}                                             a check on the PR head failed or was cancelled
#   {"comment":…,"review":…,"reply":…,"merge":…,"ci":…,"state":…}           the watermark: newest updatedAt per activity
#                                                                            surface, merge state, CI state, PR state
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
# One GraphQL request per pass reads every surface: query.graphql is the
# selection read on one PR, a fragment, and the script generates the operation
# around it — an aliased pullRequest carrying the fragment and its own
# base-to-head comparison. Watermark and events come from the same response, and
# nothing prints unless the alias is non-null and the whole response parsed, so
# a pass is never partial. The read covers the last 50
# comments, reviews, and threads (20 comments each) and 100 checks. jq/pass.jq
# is the pass — one run of it yields every line — over the definitions in
# jq/lib.jq.
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

# The operation that reads the PRs given: one aliased pullRequest each, around
# the fragment in query.graphql. The numbers are digits only, checked on entry.
request() {
  local n reads=""
  for n in "$@"; do
    reads+="pr$n: pullRequest(number: $n) { ...pr baseRef { compare(headRef: \"refs/pull/$n/head\") { behindBy } } } "
  done
  printf 'query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { %s} }\n%s\n' \
    "$reads" "$(cat "$DIR/query.graphql")"
}

fetch() {
  gh api graphql -F owner='{owner}' -F name='{repo}' -f query="$(request "$@")" \
    | jq -e '.data.repository | select(. != null and all(.[]; . != null))'
}

# One pass over a response, left in out: the event lines, then the watermark.
# Activity fires when newer than armed, drift and CI when they differ from last.
# Fails when the response did not parse.
pass() {
  out=$(jq -c -L "$DIR/jq" --arg epoch "$EPOCH" --arg marker "$MARKER" \
    --argjson armed "$armed" --argjson last "$last" -f "$DIR/jq/pass.jq" <<<"$1")
}

case "$cmd" in
  baseline)
    [[ $# -eq 2 ]] || usage
    armed='{}'
    last='{}'
    if ! { p=$(fetch "$pr") && pass "$p"; }; then
      echo "watch-pr: read failed; run it again" >&2
      exit 1
    fi
    printf '%s\n' "$out"
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

jq -e '[.comment, .review, .reply, .merge, .ci] | all(type == "string")' <<<"$3" >/dev/null 2>&1 || {
  echo "watch-pr: malformed watermark: $3" >&2
  exit 2
}
armed=$3
last=$3
echo "watch-pr: pr=$pr watermark=$3" >&2

failures=0
while :; do
  if p=$(fetch "$pr") && pass "$p"; then
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
  if [[ "$out" == *$'\n'* ]]; then
    printf '%s\n' "$out"
    exit 0
  fi
  last=$out
  sleep "$INTERVAL"
done
