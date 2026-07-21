---
name: github-comment
description: Internal agent-facing library for GitHub PR interaction via gh - post line-anchored (inline) review comments and batched reviews, reply to and resolve review threads, and arm a PR monitor that fires on comments, submitted reviews, CI results, pushes, and merge. Other skills and agents invoke these techniques instead of reimplementing them.
---

# GitHub PR Comments and Monitoring via gh

`gh pr review` cannot place comments on specific lines - it only supports review-level approve/comment/request-changes. The REST API can. Modes 1-4 wrap the working workaround documented in cli/cli#359; Mode 5 arms the PR monitor.

## Rules (apply to every posting mode)

1. Every comment body posted through this skill begins with the exact line `**Harness automated comment**` followed by a blank line, then the content. This applies to the review body and each inline comment body. The header is how any later reader distinguishes machine posts from human ones - a thread where any comment lacks it (and is not from a known bot account) is a human thread.
2. `commit_id` is always the PR's current HEAD SHA. Fetch it fresh immediately before posting - never reuse a SHA cached earlier in the run:
   ```bash
   HEAD_SHA=$(gh pr view <n> --json headRefOid -q .headRefOid)
   ```
3. `line` is a file line number on the given `side` of the diff, not a diff position. `side: RIGHT` targets the new file version (added/unchanged lines); `side: LEFT` targets deleted lines in the old version.
4. A line can only be commented on if it appears in the PR diff (in the hunk context shown by `git diff` / the Files Changed view).
5. No emoji anywhere; the review event is always `COMMENT`.

## Mode 1 - Batch review (preferred)

One submitted review carrying all inline comments. Use this whenever posting more than one comment: atomic, single notification, comments grouped under one review.

Write the payload to a JSON file (use the scratchpad directory), then POST:

```bash
gh api repos/{owner}/{repo}/pulls/{n}/reviews \
  --method POST \
  --input review.json
```

`review.json`:

```json
{
  "commit_id": "<HEAD_SHA>",
  "event": "COMMENT",
  "body": "**Harness automated comment**\n\nReview summary body.",
  "comments": [
    {
      "path": "path/to/file.ts",
      "line": 42,
      "side": "RIGHT",
      "body": "**Harness automated comment**\n\nSingle-line finding."
    },
    {
      "path": "path/to/other.ts",
      "start_line": 40,
      "start_side": "RIGHT",
      "line": 45,
      "side": "RIGHT",
      "body": "**Harness automated comment**\n\nMulti-line finding covering lines 40-45."
    }
  ]
}
```

- Multi-line ranges: add `start_line` + `start_side` (the range start) alongside `line` + `side` (the range end). Start must be strictly before end.
- The POST is all-or-nothing: one invalid comment entry fails the whole review with HTTP 422. See failure modes below for recovery.

## Mode 2 - Single-comment fallback

Direct comment endpoint, one inline comment per call. Use when posting exactly one comment, or when salvaging entries after a batch failure.

```bash
gh api repos/{owner}/{repo}/pulls/{n}/comments \
  --method POST \
  -f body='**Harness automated comment**

Finding text.' \
  -f commit_id="$HEAD_SHA" \
  -f path='path/to/file.ts' \
  -F line=42 \
  -f side='RIGHT'
```

Multi-line range: add `-F start_line=40 -f start_side='RIGHT'` before `line`/`side`.

## Mode 3 - Thread replies

Reply inside an existing review thread:

```bash
gh api repos/{owner}/{repo}/pulls/{n}/comments/{comment_id}/replies \
  --method POST \
  -f body='**Harness automated comment**

Reply text.'
```

`comment_id` is the numeric `databaseId` of the thread's first comment.

## Mode 4 - Resolving threads

Resolution is GraphQL-only. First list threads to get node IDs:

```bash
gh api graphql -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $number) {
        reviewThreads(first: 100) {
          nodes {
            id
            isResolved
            path
            comments(first: 1) { nodes { databaseId body } }
          }
        }
      }
    }
  }' -f owner=<owner> -f repo=<repo> -F number=<n>
```

