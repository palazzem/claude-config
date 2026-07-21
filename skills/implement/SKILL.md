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

1. Reclaim first. Before spawning anything, run the Reclaim procedure (`### Reclaim` below) from the user's checkout - it reconciles any worktree or branch a crashed prior run left behind and is a silent no-op when state is clean.
2. Decide the feature branch name - `<login>/<slug>`, with `<login>` from `gh api user --jq .login` (derive it at runtime, never hardcode) and `<slug>` describing the change. Everything below is derived from it.
3. Spawn one builder via the Agent tool with `isolation: "worktree"` and the stable name `builder-<owner>-<repo>-<branch-slug>` (`<branch-slug>` = the branch name lowercased, every non-alphanumeric run replaced by a single hyphen; the owner and repo come from `gh repo view --json nameWithOwner` and keep two repositories sharing a branch name from colliding on one agent - deterministic, so the name can always be re-derived from `gh pr view --json headRefName`; repository `acme/widgets` with branch `dana/worktree-internals` gives agent `builder-acme-widgets-dana-worktree-internals`). Its prompt: the spec (inline, or the GitHub link to fetch), the branch name to adopt, and the base branch.
4. The builder implements, tests, and opens a draft PR (its Phase 1), then reports the PR number. It escalates rather than deviating from the approved design; answer escalations from the spec when possible, and surface the rest to the user as a type 2 message before resuming it.

### Isolation

`isolation: "worktree"` is what actually isolates a builder. Claude Code creates `<repo>/.claude/worktrees/agent-<hex>` on a generated `worktree-agent-<hex>` branch cut fresh from `origin/<base>`, locks the tree to that agent, and pins the agent's working directory to it.

- **Never create the worktree by hand.** A tree made with `git worktree add` is invisible to the isolation guard: the guard does not recognize it as the agent's assigned workspace, so the agent's writes are blocked or redirected into whichever tree the guard does consider current. Manual isolation is not isolation.
- **Never use `EnterWorktree` here.** It mutates the calling session's process-wide working directory, and the orchestrator must stay in the user's checkout. It also refuses creation from a subagent with a cwd override, and a parent that isolates ends up redirecting its subagents' writes into the parent's own tree rather than each subagent's.
- **The builder adopts the branch name after spawn.** `isolation: "worktree"` generates the branch name, so `<login>/<slug>` cannot be set at creation. The builder's first action is `git branch -m <login>/<slug>`, which renames in place, leaves the worktree registration pointing at the new ref, and leaves no stray branch behind. State the target name in the spawn prompt.
- **Built-in worktrees are locked while their owner lives.** `git worktree list --porcelain` reports `locked claude agent ...` on them, and `git worktree remove` fails with exit 128 on a locked tree. The builder cannot reclaim the tree it is standing in; the main session reclaims it, unlocking with `git worktree unlock` before a flagless `git worktree remove` rather than forcing - see `### Reclaim`.

One builder per PR, forever: every later fix goes to the same agent via SendMessage. Never spawn a second builder or a fresh fixer for a PR that has one - the builder's accumulated context is the point.

### Reclaim

The main session owns worktree and branch reclaim; the builder never does. From inside its isolated worktree the guard refuses every command that reaches the shared checkout (reads included), and git itself refuses a worktree's self-teardown, so the builder can execute zero teardown steps. Reclaim runs from the user's checkout as an idempotent reconciliation over observable state, not as a handler on the builder's death: the work list is derived by observation - the `git worktree list --porcelain` table and `refs/heads/` - joined against GitHub PR state, so a crashed prior run is repaired by the same path as the happy one. It is argument-free and safe to run at any time, so the user may also invoke it directly.

**Pass A - worktrees.** `git worktree list --porcelain`. Skip the first entry (always the main checkout). Skip entries with no `branch` line (detached - report, never remove). Skip `locked claude session ...` entries (those are `EnterWorktree` session worktrees, not builder agent worktrees). For each remaining `locked claude agent ...` entry:

