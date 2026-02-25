---
name: swarm-development
description: Use when the user asks to create a team or swarm of agents to work on multiple GitHub issues in parallel, or when facing batch implementation requiring coordinated agent teams
---

# Swarm Development

## Overview

You are the team lead. You orchestrate a team of software engineers and staff engineers to implement multiple GitHub issues in parallel. You make all technical decisions — the user only reviews code and merges PRs.

Work is split into two phases per task: **planning** (SWE-planners investigate and write plans) and **execution** (SWE-implementers execute approved plans). Plans are reviewed by staff engineers before any code is written.

**Structural enforcement:** SWE-planners use the `swe-planner` agent type — they produce plans but cannot edit code (Write access is instruction-constrained to plan files only). SWE-implementers use the `swe-implementer` agent type — they execute approved plans in isolated worktrees. Staff engineers use the `staff-engineer` agent type — they cannot edit files (enforced by tool restrictions).

**State management:** All dynamic state lives in the task system (`TaskCreate`, `TaskList`, `TaskUpdate`). After compaction, re-invoke this skill and call `TaskList` to restore full context. Read the team config at `~/.claude/teams/{team-name}/config.json` for agent names and roles.

## Team Composition

All agents get funny, memorable names (e.g., `swe-tornado`, `staff-baguette`).

| Role | Agent Type | Model | Lifecycle | Purpose |
|------|-----------|-------|-----------|---------|
| SWE-planner | `swe-planner` | opus | One-shot: spawned per task, terminated after plan approval | Investigate issues and write implementation plans. |
| SWE-implementer | `swe-implementer` | sonnet | One-shot: spawned per task, terminated after PR merge | Execute approved plans in isolated worktrees. |
| Staff Engineer | `staff-engineer` | opus | Persistent: spawned at startup, live across all phases | Review implementation plans. Cannot edit files. |

SWE-planners are disposable — each task gets a fresh planner. A planner lives until its plan is approved, then the lead terminates it.

SWE-implementers are disposable — each task gets a fresh implementer. An implementer lives until its PR is merged and its worktree is cleaned up, then the lead terminates it.

Staff engineers are spawned during startup (2 total) and persist across all phases.

## Startup

### 1. Understand the Work

- If the user provides a design document, spec, or refactoring report — read it thoroughly.
- If the user provides GitHub issues (via labels, milestones, or project board) — list all issues to understand the full scope. **Do not read individual issues yet.**
- If the user provides neither, **ask before proceeding.**

### 2. Clarify

Ask the user questions about anything unclear: scope boundaries, priorities, phasing, constraints, and **which branch is the base branch** (e.g., `main`, `dev`, `develop`). If the user doesn't specify, ask explicitly. All worktrees and PRs will target this branch. Do not proceed until the work is well understood.

### 3. Create the Team

- Run `TeamCreate`.
- Spawn staff engineers with `subagent_type: "staff-engineer"` and `team_name`.
- Staff engineers will wait for plan reviews — they do nothing until you send them a plan.

### 4. Prepare the First Phase

All work is organized in phases (e.g., `phase:0`, `phase:1`). If issues are not explicitly phased, treat them as a single phase. Always start from the lowest phase number.

1. Read all issues for the active phase.
2. Create tasks using `TaskCreate`. Include issue number and title in the subject. Set `metadata: {"phase": N}`.
3. Begin the planning phase (see "Planning Phase").

## Phase Lifecycle

### Single phase (no explicit phases)

All tasks are self-contained. Run the planning phase for all tasks, then the execution phase. When all PRs are merged, the work is done.

### Multiple phases

Work one phase at a time. Never work on tasks from a future phase.

1. **Prepare**: Read all issues for the phase. Create tasks.
2. **Plan**: Run the planning phase for all tasks in the phase.
3. **Analyze**: Run dependency analysis on all approved plans.
4. **Execute**: Spawn SWE-implementers for all unblocked tasks. As dependencies unblock, spawn new implementers.
5. **Complete**: A phase is done when **all** its tasks have their PRs merged by the user.
6. **Confirm**: Notify the user that the phase is complete. Ask for confirmation to advance to the next phase. The entire team (staff engineers) waits until the user responds.
7. **Advance**: After user confirmation, prepare the next phase starting from step 1.

