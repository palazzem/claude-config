---
name: gh-inline-comment
description: Internal agent-facing command. Use whenever a harness skill or agent must post line-anchored (inline) review comments on a GitHub PR, reply to an existing review thread, or resolve a review thread via gh. Not user-facing; other skills (pr-review for posting, review-triage for thread resolution) invoke this technique instead of reimplementing it.
---

# Inline PR Comments via gh api

`gh pr review` cannot place comments on specific lines — it only supports review-level
approve/comment/request-changes. The REST API can. This skill wraps the working
workaround documented in cli/cli#359 (credit: the technique below was verified and
published there after native support was declined).

## Rules (apply to every mode below)

1. Every comment body posted through this skill MUST begin with the exact line
   `**Harness automated comment**` followed by a blank line, then the content.
   This applies to the review body AND each inline comment body.
2. `commit_id` is always the PR's current HEAD SHA. Fetch it fresh immediately
   before posting — never reuse a SHA cached earlier in the run:
   ```bash
   HEAD_SHA=$(gh pr view <n> --json headRefOid -q .headRefOid)
   ```
3. `line` is a file line number on the given `side` of the diff, not a diff
   position. `side: RIGHT` targets the new file version (added/unchanged lines);
   `side: LEFT` targets deleted lines in the old version.
4. A line can only be commented on if it appears in the PR diff (in the hunk
   context shown by `git diff` / the Files Changed view).

## Mode 1 — Batch review (PREFERRED)

One submitted review carrying all inline comments. Use this whenever posting more
than one comment: atomic, single notification, comments grouped under one review.

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

- `event` is always `"COMMENT"` — the harness never posts approve or
  request-changes reviews.
- Multi-line ranges: add `start_line` + `start_side` (the range start) alongside
  `line` + `side` (the range end). Start must be strictly before end.
- The POST is all-or-nothing: one invalid comment entry fails the whole review
  with HTTP 422. See failure modes below for recovery.

## Mode 2 — Single-comment fallback

Direct comment endpoint, one inline comment per call. Use when posting exactly
one comment, or when salvaging entries after a batch failure.

Single line:

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

Multi-line range:

```bash
gh api repos/{owner}/{repo}/pulls/{n}/comments \
  --method POST \
  -f body='**Harness automated comment**

Finding text.' \
  -f commit_id="$HEAD_SHA" \
  -f path='path/to/file.ts' \
  -F start_line=40 \
  -f start_side='RIGHT' \
  -F line=42 \
  -f side='RIGHT'
```

## Mode 3 — Thread replies

Reply inside an existing review thread (bot threads only — triage never replies
to humans):

```bash
gh api repos/{owner}/{repo}/pulls/{n}/comments/{comment_id}/replies \
  --method POST \
  -f body='**Harness automated comment**

Reply text.'
```

`comment_id` is the numeric `databaseId` of the thread's FIRST comment.

## Mode 4 — Resolving threads

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

Match the target thread by `path` plus the first comment's `databaseId` or body
prefix, then resolve:

```bash
gh api graphql -f query='
  mutation($threadId: ID!) {
    resolveReviewThread(input: {threadId: $threadId}) {
      thread { id isResolved }
    }
  }' -f threadId=<PRRT_node_id>
```

## Failure modes

| Symptom | Cause | Recovery |
|---|---|---|
| 422 `line must be part of the diff` (or `...position is invalid`) | Target line is not in the PR diff | Re-read the diff for that file; anchor to the closest changed line in the same file and say "re: line N" in the body. If the file has no nearby diff line, fall back to a general comment: fold the finding into the review `body` (Mode 1) or post `gh pr comment <n> --body ...` with the bot header. |
| 422 on the batch POST | One or more invalid entries fail the entire review | Parse the error to identify the offending entry; fix its coordinates or demote it to a general comment; retry the batch. If the error does not identify the entry, post the entries individually via Mode 2 — the failures isolate themselves. |
| 422 `commit_id is not part of the pull request` (or comments land as "outdated") | Stale `commit_id` — the branch was pushed after the SHA was fetched | Refetch `HEAD_SHA` with `gh pr view --json headRefOid`, re-validate line coordinates against the new diff, retry. |
| 404 on `/comments/{id}/replies` | `comment_id` is not the thread's first comment, or is a node ID | Use the numeric `databaseId` of the FIRST comment in the thread (from the GraphQL thread listing). |
| GraphQL `resolveReviewThread` errors | Wrong ID type or thread already resolved | Thread IDs are `PRRT_...` node IDs from `reviewThreads`, not comment IDs. Check `isResolved` before mutating; already-resolved is a no-op success, not an error. |

## Ordering discipline

When posting a review round: fetch HEAD SHA → build all coordinates against that
SHA's diff → POST immediately. Minimize the window between fetch and post; if any
other step pushes commits in between, restart from the SHA fetch.