1. **Ownership gate.** Act only if either (i) the builder's Agent invocation has already returned to this session, or (ii) the pid named in the lock reason is dead (`ps -p <pid>`). If the lock reason cannot be parsed, treat it as live and skip. Never unlock a live agent.
2. **Resolve the PR.** Prefer `gh pr view <n> --json number,state,headRefOid` when the chain still holds the number; otherwise `gh pr list -R <slug> --head <branch> --state all --json number,state,headRefOid --limit 2`. Zero rows -> report and touch nothing. TWO rows -> abort this entry and report both PR numbers; never guess which. `OPEN` -> skip silently. A `gh` failure -> abort the pass and change nothing (an empty result must never be read as CLOSED).
3. **Unlock.** `git worktree unlock <path>` if the entry is locked.
4. **Remove.** `git worktree remove <path>` with NO flags, ever. A refusal (dirty or modified tree) stops this entry - report the preserved path, never force.
5. **Delete the branch under one invariant:** delete a local branch only when its tip is proven contained in a copy that outlives the deletion.
   - MERGED -> `git merge-base --is-ancestor <branch> <headRefOid>`; exit 0 -> `git branch -D <branch>`.
   - CLOSED -> `git ls-remote --exit-code --heads origin <branch>` to get the remote OID, then the same ancestry check against that remote OID; exit 0 -> `git branch -D <branch>`.
   - Any non-zero exit (local commits not captured, unresolvable rev, or no remote ref) -> keep the branch and report it. `-d` is unusable because a squash-merged branch's commits are not ancestors of the base, so the ancestry check runs against the PR's merged head OID (or the closed PR's remote OID), never against the base; use `-D` gated by that proof.
6. **Never `git push origin --delete`,** on either path. `deleteBranchOnMerge` already removes the remote head on merge, and on a closed PR the remote branch may be the last durable copy of unmerged work.

**Pass B - branchless residue.** Removing a worktree directory leaves the renamed local branch behind with a `[gone]` upstream and no worktree entry, so a worktree-only sweep never sees it. Enumerate `git for-each-ref --format='%(refname:short) %(worktreepath)' refs/heads/` (the `refs/heads/` restriction is required - without it `refs/remotes/origin/HEAD` surfaces as a branch named `origin`). Skip the default branch and anything still attached to a worktree. For the rest, apply the same PR-resolution gate (Pass A step 2) and the same containment invariant (Pass A step 5). A branch with no resolvable PR is a human's local branch - never touch it.

Then once: `git fetch --prune`. Report one line per preserved or aborted item; silence means clean.

Triggers: Reclaim is the FIRST step of section 2 (before spawning any builder, to reconcile a crashed prior run) and the LAST step of section 5 (after the builder's final report returns). Because it is idempotent and argument-free, the user may also invoke it directly.

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

1. Arm the PR monitor per the github-comment skill (Mode 5), owned by this session - a subagent cannot receive monitor events.
2. On any monitor event, do exactly one thing: `SendMessage` to `builder-<owner>-<repo>-<branch-slug>` with "PR updated: PR #<n>". No classification, no fixing, no replying - the builder inspects the PR and handles what it finds (human feedback, CI, rebase; its Phase 3).
3. On merge or close the monitor exits; the wake is only for the builder to file its deferred-finding tracking issues (on merge) and send its final report. Worktree and branch reclaim is not the builder's - it cannot reach this checkout from inside its isolated tree.
4. After that final report returns, run Reclaim (`### Reclaim`) as the last step: it removes the merged or closed PR's worktree and deletes its branch under the containment invariant. Relay nothing further to the user unless the builder escalates.

If the session dies, the user resumes it and asks to re-arm the watch; GitHub still holds the full state, the builder still holds its context, and the next Reclaim - run first at section 2 or invoked directly - repairs anything a crash left mid-teardown.