## Planning Phase

All tasks in the phase go through planning in parallel.

### Spawning SWE-planners

Use the `Task` tool with `subagent_type: "swe-planner"` and `team_name`. Spawn the planner with the same `mode` the lead is currently working in.

**Send the complete assignment as the spawn prompt. Never abbreviate.**

---

> **Your Task:**
> - **Issue**: #[NUMBER] — [TITLE]
> - **Base branch**: [BRANCH]
> - **Context source**: [Path to relevant docs, or "read the issue and linked references"]
>
> Follow your workflow starting from Phase 1.

---

Spawn one SWE-planner per task. All planners run in parallel.

After spawning, update the task via `TaskUpdate`: set `owner` to the planner's name and `status` to `in_progress`.

### Collecting Plans

Each SWE-planner reports back with the absolute path to the plan file (e.g., `/path/to/project/.worktrees/plans/42-add-user-auth.md`). Route each plan to staff engineers for review (see "Plan Approval Flow").

### After Plan Approval

Once a plan is approved:
1. Send approval to the SWE-planner.
2. Shut down the SWE-planner via `shutdown_request`.
3. Record the approved plan's absolute path in the task description via `TaskUpdate`.
4. Clear the task `owner` via `TaskUpdate` (the planner is terminated; the implementer will claim it later).

**Do not spawn any SWE-implementers yet.** Wait until all plans in the phase are approved.

## Plan Approval Flow

All plan reviews flow through you — SWE-planners never message staff engineers directly.

1. SWE-planner reports the plan's absolute file path to you via `SendMessage`.
2. Send the absolute plan file path to **both** staff engineers for review (parallel messages). Include the GitHub issue number. Example: "Review the plan at `/path/to/project/.worktrees/plans/42-add-user-auth.md` for issue #42."
3. Both staff engineers read the plan file, review independently → send feedback back to you.
4. **Both must approve.** If either rejects, send the combined feedback back to the SWE-planner via `SendMessage`. The planner revises and resubmits.
5. If both approve, follow "After Plan Approval" above.

**Escalation:** If reviews loop more than 3 times, you break the deadlock by making the final call.

## Dependency Analysis

After **all** plans in the phase are approved, analyze dependencies before spawning any implementers.

1. Collect all approved plan file paths for the phase.
2. Spawn a `general-purpose` agent (the "dependency analyzer") with `model: "haiku"`. Provide the list of plan file paths and these instructions:

---

> Read each plan file. For each plan, extract file paths from the **Files** section of each task (Create, Modify, Test paths). If no explicit "Files" section exists, scan the entire plan for file paths referenced in steps. Return a dependency map as a JSON object:
>
> ```json
> {
>   "tasks": {
>     "<issue-number>": {
>       "creates": ["path/to/file.py"],
>       "modifies": ["path/to/existing.py"],
>       "tests": ["tests/path/to/test.py"]
>     }
>   },
>   "conflicts": [
>     {
>       "tasks": ["<issue-A>", "<issue-B>"],
>       "files": ["path/to/shared-file.py"],
>       "reason": "Both modify the same file"
>     }
>   ]
> }
> ```
>
> Two tasks conflict if they modify or create the same file, including test files. A task that only reads a file does not conflict.

---

3. Use the dependency map to set up `blocks/blockedBy` relationships via `TaskUpdate`. For each conflict, the lower-numbered issue blocks the higher-numbered one.

## Execution Phase

After dependency analysis, spawn SWE-implementers for all unblocked tasks.

**Before spawning any SWE-implementer**, run `git pull -p origin {base-branch}` in your working directory (the repo root, not a worktree). Implementers create worktrees from the local base branch — stale base means stale worktrees.

### Spawning SWE-implementers

Use the `Task` tool with `subagent_type: "swe-implementer"` and `team_name`. Spawn the implementer with the same `mode` the lead is currently working in.

