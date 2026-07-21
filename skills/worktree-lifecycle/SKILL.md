---
name: worktree-lifecycle
description: Internal agent-facing skill for tearing down a PR's isolated worktree and branches after the PR reaches a terminal state (merged or closed without merge), and syncing the local base ref. Used by the builder in Phase 3 on merge or close, and by the implement chain's main agent when no builder exists for the PR.
---

# Guarded Worktree Teardown

Teardown is destructive only when the work provably lives elsewhere. A merged PR's worktree and branches are disposable copies of history that now sits on the base branch; a PR closed without merge is the opposite - its commits exist nowhere else, and deleting them destroys the work. The PR state gates everything: verify it first, then follow the matching path and no other.

## Rules

1. Derive every fact at runtime - never assume repo, branch, or path names:
   ```bash
   STATE=$(gh pr view <n> --json state -q .state)
   BRANCH=$(gh pr view <n> --json headRefName -q .headRefName)
   BASE=$(gh pr view <n> --json baseRefName -q .baseRefName)
   git worktree list --porcelain
   ```
   In the `--porcelain` output the first `worktree <path>` entry is the main checkout (`MAIN`); the PR's worktree (`WT`) is the entry carrying the line `branch refs/heads/$BRANCH`.
2. Every command runs from the main checkout - `git -C "$MAIN" ...` with absolute paths - never from inside the worktree being removed. You cannot remove the directory you are standing in, and agent bash calls do not share a persistent cwd, so an ambient current directory is never reliable anyway.
3. Gate on `$STATE` before any destructive step. `MERGED` and `CLOSED` have different procedures; any other value aborts.

## MERGED path

Destructive steps are permitted only here - the gh-verified `MERGED` state is the proof that the work is safe on the base branch.

1. Remove the worktree:
   ```bash
   git -C "$MAIN" worktree remove "$WT"
   ```
   If it refuses because the worktree is dirty, `--force` is permitted on this path only: the work is merged, so anything left in the tree is scratch and disposable.
2. Delete the local branch:
   ```bash
   git -C "$MAIN" branch -D "$BRANCH"
   ```
   `-D`, not `-d`, and only after the gh-verified `MERGED` state: after a squash or rebase merge the branch's commits are not ancestors of the base, so `-d` refuses even though the work is merged. The gh check is the merge verification; the flag choice depends on it.
3. Delete the remote branch:
   ```bash
   git -C "$MAIN" push origin --delete "$BRANCH"
   ```
   Treat "remote ref does not exist" as success - GitHub's auto-delete of head branches may have already removed it.
4. Prune the stale remote-tracking ref:
   ```bash
   git -C "$MAIN" fetch --prune
   ```
   NEVER `git pull`: the main checkout is the user's checkout and may be on any branch with uncommitted work.
5. Sync the local base ref:
   ```bash
   git -C "$MAIN" fetch origin "$BASE:$BASE"
   ```
   Only when the base branch is not checked out in any worktree (no `branch refs/heads/$BASE` line in the `--porcelain` output) - the fast-forward refuses otherwise. If the user's checkout is on the base branch, do not touch their tree; report that the base needs a manual pull instead.

## CLOSED-without-merge path

Preservation mode. The branch commits exist nowhere else; destroying them loses the work. Never delete the local branch, never delete the remote branch, never `--force` the worktree removal.

1. Remove the worktree only if it is clean:
   ```bash
   git -C "$MAIN" worktree remove "$WT"
   ```
   If it refuses because the worktree is dirty, leave it in place - the uncommitted changes may be the only copy of that work.
2. Prune safely:
   ```bash
   git -C "$MAIN" fetch --prune
   ```
3. Report what was preserved and where - the branch name, and the worktree path if it was kept - so the user can decide what to do with the unmerged work.

## Any other state

`OPEN`, or a state lookup failure: abort and report. Teardown does not apply to a live PR, and a failed lookup means the terminal state is unverified - no destructive step may run on an assumption.

## Failure modes

| Symptom | Cause | Recovery |
|---|---|---|
| `worktree remove` refuses (dirty worktree) | Uncommitted or untracked files in the worktree | MERGED path: retry with `--force`. CLOSED path: leave the worktree in place and report its path |
| `remote ref does not exist` on `push origin --delete` | GitHub auto-delete already removed the head branch | Treat as success and continue |
| `fetch origin <base>:<base>` refuses | The base branch is checked out in some worktree | Skip the sync; if it is the user's checkout, report that the base needs a manual pull |