Match the target thread by `path` plus the first comment's `databaseId` or body prefix, then resolve:

```bash
gh api graphql -f query='
  mutation($threadId: ID!) {
    resolveReviewThread(input: {threadId: $threadId}) {
      thread { id isResolved }
    }
  }' -f threadId=<PRRT_node_id>
```

Never resolve a thread a human opened or replied in.

## Mode 5 - PR monitor and the wake pattern

Arm one persistent Monitor per watched PR, owned by the main session. The main session owns it on purpose: the watch must outlive any single builder turn - it runs while the builder sits idle between events and must survive the builder's teardown at merge. A subagent *can* receive monitor events (that is verified), so the reason is not a platform limit; whether a builder-owned `Monitor(persistent: true)` would keep delivering across the builder's own dormant turns and past teardown is unverified, so ownership stays with the main session until that is demonstrated. GitHub splits PR activity across separate API objects - issue comments, submitted reviews, review (inline) comments, CI checks, pushes, merge state - and the script must poll all of them: a monitor watching only comments misses a human "Request changes" review entirely.

```bash
Monitor (persistent: true, description: "PR #<n> activity"):

PR=<n>; OWNER=<owner>; REPO=<repo>; prev=""; merge_known=""
while true; do
  issues=$(gh api --paginate "repos/$OWNER/$REPO/issues/$PR/comments?per_page=100" --jq 'map(select(.body | startswith("**Harness automated comment**") | not)) | .[-1].id // empty' 2>/dev/null) || { sleep 60; continue; }
  issues=$(printf '%s' "$issues" | tail -n 1); issues=${issues:-0}
  reviews=$(gh api --paginate "repos/$OWNER/$REPO/pulls/$PR/reviews?per_page=100" --jq '.[-1].id // 0' 2>/dev/null) || { sleep 60; continue; }
  reviews=$(printf '%s' "$reviews" | tail -n 1)
  rcomments=$(gh api --paginate "repos/$OWNER/$REPO/pulls/$PR/comments?per_page=100" --jq 'map(select(.body | startswith("**Harness automated comment**") | not)) | .[-1].id // empty' 2>/dev/null) || { sleep 60; continue; }
  rcomments=$(printf '%s' "$rcomments" | tail -n 1); rcomments=${rcomments:-0}
  line=$(gh pr view "$PR" --repo "$OWNER/$REPO" \
    --json state,headRefOid,mergeStateStatus,statusCheckRollup \
    --jq '[.mergeStateStatus, .state, .headRefOid,
           ([.statusCheckRollup[]? | .conclusion // .state] | sort | join(","))] | join(" ")' \
    2>/dev/null) || { sleep 60; continue; }
  merge=${line%% *}; rest=${line#* }
  if [ "$merge" = UNKNOWN ] && [ -z "$merge_known" ]; then
    sleep 60; continue
  elif [ "$merge" = UNKNOWN ]; then
    merge=$merge_known
  else
    merge_known=$merge
  fi
  cur="$issues|$reviews|$rcomments|$rest|$merge"
  if [ -n "$prev" ] && [ "$cur" != "$prev" ]; then
    echo "PR_UPDATED #$PR"
    case "$cur" in *MERGED*) echo "PR_MERGED #$PR"; exit 0;; *CLOSED*) echo "PR_CLOSED #$PR"; exit 0;; esac
  fi
  prev="$cur"
  sleep 60
done
```

