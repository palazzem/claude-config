---
name: implement
description: Use when the user asks to implement something - "implement X", "implement the brainstorm result", "build this spec". Runs the whole delivery chain without further prompts: spawns one persistent builder that codes and opens a draft PR, runs the review-panel loop, flips the PR open, then watches it to merge. The user is contacted only via the two message types.
argument-hint: "<what to implement> (optional) - a task description or a reference to an approved spec (issue URL or number)"
---

# Implement

Manual entry, automatic chain: draft PR, review loop, open flip, watch - no user prompts in between. The main agent is the orchestrator and never touches code: it spawns agents, invokes skills, relays wake-ups, and answers escalations. All code is written by one persistent builder agent per PR, spawned once and woken by name for everything that follows.

## 1. The spec

Locate what to implement: the approved brainstorming result (in this conversation or at the GitHub location it was published to), an issue the user points at, or the request itself for trivial work. If the task is non-trivial (new feature, ambiguous scope, architectural impact) and no approved design exists, offer /brainstorming first via the question selector - offer, never require. The base branch is the repository default (`gh repo view --json defaultBranchRef`) unless the user says otherwise.

## 2. Setup and build

1. Create an isolated worktree and feature branch off the base branch (`git worktree add`). Never build on the user's checked-out branch.
2. Spawn one builder via the Agent tool with the stable name `builder-<branch-slug>` (`<branch-slug>` = the branch name lowercased, every non-alphanumeric run replaced by a single hyphen - deterministic, so the name can always be re-derived from `gh pr view --json headRefName`). Its prompt: the spec (inline, or the GitHub link to fetch), the worktree path, the branch, and the base branch.
3. The builder implements, tests, and opens a draft PR (its Phase 1), then reports the PR number. It escalates rather than deviating from the approved design; answer escalations from the spec when possible, and surface the rest to the user as a type 2 message before resuming it.

One builder per PR, forever: every later fix goes to the same agent via SendMessage. Never spawn a second builder or a fresh fixer for a PR that has one - the builder's accumulated context is the point.

## 3. The review loop (max 3 rounds)

With `round` starting at 1:

1. Invoke the review-panel skill by name on the draft PR.
2. If the round posted findings, wake the builder: "address the panel review on PR #N". The builder verifies each finding, fixes or rebuts on the threads, pushes, and reports back.
3. Re-round only if the builder applied substantive fixes - logic or design changes, not mechanical ones (lint, renames, comment edits) - by incrementing `round` and going to 1 for a re-check.

Reaching round 3 without convergence means something is structurally wrong - the design or implementation is off, or the review chain itself misbehaved. Stop and escalate to the user with a diagnosis: what each round found, why the fixes did not converge, and whether the cause looks like the design, the implementation, or a review bug.

## 4. Open flip and the one message

When the loop converges (or, after the round-cap escalation above, the user tells you to proceed):

1. Flip the PR open: `gh pr ready <n>`. Draft means machines are iterating; open means humans are involved.
2. Send the user exactly one message:
   - Type 1 (nothing unresolved): "ready for your final review - push back or merge"
   - Type 2 (open questions remain - builder rebuttals the panel did not accept, escalations needing a ruling): "escalated items - findings pushed back with uncertainty, your call", with each item and its uncertainty stated.

Never merge, close, or approve the PR - final review and merge are always the user's.

## 5. Watch to merge

1. Pre-arm state check: `gh pr view <n> --json state -q .state`. If the PR is already MERGED or CLOSED, skip the monitor entirely - Mode 5 never emits for a PR that is already terminal when armed; see github-comment - and go straight to cleanup: wake the builder with "PR updated: PR #<n>" if it exists, otherwise invoke the worktree-lifecycle skill directly, passing the PR number and the repository.
2. Arm the PR monitor per the github-comment skill (Mode 5), owned by this session - a subagent cannot receive monitor events.
3. On any monitor event, do exactly one thing: `SendMessage` to `builder-<branch-slug>` with "PR updated: PR #<n>". No classification, no fixing, no replying - the builder inspects the PR and handles what it finds (human feedback, CI, rebase; its Phase 3).
4. On merge or close the monitor exits; the wake lets the builder clean up its worktree and branch and send its final report. Relay nothing further to the user unless the builder escalates.

If the session dies, the user resumes it and asks to re-arm the watch; GitHub still holds the full state. Re-arm through the same pre-arm state check: a PR that went terminal while the session was down goes straight to cleanup, and if the builder cannot be woken - a fresh session has no builder agent - the main agent performs the cleanup itself via the worktree-lifecycle skill, passing the PR number and the repository.
