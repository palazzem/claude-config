#!/usr/bin/env bash
# watch-pr.sh — the shepherd skill's one PR watcher. It watches every open layer
# of the stack a PR belongs to, a PR in no stack being a stack of one. The first
# read and the armed monitor run the same filter, so they can never disagree.
#
# Usage:
#   watch-pr.sh baseline <number>    once per watch: print everything standing on every
#                                    open layer — every unmarked comment, review and
#                                    thread reply, drift, CI, or the terminal — then
#                                    the watermark
#   watch-pr.sh watch '<watermark>'  the monitor: poll every layer until the first
#                                    events past the watermark, print them, then the
#                                    watermark of that pass — arm again with it — and
#                                    exit
# <number> is any PR of the stack; the repository is the current checkout (or
# GH_REPO). The watermark is the whole state of a watch, so watch takes it alone.
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
# The layers of a watch are the PRs its watermark names plus every entry of
# their stack whose PR is open, as GitHub's API reports the stack — the gh-stack
# extension is never called — and an entry with no PR is skipped. Each layer's
# events are computed against its own entry, and a layer with no entry — one
# that joined the stack while armed — is read from the epoch. A layer that
# reached a terminal prints that event once and is left out of the watermark,
# while the other layers' events print in the same pass; nothing else takes a
# layer out.
# Event lines print grouped by layer, bottom first by position in the stack.
# Within a layer: the terminal alone, or else drift, then CI_FAILED, then
# COMMENT, REVIEW, and THREAD_REPLY lines. {} is the watermark of a watch that
# is over, and watch refuses it.
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
# One GraphQL request per pass reads every surface of every layer:
# query.graphql is the selection read on one PR, a fragment, its stack's entries
# included, and the script generates the operation around it — per layer, an
# aliased pullRequest carrying the fragment and its own base-to-head comparison.
# When the entries name an open PR the request did not read, the pass reads once
# more, with the PRs it read and the ones named, before printing: baseline on a
# stack is two requests, a steady pass one. Watermark and events come from the
# same response, and nothing prints unless every alias is non-null and the whole
# response parsed, so a pass is never partial, across surfaces or across layers.
# The read covers the last 50 comments, reviews, and threads (20 comments each)
# and 100 checks of each layer, and 100 entries of a stack. jq/pass.jq is the
# pass — one run of it yields every line — over the definitions in jq/lib.jq;
# jq/layers.jq is the set of layers a response names, when it is wider than the
# one read.
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
# the fragment in query.graphql. Fails on a number that is not digits only.
request() {
  local n reads=""
  for n in "$@"; do
    [[ "$n" =~ ^[0-9]+$ ]] || return 1
    reads+="pr$n: pullRequest(number: $n) { ...pr baseRef { compare(headRef: \"refs/pull/$n/head\") { behindBy } } } "
  done
  printf 'query($owner: String!, $name: String!) { repository(owner: $owner, name: $name) { %s} }\n%s\n' \
    "$reads" "$(cat "$DIR/query.graphql")"
}

fetch() {
  local query
  query=$(request "$@") || return 1
  gh api graphql -F owner='{owner}' -F name='{repo}' -f query="$query" \
    | jq -e '.data.repository | select(. != null and all(.[]; . != null))'
}

# One pass over the layers of the PRs that last names, left in out: the event
# lines, then the watermark. Activity fires when newer than a layer's entry in
# armed, drift and CI when they differ from its entry in last. Fails when a read
# did.
pass() {
  local numbers wider response
  read -r -a numbers <<<"$(jq -r 'keys_unsorted | join(" ")' <<<"$last")"
  response=$(fetch "${numbers[@]}") || return 1
  wider=$(jq -r -f "$DIR/jq/layers.jq" <<<"$response") || return 1
  if [[ -n "$wider" ]]; then
    read -r -a numbers <<<"$wider"
    response=$(fetch "${numbers[@]}") || return 1
  fi
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
    jq -es 'length == 1 and (.[0] | type == "object" and length > 0 and all(to_entries[];
      (.key | test("\\A[1-9][0-9]*\\z")) and (.value | type == "object"
        and ([.comment, .review, .reply, .merge, .ci, .state] | all(type == "string")))))' \
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