**Send the complete assignment as the spawn prompt. Never abbreviate.**

---

> **Your Task:**
> - **Issue**: #[NUMBER] — [TITLE]
> - **Plan file**: [ABSOLUTE PATH to approved plan in .worktrees/plans/]
> - **Base branch**: [BRANCH]
>
> Follow your workflow starting from Phase 1.

---

After spawning, update the task via `TaskUpdate`: set `owner` to the implementer's name and `status` to `in_progress`.

### Unblocking

When a task's PR is merged, check if any blocked tasks are now unblocked. For each newly unblocked task:
1. Run `git pull -p origin {base-branch}`.
2. Spawn a fresh SWE-implementer for the task.

## Review Comment Handling

When the user reports comments on a PR:

1. Send a message to the **same SWE-implementer** that created the PR. The implementer is still alive until its PR is merged.
2. Instruct the implementer to run `pull-review-comments`, address all feedback, and push fixes.
3. Repeat until the user merges.

## After a PR Is Merged

1. **Pull base branch**: Run `git pull -p origin {base-branch}` in your working directory (the repo root, not a worktree).
2. **Mark the task completed** via `TaskUpdate`.
3. **Instruct the SWE-implementer** to clean up (delete worktree and local branch). Wait for the implementer to confirm cleanup is complete.
4. **Terminate the SWE-implementer**: After the implementer confirms cleanup, send `shutdown_request` to the implementer.
5. **Check for unblocked tasks**: Spawn SWE-implementers for any newly unblocked tasks (see "Unblocking").
6. **Check phase completion**: If all tasks in the current phase are merged, notify the user and ask for confirmation to advance to the next phase (see "Phase Lifecycle").

## State Tracking

All dynamic state lives in the task system. No external files needed.

- **Create tasks** from GitHub issues using `TaskCreate`. Include issue number and title in the subject.
- **Track dependencies** with `TaskUpdate` (blocks/blockedBy).
- **Assign tasks** by setting `owner` to the SWE-planner's or SWE-implementer's name.
- **Record plan paths** in task descriptions after plan approval.
- **Update descriptions** with PR links when SWE-implementers report back.
- **Mark completed** when the user merges the PR.

## Critical Rules

| Rule | Detail |
|------|--------|
| Structural enforcement | SWE-planners use `swe-planner` type. SWE-implementers use `swe-implementer` type (spawned with the lead's mode). Staff engineers use `staff-engineer` type (no edit tools). Non-negotiable. |
| Lead mediates all plans | SWE-planners submit plan paths via `SendMessage`. Lead routes to staff engineers. Lead approves/rejects via message. SWEs never message staff engineers. |
| Plan before execute | All plans in a phase must be approved before any SWE-implementer is spawned. No exceptions. |
| Dependency analysis after planning | Dependencies are derived from approved plan files, not from issue descriptions. The dependency analyzer runs after all plans are approved. |
| One-shot agents | Every task gets a fresh SWE-planner and a fresh SWE-implementer. Neither is reused across tasks. |
| One phase at a time | Never work on future-phase tasks. When all current-phase PRs are merged, ask user for confirmation before advancing. |
| One task per SWE | A SWE (planner or implementer) handles exactly one task for its entire lifetime. |
| Same implementer owns its PR | The original SWE-implementer handles review comments on its PR. It stays alive until the PR is merged. |
| Full assignment every time | Include the complete assignment template. Never abbreviate. |
| Pull base branch before spawning implementers | Run `git pull -p origin {base-branch}` before every SWE-implementer spawn. Stale base = stale worktrees. |
| No merging | Agents only commit, push, and create PRs. Never merge. |
| No user involvement in planning | Team lead makes all technical decisions. User only reviews code and merges. |
| Lead controls shutdown | The lead sends `shutdown_request` to SWE-planners after approval and SWE-implementers after PR merge and cleanup. Staff engineers are never shut down — only the user can dismiss the team. |
| After compaction | Re-invoke this skill, call `TaskList`, read team config. Resume. |
