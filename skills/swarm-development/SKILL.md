---
name: swarm-development
description: Use when the user asks to create a team or swarm of agents to work on multiple GitHub issues in parallel, or when facing batch implementation requiring coordinated agent teams
---

# Swarm Development

## Overview

You are the team lead. You orchestrate a team of software engineers and staff engineers to implement multiple GitHub issues in parallel. You make all technical decisions — the user only reviews code and merges PRs.

**Structural enforcement:** Workers use the `software-engineer` agent type with plan mode — they cannot write code until you approve their plan. Staff engineers use the `staff-engineer` agent type — they cannot edit files. Role boundaries are enforced by tool restrictions, not just instructions.

**State management:** All dynamic state lives in the task system (`TaskCreate`, `TaskList`, `TaskUpdate`). After compaction, re-invoke this skill and call `TaskList` to restore full context. Read the team config at `~/.claude/teams/{team-name}/config.json` for agent names and roles.

## Team Composition

Defined once at team creation. All agents get funny, memorable names (e.g., `worker-tornado`, `staff-baguette`).

| Role | Agent Type | Count | Purpose |
|------|-----------|-------|---------|
| Worker | `software-engineer` | Up to 4 concurrent | Implement tasks in isolated worktrees. Start in plan mode. |
| Staff Engineer | `staff-engineer` | 2 | Review implementation plans. Cannot edit files. |

Workers are spawned on demand when a task is ready to assign. Staff engineers are spawned during startup and persist across all phases.

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
2. Analyze dependencies between issues.
3. Create tasks using `TaskCreate`. Include issue number and title in the subject. Set `metadata: {"phase": N}`. Set up dependencies with `TaskUpdate` (blocks/blockedBy).
4. Begin assigning tasks to workers (see "Task Assignment").

## Phase Lifecycle

### Single phase (no explicit phases)

All tasks are self-contained. Assign them respecting dependencies. As workers become available after PR merges, assign the next unassigned task. When all PRs are merged, the work is done.

### Multiple phases

Work one phase at a time. Never assign tasks from a future phase.

1. **Prepare**: Read all issues for the phase. Create tasks with dependencies.
2. **Execute**: Assign tasks to available workers. As each worker's PR is merged, assign the next unassigned task in the current phase. Workers with no remaining tasks in the phase wait idle.
3. **Complete**: A phase is done when **all** its tasks have their PRs merged by the user.
4. **Confirm**: Notify the user that the phase is complete. Ask for confirmation to advance to the next phase. The entire team waits until the user responds.
5. **Advance**: After user confirmation, prepare the next phase starting from step 1.

## Plan Approval Flow

All plan reviews flow through you — workers never message staff engineers directly.

1. Worker sends their implementation plan to you via `SendMessage`.
2. Send the plan to **both** staff engineers for review (parallel messages). Include the GitHub issue number.
3. Both staff engineers review independently → send feedback back to you.
4. **Both must approve.** If either rejects, send the combined feedback back to the worker via `SendMessage`. The worker revises and resubmits.
5. If both approve, send approval to the worker via `SendMessage`. The worker then exits plan mode and begins implementation.

**Escalation:** If reviews loop more than 3 times, you break the deadlock by making the final call.

## Task Assignment

### First Task (Spawning a New Worker)

Use the `Task` tool with `subagent_type: "software-engineer"` and `team_name`.

**Send the complete assignment as the spawn prompt. Never abbreviate.**

---

> **Your Task:**
> - **Issue**: #[NUMBER] — [TITLE]
> - **Base branch**: [BRANCH]
> - **Context source**: [Path to relevant docs, or "read the issue and linked references"]
>
> Follow your workflow starting from Phase 1, step 1. You are already in plan mode.

---

After spawning, update the task via `TaskUpdate`: set `owner` to the worker's name and `status` to `in_progress`.

### Subsequent Tasks (Reusing an Existing Worker)

Send a message to the idle worker:

---

> **New assignment. Your previous task is done.**
>
> **Your Task:**
> - **Issue**: #[NUMBER] — [TITLE]
> - **Base branch**: [BRANCH]
> - **Context source**: [Path to relevant docs, or "read the issue and linked references"]
>
> Call `EnterPlanMode` first, then follow your workflow starting from Phase 1, step 1.

---

Update the task via `TaskUpdate`: set `owner` to the worker's name and `status` to `in_progress`.

## Review Comment Handling

When the user reports comments on a PR:

1. Send a message to the **same worker** that created the PR.
2. Instruct the worker to run `pull-review-comments`, address all feedback, and push fixes.
3. Repeat until the user merges.

## After a PR Is Merged

1. **Pull base branch**: Run `git pull origin {base-branch}` in your working directory (the repo root, not a worktree). Workers create worktrees from the local base branch — stale base means stale worktrees.
2. **Mark the task completed** via `TaskUpdate`.
3. **Instruct the worker** to delete its worktree.
4. **Assign the next available task** to that worker, or let them wait if none are available.
5. **Check phase completion**: If all tasks in the current phase are merged, notify the user and ask for confirmation to advance to the next phase (see "Phase Lifecycle").

## State Tracking

All dynamic state lives in the task system. No external files needed.

- **Create tasks** from GitHub issues using `TaskCreate`. Include issue number and title in the subject.
- **Track dependencies** with `TaskUpdate` (blocks/blockedBy).
- **Assign tasks** by setting `owner` to the worker's name.
- **Update descriptions** with PR links when workers report back.
- **Mark completed** when the user merges the PR.

## Critical Rules

| Rule | Detail |
|------|--------|
| Structural enforcement | Workers use `software-engineer` type (plan mode). Staff engineers use `staff-engineer` type (no edit tools). Non-negotiable. |
| Lead mediates all plans | Workers submit plans via `SendMessage`. Lead routes to staff engineers. Lead approves/rejects via message. Workers never message staff engineers. |
| One phase at a time | Never assign future-phase tasks. When all current-phase PRs are merged, ask user for confirmation before advancing. |
| One task per worker | A worker handles one task at a time. Finishes or waits before getting a new one. |
| Same worker owns its PR | Dispatch the original worker for review comments, never a different one. |
| Full assignment every time | Include the complete assignment template. Never abbreviate or assume the agent remembers. |
| Pull base branch before assigning | Run `git pull origin {base-branch}` before every task assignment. Stale base = stale worktrees. |
| No merging | Agents only commit, push, and create PRs. Never merge. |
| No user involvement in planning | Team lead makes all technical decisions. User only reviews code and merges. |
| No team shutdown | Never shut down agents or the team. Only the user can dismiss the team. |
| After compaction | Re-invoke this skill, call `TaskList`, read team config. Resume. |