Each fetch goes into its own variable, and any failure (non-zero exit under `2>/dev/null`) skips the whole cycle via `{ sleep 60; continue; }` — a brace group, never a subshell, or `continue` would be a silent no-op. The fingerprint is assembled only after all four fetches succeed, so a state the monitor failed to observe is never compared and an API outage never fabricates an event: during an outage the monitor is simply silent, and detection is delayed by the outage plus up to one poll interval. The three list fetches use `--paginate` and print one id per page; the multi-line output is captured first — so the checked exit status is `gh`'s and not a pipeline's (which would be `tail`'s and would mask a `gh` failure) — and only then reduced with `tail -n 1` to the true last id. The issue-comment and review-comment fetches carry the self-wake guard: `map(select(.body | startswith("**Harness automated comment**") | not))` drops every comment the harness itself posted before taking `.[-1].id`, so the builder's own thread replies and PR comments never move the fingerprint and never wake it — only a human comment does. Those two emit `.[-1].id // empty` per page, so a page with no human comment prints nothing rather than `0`, and `tail -n 1` keeps the last human id instead of letting a trailing page of pure harness posts collapse it to `0`; the final `${var:-0}` supplies `0` only when no page held a human comment. The submitted-reviews fetch keeps `.[-1].id // 0` unfiltered, because during the watch a new submitted review is always a human's. `per_page=100` alone would pin at item 100 once a list grows past one page, and `direction=desc` is not used because the issue-comments endpoint silently ignores it (with `per_page=1` that would pin to the oldest comment).

Mergeability is lazily computed by GitHub and transiently flips to `UNKNOWN`, and every MERGED PR reports `mergeStateStatus: UNKNOWN` permanently — so UNKNOWN is masked with the last known value (`merge_known`), never skipped: skipping on UNKNOWN would silence the monitor forever at exactly the merge event. During an UNKNOWN window the poll still runs, so comments, pushes, and CI changes are still detected, and `.state` flipping to MERGED/CLOSED still changes the fingerprint — the case patterns match on `.state`, which masking never touches. The one exception is a startup UNKNOWN with no known value yet, which skips: bounded startup blindness only.

The line coverage is deliberate: a new human issue comment, a submitted review (human or bot), a new human inline review comment, a CI conclusion change, a push (head SHA), a base-branch conflict (`mergeStateStatus`), and merge/close all change `cur` and emit an event. The self-wake guard keeps the builder's own thread replies and PR comments out of the two comment fetches - they carry the harness header and are filtered - so they never wake it. A push by the builder does still change the head SHA and emits one event, but that is a benign single wake rather than a loop: the builder inspects, sees its own commit already at HEAD with nothing external pending, does nothing, and does not push again without a fresh reason. With the PR author's own token the reviews endpoint also returns PENDING (unsubmitted) reviews, so a wake-up may mean a review was started, not only submitted.

The wake pattern: on any event, the main session's only action is waking the PR's builder agent:

```
SendMessage to: builder-<owner>-<repo>-<branch-slug>
message: "PR updated: PR #<n>"
```

Nothing else - no classification, no fixing, no replying. The builder inspects the PR and decides what the event means. On `PR_MERGED` / `PR_CLOSED` the monitor exits by itself; the wake message lets the builder run its cleanup, and the watch is over.

## Failure modes

| Symptom | Cause | Recovery |
|---|---|---|
| 422 `line must be part of the diff` (or `...position is invalid`) | Target line is not in the PR diff | Re-read the diff for that file; anchor to the closest changed line in the same file and say "re: line N" in the body. If the file has no nearby diff line, fold the finding into the review `body` (Mode 1) or post `gh pr comment <n> --body ...` with the bot header. |
| 422 on the batch POST | One or more invalid entries fail the entire review | Parse the error to identify the offending entry; fix its coordinates or demote it to a general comment; retry the batch. If the error does not identify the entry, post the entries individually via Mode 2 - the failures isolate themselves. |
| 422 `commit_id is not part of the pull request` (or comments land as "outdated") | Stale `commit_id` - the branch was pushed after the SHA was fetched | Refetch `HEAD_SHA`, re-validate line coordinates against the new diff, retry. |
| 404 on `/comments/{id}/replies` | `comment_id` is not the thread's first comment, or is a node ID | Use the numeric `databaseId` of the first comment in the thread (from the GraphQL thread listing). |
| GraphQL `resolveReviewThread` errors | Wrong ID type or thread already resolved | Thread IDs are `PRRT_...` node IDs from `reviewThreads`, not comment IDs. Check `isResolved` before mutating; already-resolved is a no-op success, not an error. |

## Ordering discipline

When posting a review round: fetch HEAD SHA, build all coordinates against that SHA's diff, then POST immediately. Minimize the window between fetch and post; if any other step pushes commits in between, restart from the SHA fetch.
