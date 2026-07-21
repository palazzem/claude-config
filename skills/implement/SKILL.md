---
name: implement
description: Use when the user asks to implement something - "implement X", "implement the brainstorm result", "build this spec". Runs the whole delivery chain without further prompts: spawns one persistent builder that codes and opens a draft PR, runs the review-panel loop, flips the PR open, then watches it to merge. The user is contacted only via the two message types.
argument-hint: "<what to implement> (optional) - a task description or a reference to an approved spec (issue URL or number)"
---

# Implement

Manual entry, automatic chain: draft PR, review loop, open flip, watch - no user prompts in between. The main agent is the orchestrator and never touches code: it spawns agents, invokes skills, relays wake-ups, and answers escalations. The split exists for separation of duties - the author of a diff must not convene the review of its own diff - so all code is written by one persistent builder agent per PR, spawned once and woken by name for everything that follows.

## 1. The spec

Locate what to implement: the approved brainstorming result (in this conversation or at the GitHub location it was published to), an issue the user points at, or the request itself for trivial work. If the task is non-trivial (new feature, ambiguous scope, architectural impact) and no approved design exists, offer /brainstorming first via the question selector - offer, never require. The base branch is the repository default (`gh repo view --json defaultBranchRef`) unless the user says otherwise.

## 2. Setup and build

1. Decide the feature branch name first - `<login>/<slug>`, with `<login>` from `gh api user --jq .login` (derive it at runtime, never hardcode) and `<slug>` describing the change. Everything below is derived from it.
2. Spawn one builder via the Agent tool with `isolation: "worktree"` and the stable name `builder-<branch-slug>` (`<branch-slug>` = the branch name lowercased, every non-alphanumeric run replaced by a single hyphen; deterministic, so the name is re-derivable on resume from `gh pr view --json headRefName`). Its prompt: the spec (inline, or the GitHub link to fetch), the branch name to adopt, and the base branch. Because `isolation: "worktree"` generates the branch name, `<login>/<slug>` cannot be set at creation; the builder's first action is `git branch -m <login>/<slug>` to rename the generated branch in place, so state the target name in the spawn prompt.
3. The builder implements, tests, and opens a draft PR (its Phase 1), then reports the PR number. It escalates rather than deviating from the approved design; answer escalations from the spec when possible, and surface the rest to the user as a type 2 message before resuming it.

One builder per PR, forever: every later fix goes to the same agent via SendMessage. Never spawn a second builder or a fresh fixer for a PR that has one - the builder's accumulated context is the point.

## 3. The review loop (max 2 rounds)

With `round` starting at 1:

1. Invoke the review-panel skill by name on the draft PR.
2. If the round posted findings, wake the builder: "address the panel review on PR #N". The builder verifies each finding, fixes or rebuts on the threads, pushes, and reports back.
3. Re-round only if the builder applied substantive fixes - logic or design changes, not mechanical ones (lint, renames, comment edits) - by incrementing `round` and going to 1 for a re-check.

Reaching round 2 without convergence means something is structurally wrong - the design or implementation is off, or the review chain itself misbehaved. Stop and escalate to the user with a diagnosis: what each round found, why the fixes did not converge, and whether the cause looks like the design, the implementation, or a review bug.

## 4. Open flip and the one message

When the loop converges (or, after the round-cap escalation above, the user tells you to proceed):

1. Flip the PR open: `gh pr ready <n>`. Draft means machines are iterating; open means humans are involved.
2. Send the user exactly one message:
   - Type 1 (nothing unresolved): "ready for your final review - push back or merge"
   - Type 2 (open questions remain - builder rebuttals the panel did not accept, escalations needing a ruling): "escalated items - findings pushed back with uncertainty, your call", with each item and its uncertainty stated.

Never merge, close, or approve the PR - final review and merge are always the user's.

## 5. Watch to merge

1. Arm the PR monitor per the github-comment skill (Mode 5), owned by this session. The main session holds it because the watch must outlive any single builder turn and survive the builder's teardown at merge; a subagent could receive the events, but a builder-owned watch across its own dormant turns and past teardown is unverified, so ownership stays here until that is demonstrated.
2. On any monitor event, do exactly one thing: `SendMessage` to `builder-<branch-slug>` with "PR updated: PR #<n>". No classification, no fixing, no replying - the builder inspects the PR and handles what it finds (human feedback, CI, rebase; its Phase 3).
3. On merge or close the monitor exits and wakes the builder a final time. The builder files any deferred findings as tracking issues (merge only), sends its final report, and stops - it never removes its own worktree or branch, which is mechanically impossible from inside the locked tree it lives in. Teardown belongs to this session, which runs from the user's checkout where that worktree is not the current tree and its branch is not checked out, so the destructive commands are legal. After the builder's final report, find the PR branch's worktree in `git worktree list --porcelain` and remove it, then delete both copies of the branch:
   ```bash
   git worktree unlock "<worktree-path>"   # built-in worktrees stay locked while their owner lives
   git worktree remove "<worktree-path>"
   git branch -D "<branch>"
   gh api -X DELETE "repos/<owner>/<repo>/git/refs/heads/<branch>"
   ```
   Relay nothing further to the user unless the builder escalates.

If the session dies, the user resumes it and asks to re-arm the watch; GitHub still holds the full state, and the builder still holds its context.
