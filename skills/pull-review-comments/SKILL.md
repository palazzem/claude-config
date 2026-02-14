---
name: pull-review-comments
description: Use when a GitHub PR exists for the current branch and you need to fetch and address unresolved review comments - pulls threads from GitHub, applies receiving-code-review philosophy, replies in threads
---

# Pull Review Comments

## Overview

Fetch unresolved GitHub PR review threads via a subagent, then address each
thread as a discrete task. The subagent handles all GitHub API interaction
and writes results to a file. The main agent reads the file and fixes code.

**Core principle:** Subagent fetches. Main agent fixes. File persists across
context compaction.

## Process

### Step 1: Pre-flight Checks

Run these checks before anything else. **If any check fails, STOP and tell
the user.**

1. `gh pr view` — if fails, say: "No PR on this branch. Run /push-pr first."
   Stop.
2. `gh pr view --json reviewDecision -q '.reviewDecision'` — if APPROVED,
   proceed to Step 2 (still need to check for unresolved threads).

### Step 2: Dispatch Fetching Subagent

Dispatch a single subagent (Task tool, `general-purpose` type) with the
following instructions:

> **Subagent task:**
>
> 1. Derive owner, repo name, and PR number:
>    ```bash
>    OWNER=$(gh repo view --json owner -q '.owner.login')
>    REPO=$(gh repo view --json name -q '.name')
>    PR_NUMBER=$(gh pr view --json number -q '.number')
>    PR_URL=$(gh pr view --json url -q '.url')
>    BRANCH=$(git branch --show-current)
>    DECISION=$(gh pr view --json reviewDecision -q '.reviewDecision')
>    ```
>
> 2. Fetch unresolved review threads via GraphQL:
>    ```bash
>    gh api graphql -f query='
>      query($owner: String!, $repo: String!, $pr: Int!) {
>        repository(owner: $owner, name: $repo) {
>          pullRequest(number: $pr) {
>            reviewThreads(first: 100) {
>              nodes {
>                isResolved
>                id
>                comments(first: 10) {
>                  nodes {
>                    id
>                    body
>                    path
>                    line
>                    startLine
>                    author { login }
>                  }
>                }
>              }
>            }
>          }
>        }
>      }
>    ' -f owner="$OWNER" -f repo="$REPO" -F pr="$PR_NUMBER"
>    ```
>
>    If GraphQL fails, fall back to REST:
>    ```bash
>    gh api repos/$OWNER/$REPO/pulls/$PR_NUMBER/comments
>    ```
>
> 3. Filter to threads where `isResolved == false`.
>
> 4. Create directory `~/.claude/reviews/` if it doesn't exist.
>
> 5. Write results to `~/.claude/reviews/$OWNER-$REPO-$PR_NUMBER.md`
>    (overwrite if exists) in this format:
>
>    ```markdown
>    # PR Review: <owner>/<repo>#<number>
>
>    **URL:** <pr_url>
>    **Branch:** <branch>
>    **Review decision:** <decision>
>
>    ## Unresolved Threads
>
>    ### Thread 1
>    - **Thread ID:** <graphql_thread_id>
>    - **File:** <path>
>    - **Lines:** <startLine>-<line>
>
>    **@author:**
>    > Full comment body
>
>    ---
>    ```
>
>    If multiple comments exist in a thread, list them all in order.
>    If zero unresolved threads, write the header with
>    "No unresolved threads." under ## Unresolved Threads.
>
> 6. Return the file path and the count of unresolved threads.

### Step 3: Check Results

Read the file the subagent wrote.

- If zero unresolved threads AND review decision is APPROVED (or empty):
  print **"PR approved. No unresolved threads."** Stop.
- If zero unresolved threads AND review decision is CHANGES_REQUESTED:
  print **"No unresolved comment threads, but changes were requested.
  Check the PR reviews for top-level feedback."** Stop.
- Otherwise: proceed to Step 4.

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

- No PR on branch → tell user, suggest `/push-pr`
- GraphQL fails → subagent falls back to REST
- Zero threads + approved → "PR approved." Stop.
- Zero threads + changes requested → inform user of top-level feedback
- Owner/repo/PR number always derived dynamically, never hardcoded
- Review file at `~/.claude/reviews/<owner>-<repo>-<pr>.md` — supports
  multiple repos, worktrees, multi-agent setups

## Red Flags

- Do NOT auto-merge the PR
- Do NOT skip threads because they "look trivial"
- Do NOT implement suggestions without verifying against the codebase
- Do NOT continue to other tasks after pushing — stop and wait
- Do NOT hardcode owner, repo, or PR number anywhere
