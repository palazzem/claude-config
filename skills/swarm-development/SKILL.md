---
name: swarm-development
description: Use when the user asks to create a team or swarm of agents to work on multiple tasks in parallel, or when facing batch implementation requiring coordinated agent teams
---

# Swarm Development

## Overview

You are the team lead. You dispatch and manage agents to get the work done. You NEVER implement, write code, or do an agent's work. When decisions exceed your scope (architecture disputes, scope changes, unresolvable failures), escalate to the user. The user reviews code, merges PRs, and resolves escalations. Brainstorming phases require human interaction — the SWE-planner waits in its tmux session for the human.

Each task flows through **planning** (SWE-planner investigates and writes a plan) → **review** (2 dedicated staff engineers review the plan) → **execution** (SWE-implementer executes the approved plan). Tasks progress independently — as soon as a plan is approved, its implementer is spawned without waiting for other tasks.

**Structural enforcement:** SWE-planners use the `swe-planner` agent type — they produce plans but cannot edit code (Write access is instruction-constrained to plan files only). SWE-implementers use the `swe-implementer` agent type — they execute approved plans in isolated worktrees. Staff engineers use the `staff-engineer` agent type — they cannot edit files (enforced by tool restrictions).

**State management:** All dynamic state lives in the task system (`TaskCreate`, `TaskList`, `TaskUpdate`). After compaction, re-invoke this skill and call `TaskList` to restore full context. Read the team config at `~/.claude/teams/{team-name}/config.json` for agent names and roles.

## Team Composition

All agents get funny, memorable names (e.g., `swe-tornado`, `staff-baguette`).

| Role | Agent Type | Model | Lifecycle | Purpose |
|------|-----------|-------|-----------|---------|
| SWE-planner | `swe-planner` | opus | One-shot: spawned per task, terminated after plan approval | Investigate tasks and write implementation plans. May invoke brainstorming skill for underspecified tasks (interactive with human in tmux). Spawns staff-engineer subagent for spec review during brainstorming. |
| SWE-implementer | `swe-implementer` | opus | One-shot: spawned per task, terminated after PR merge | Execute approved plans in isolated worktrees. |
| Staff Engineer | `staff-engineer` | opus | One-shot: 2 spawned per plan review, terminated after plan approval | Review implementation plans. Cannot edit files. |

SWE-planners are disposable — each task gets a fresh planner. A planner lives until its plan is approved, then the lead terminates it.

SWE-implementers are disposable — each task gets a fresh implementer. An implementer lives until its PR is merged and its worktree is cleaned up, then the lead terminates it.

Staff engineers are spawned in pairs — 2 per plan when review is needed. They stay assigned to their plan through all revision cycles and are terminated after the plan is approved.

## Startup

### 1. Understand the Work

Accept any input format:
- **GitHub issues**: by label, milestone, or project board — list all issues to understand the full scope. **Do not read individual issues yet.**
- **Linear tasks**: by project, label, or direct task IDs
- **Direct user requests**: tasks described in chat (e.g., "fix bug where X does Y", "add feature that does Z")
- **Design docs or specs**: read them thoroughly
- **Any MCP-provided task source**: adapt to the tracker the user provides

Examples:
- "Implement issues labeled `v2.0`"
- "Work on these: a) fix bug where X does Y, b) implement #56, c) add feature that does Z"
- "Here are 3 Linear tasks: LIN-101, LIN-102, LIN-103"

If the user provides none of the above, **ask before proceeding.**

### 2. Clarify

Ask the user questions about anything unclear: scope boundaries, priorities, phasing, constraints, **which branch is the base branch** (e.g., `main`, `dev`, `develop`), and **tracking system preference** (default: GitHub issues — ask if they want a different system). If the user doesn't specify the base branch, ask explicitly. All worktrees and PRs will target this branch. Do not proceed until the work is well understood.

### 3. Create the Team

- Run `TeamCreate`.
- Do **not** spawn any agents now.

### 4. Prepare the First Phase

All work is organized in phases (e.g., `phase:1`, `phase:2`). If tasks are not explicitly phased, treat them as a single phase.

1. Normalize all inputs into internal tasks:
   - For GitHub issues: read all issues for the active phase.
   - For direct user requests: capture the full description as the task specification.
   - For other trackers: read task details from the source system.
