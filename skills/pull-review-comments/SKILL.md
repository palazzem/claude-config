---
name: pull-review-comments
description: Use when a GitHub PR exists for the current branch and you need to fetch and address unresolved review comments - pulls threads from GitHub, applies receiving-code-review philosophy, replies in threads
---

# Pull Review Comments

## Overview

Fetch unresolved GitHub PR review threads, present them in a table, then
address each thread as a discrete task.

**Core principle:** Fetch, present, fix. No intermediate files.

## Process

### Step 1: Pre-flight Checks

Run these checks before anything else. **If any check fails, STOP and tell
the user.**

1. `gh pr view` — if fails, say: "No PR on this branch. Run /push-pr first."
   Stop.
2. `gh pr view --json reviewDecision -q '.reviewDecision'` — if APPROVED,
   proceed to Step 2 (still need to check for unresolved threads).

### Step 2: Fetch Review Threads

Get all PR metadata in a single call:

```bash
gh pr view --json number,url,reviewDecision,headRefName
```

Parse from the result:
- **PR number** from `number`
- **PR URL** from `url`
- **Branch** from `headRefName`
- **Review decision** from `reviewDecision`
- **Owner and repo** from `url` (e.g. `https://github.com/owner/repo/pull/123`)

Then fetch unresolved review threads via GraphQL:

```bash
gh api graphql -f query='
  query($owner: String!, $repo: String!, $pr: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $pr) {
        reviewThreads(first: 100) {
          nodes {
            isResolved
            id
            comments(first: 100) {
              nodes {
                id
                body
                path
                line
                startLine
                author { login }
              }
            }
          }
        }
      }
    }
  }
' -f owner="$OWNER" -f repo="$REPO" -F pr="$PR_NUMBER"
```

Filter to threads where `isResolved == false`.

### Step 3: Present Results Table

- If zero unresolved threads AND review decision is APPROVED (or empty):
  print **"PR approved. No unresolved threads."** Stop.
- If zero unresolved threads AND review decision is CHANGES_REQUESTED:
  print **"No unresolved comment threads, but changes were requested.
  Check the PR reviews for top-level feedback."** Stop.
- Otherwise, present this table:

```
**PR:** <owner>/<repo>#<number> (<pr_url>)
**Branch:** <branch>
**Review decision:** <decision>

| # | File | Lines | Author | Comment (truncated) |
|---|------|-------|--------|---------------------|
| 1 | src/foo.py | 42-45 | @reviewer | "Extract this into..." |
| 2 | src/bar.py | 10 | @reviewer | "Missing error handl..." |
| 3 | tests/test_foo.py | 88 | @reviewer | "This test duplicat..." |
```

Truncate comment body to ~40 chars in the table. The full comment is used
when addressing each thread in Step 4.

### Step 4: Address Each Thread

Each unresolved thread is one task. For each thread in order:

1. Read the full comment (file path, line range, body)
2. **Apply /receiving-code-review philosophy:**
   - Verify the suggestion against the actual codebase
   - If technically wrong: push back with reasoning (reply explaining why)
   - If valid: make the code fix
3. Reply in the GitHub thread:
   ```bash
   gh api graphql -f query='
     mutation($threadId: ID!, $body: String!) {
       addPullRequestReviewThreadReply(
         input: {pullRequestReviewThreadId: $threadId, body: $body}
       ) { comment { id } }
     }
   ' -f threadId="<thread_id>" -f body="<explanation of what changed>"
   ```

**REQUIRED BACKGROUND:** You MUST apply superpowers:receiving-code-review
principles when evaluating each comment. Verify before implementing.
Push back with technical reasoning if wrong.

### Step 5: Commit, Push, Report

After all threads are addressed:

1. Commit: `git add -A && git commit -m "fix: address review feedback"`
2. Push: `git push`
3. Print: **"Review feedback addressed and pushed. Re-review on GitHub,
   then run /pull-review-comments again."**
4. **Stop. Do not continue to any next task.**

## Edge Cases

- No PR on branch -> tell user, suggest `/push-pr`
- Zero threads + approved -> "PR approved." Stop.
- Zero threads + changes requested -> inform user of top-level feedback
- Owner/repo/PR number always derived dynamically, never hardcoded

## Red Flags

- Do NOT auto-merge the PR
- Do NOT skip threads because they "look trivial"
- Do NOT implement suggestions without verifying against the codebase
- Do NOT continue to other tasks after pushing — stop and wait
- Do NOT hardcode owner, repo, or PR number anywhere
- Do NOT write results to a file — always present directly in conversation
