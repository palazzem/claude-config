#!/usr/bin/env bash
# watch-pr.sh — the shepherd skill's one PR watcher. The first read and the
# armed monitor run the same filter, so they can never disagree.
#
# Usage:
#   watch-pr.sh baseline <number>    once per watch: print everything standing — every
#                                    unmarked comment, review and thread reply, drift,
#                                    CI, or the terminal — then the watermark
#   watch-pr.sh watch '<watermark>'  the monitor: poll every PR the watermark names
#                                    until the first events past it, print them, then
#                                    the watermark of that pass — arm again with it —
#                                    and exit
# <number> is the PR number; the repository is the current checkout (or GH_REPO).
# The watermark is the whole state of a watch, so watch takes it alone.
#
# Every line is one JSON object on stdout; the last line is always the
# watermark, every other line an event that wakes the session. Every event
# carries pr, the number of the PR it happened on:
#   {"event":"COMMENT","pr":…,"url":…,"login":…,"assoc":…,"at":…}          unmarked PR conversation comment
#   {"event":"REVIEW","pr":…,"url":…,"login":…,"assoc":…,"at":…,"state":…}  unmarked submitted review, body-less approvals included
#   {"event":"THREAD_REPLY","pr":…,"url":…,"login":…,"assoc":…,"at":…}     unmarked review-thread comment
#   {"event":"MERGED","pr":…} | {"event":"CLOSED","pr":…}                    the PR reached a terminal; no other event prints for it
#   {"event":"BEHIND","pr":…} | {"event":"DIRTY","pr":…}                     merge readiness drifted (base moved / conflicts)
#   {"event":"CI_FAILED","pr":…}                                             a check on the PR head failed or was cancelled
#   {"<number>":{"comment":…,"review":…,"reply":…,"merge":…,"ci":…,"state":…},…}
#                                    the watermark: one entry per open PR, keyed by its
#                                    number — newest updatedAt per activity surface,
#                                    merge state, CI state, PR state
#
# Each PR's events are computed against its own entry, and a PR with no entry is
# read from the epoch. A PR that reached a terminal prints that event once and
# is left out of the watermark, while the other PRs' events print in the same
# pass; {} is the watermark of a watch that is over, and watch refuses it.
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
# One GraphQL request per pass reads every surface of every PR: query.graphql
# is the selection read on one PR, a fragment, and the script generates the
# operation around it — per PR, an aliased pullRequest carrying the fragment and
# its own base-to-head comparison. Watermark and events come from the same
# response, and nothing prints unless every alias is non-null and the whole
# response parsed, so a pass is never partial, across surfaces or across PRs.
# The read covers the last 50 comments, reviews, and threads (20 comments each)
# and 100 checks of each PR. jq/pass.jq is the pass — one run of it yields every
# line — over the definitions in jq/lib.jq.
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
  echo "usage: watch-pr.sh baseline <number> | watch '<watermark>'" >&2
  exit 2
}

[[ $# -eq 2 ]] || usage
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

# One pass over the PRs that last names, left in out: the event lines, then the
# watermark. Activity fires when newer than a PR's entry in armed, drift and CI
# when they differ from its entry in last. Fails when the read did.
pass() {
  local numbers response
  read -r -a numbers <<<"$(jq -r 'keys_unsorted | join(" ")' <<<"$last")"
  response=$(fetch "${numbers[@]}") || return 1
  out=$(jq -c -L "$DIR/jq" --arg epoch "$EPOCH" --arg marker "$MARKER" \
    --argjson armed "$armed" --argjson last "$last" -f "$DIR/jq/pass.jq" <<<"$response")
}

case "$1" in
  baseline)
    [[ "$2" =~ ^[0-9]+$ ]] || { echo "watch-pr: <number> must be the PR number" >&2; exit 2; }
    armed='{}'
    last="{\"$2\":{}}"
    if ! pass; then
      echo "watch-pr: read failed; run it again" >&2
      exit 1
    fi
    printf '%s\n' "$out"
    exit 0
    ;;
  watch)
    jq -e 'type == "object" and length > 0 and all(to_entries[];
      (.key | test("^[1-9][0-9]*$")) and (.value | type == "object"
        and ([.comment, .review, .reply, .merge, .ci, .state] | all(type == "string"))))' \
      <<<"$2" >/dev/null 2>&1 || {
      echo "watch-pr: malformed watermark: $2" >&2
      exit 2
    }
    armed=$2
    last=$2
    echo "watch-pr: watermark=$2" >&2
    ;;
  *)
    echo "watch-pr: unknown command: $1" >&2
    exit 2
    ;;
esac

failures=0
while :; do
  if pass; then
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