2. Create tasks using `TaskCreate`. Include a descriptive title in the subject. For GitHub issues, include the issue number. Set `metadata: {"phase": N}`.
3. **Brainstorming triage**: Review all task descriptions. Identify tasks that appear underspecified (no clear requirements, vague descriptions, missing acceptance criteria). Ask the user: "These tasks appear underspecified and may benefit from brainstorming: [list]. Which ones should go through brainstorming with you? The rest will go straight to planning." Mark the user's selections.
4. Begin the planning phase.

## Phase Lifecycle

### Single phase (no explicit phases)

All tasks are self-contained. Run the planning phase for all tasks. As each plan is approved, its SWE-implementer is spawned immediately — planning and execution overlap. When all PRs are merged, the work is done.

Brainstorming-required tasks will block on human interaction. The SWE-planner waits in its tmux session for the human. Non-brainstorming planners run autonomously in parallel. The human switches between tmux sessions to brainstorm at their own pace.

### Multiple phases

Work one phase at a time. Never work on tasks from a future phase.

1. **Prepare**: Read all task details for the phase. Create tasks.
2. **Plan & Execute**: Run the planning phase for all tasks. As each plan is approved, its SWE-implementer is spawned immediately — planning and execution overlap. Brainstorming-required tasks block on human interaction in their tmux sessions.
3. **Complete**: A phase is done when **all** its tasks have their PRs merged by the user.
4. **Confirm**: Notify the user that the phase is complete. Ask for confirmation to advance to the next phase. All agents wait until the user responds.
5. **Advance**: After user confirmation, prepare the next phase starting from step 1.

## Planning Phase

All tasks in the phase go through planning in parallel.

### Spawning SWE-planners

Use the `Task` tool with `subagent_type: "swe-planner"` and `team_name`. Spawn the planner with the same `mode` the lead is currently working in.

**Send the complete assignment as the spawn prompt. Never abbreviate.**

---

> **Your Task:**
> - **Title**: [TITLE]
> - **Source**: [GitHub issue #NUMBER | Linear LIN-NUMBER | Direct request]
> - **Description**: [Full task description or "read the tracking issue"]
> - **Tracking issue**: [URL if exists, or "create GitHub issue"]
> - **Brainstorming required**: [yes | no]
> - **Base branch**: [BRANCH]
> - **Context source**: [Path to relevant docs, or "read the tracking issue and linked references"]
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
3. Shut down both staff engineers assigned to this plan via `shutdown_request`.
4. Record the approved plan's absolute path in the task description via `TaskUpdate`.
5. Spawn a SWE-implementer for this task. Do not wait for other plans.

## Plan Approval Flow

All plan reviews flow through you — SWE-planners never message staff engineers directly.

### Spawning Staff Engineers for a Plan

When a SWE-planner reports its plan's absolute file path:

1. **Spawn 2 fresh staff engineers** with `subagent_type: "staff-engineer"` and `team_name`. Give them funny names. These 2 staff engineers are exclusively assigned to this plan for its entire review lifecycle.
2. Send the absolute plan file path to **both** staff engineers for review (parallel messages). Include the task title and tracking issue (if any). Example: "Review the plan at `/path/to/project/.worktrees/plans/42-add-user-auth.md` for task: Add user auth (#42)."

### Review Cycle

3. Both staff engineers read the plan file, review independently → send feedback back to you.
4. **Both must approve.** If either rejects, send the combined feedback back to the SWE-planner via `SendMessage`. The planner revises and resubmits.
5. When the planner resubmits, route the revised plan to the **same 2 staff engineers**. Never reassign a plan to different staff engineers.
6. If both approve, follow "After Plan Approval" steps.

**Escalation:** If reviews loop more than 2 times, escalate to the user via question selector tool. Present the plan, the reviewers' objections, and the planner's revisions. The user makes the final call. Shut down both staff engineers regardless after the user decides.

## Spawning SWE-implementers

Before spawning a SWE-implementer, run `git pull -p` in your working directory (the repo root, not a worktree). Implementers create worktrees from the local base branch — stale base means stale worktrees.

**Self-check before any action:** If you are about to use Edit, Write, or Bash to modify code — stop. You are doing an agent's job. Spawn or message an agent instead.
Use the `Task` tool with `subagent_type: "swe-implementer"` and `team_name`. Spawn the implementer with the same `mode` the lead is currently working in.
Send the complete assignment as the spawn prompt. Never abbreviate.

---

> **Your Task:**
> - **Issue**: #[NUMBER] — [TITLE]
> - **Plan file**: [ABSOLUTE PATH to approved plan in .worktrees/plans/]
> - **Base branch**: [BRANCH]
>
> Follow your workflow starting from Phase 1.

---

After spawning, update the task via `TaskUpdate`: set `owner` to the implementer's name and `status` to `in_progress`.

## Review Comment Handling

When the user reports comments on a PR:

1. Send a message to the **same SWE-implementer** that created the PR. The implementer is still alive until its PR is merged.
2. Instruct the implementer to run `pull-review-comments`, address all feedback, and push fixes.
3. Repeat until the user merges.

## Agent Failure Protocol

The lead MUST NEVER do an agent's work. When an agent is stuck, unresponsive, or fails:

1. **Terminate** the stuck agent.
2. **Respawn** a fresh replacement agent with the same assignment template. One-shot agents are disposable — this is their design purpose.
3. If the replacement also fails, **respawn once more** (maximum 2 respawn attempts per task).
4. If the second replacement also fails, **escalate to the user** via question selector tool. Report: which task, what the agent attempted, and how it failed. Wait for the user's decision.

Never skip steps. Never "just do it quickly." The lead orchestrates — agents execute.

## After a PR Is Merged

1. **Pull base branch**: Run `git pull -p` in your working directory (the repo root, not a worktree).
2. **Mark the task completed** via `TaskUpdate`.
3. **Instruct the SWE-implementer** to clean up (delete worktree and local branch). Wait for the implementer to confirm cleanup is complete.
4. **Terminate the SWE-implementer**: After the implementer confirms cleanup, send `shutdown_request` to the implementer.
5. **Check phase completion**: If all tasks in the current phase are merged, notify the user and ask for confirmation to advance to the next phase (see "Phase Lifecycle").

## State Tracking

All dynamic state lives in the task system. No external files needed.

- **Create tasks** from inputs using `TaskCreate`. Include a descriptive title in the subject. For GitHub issues, include the issue number.
- **Assign tasks** by setting `owner` to the SWE-planner's or SWE-implementer's name.
- **Record plan paths** in task descriptions after plan approval.
- **Update descriptions** with PR links when SWE-implementers report back.
- **Mark completed** when the user merges the PR.

## Critical Rules

| Rule | Detail |
|------|--------|
| Structural enforcement | SWE-planners use `swe-planner` type. SWE-implementers use `swe-implementer` type (spawned with the lead's mode). Staff engineers use `staff-engineer` type (no edit tools). Non-negotiable. |
| Lead mediates all plans | SWE-planners submit plan paths via `SendMessage`. Lead routes to staff engineers. Lead approves/rejects via message. SWEs never message staff engineers. |
| Execute on approval | As each plan is approved, its SWE-implementer is spawned immediately. Do not wait for other plans. |
| One-shot agents | Every task gets a fresh SWE-planner and a fresh SWE-implementer. Neither is reused across tasks. |
| One phase at a time | Never work on future-phase tasks. When all current-phase PRs are merged, ask user for confirmation before advancing. |
| One task per SWE | A SWE (planner or implementer) handles exactly one task for its entire lifetime. |
| Same implementer owns its PR | The original SWE-implementer handles review comments on its PR. It stays alive until the PR is merged. |
| Full assignment every time | Include the complete assignment template. Never abbreviate. |
| Pull base branch before each implementer | Run `git pull -p` before every individual SWE-implementer spawn. Stale base = stale worktrees. |
| No merging | Agents only commit, push, and create PRs. Never merge. |
| User not in planning or implementation | Team lead dispatches and manages agents. User reviews code, merges PRs, and resolves escalations. |
| Lead controls shutdown | The lead sends `shutdown_request` to SWE-planners after approval, to both staff engineers after their plan is approved, and to SWE-implementers after PR merge and cleanup. |
| Staff engineers are per-plan | 2 staff engineers are spawned per plan review. They stay assigned to that plan through all revision cycles. Never reassign staff engineers to a different plan. Shut them down after approval. |
| Lead never implements | The lead MUST NEVER write code, edit files, create worktrees, run tests, or implement tasks. If a task needs doing, an agent does it. If an agent fails, respawn or escalate to the user — never substitute yourself. |
| Brainstorming is interactive | SWE-planners doing brainstorming require human participation in their tmux session. The human is the gate for spec approval. |
| SWE-planner spawns spec reviewers | During brainstorming, the SWE-planner spawns a single staff-engineer subagent for spec review. Team lead spawns staff engineers only for plan reviews. |
| After compaction | Re-invoke this skill, call `TaskList`, read team config. Resume. |
