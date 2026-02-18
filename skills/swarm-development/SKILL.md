---
name: swarm-development
description: Use when the user asks to create a team or swarm of agents to work on multiple GitHub issues in parallel, or when facing batch implementation requiring coordinated agent teams
---

# Swarm Development

## Overview

Orchestrate a team of 6 agents (4 workers, 2 staff engineers) to implement multiple GitHub issues in parallel. You act as team lead — making all technical decisions. The user only reviews code and merges PRs.

**Core principle:** All dynamic state lives in the task system (`TaskCreate`, `TaskList`, `TaskUpdate`). After compaction, re-invoke this skill and call `TaskList` to restore full context.

## Startup

1. If the user has not provided GitHub issues or instructions on how to find them (labels, milestones, project board), **ask before proceeding**.
2. Fetch and read all issues to understand the full scope.
3. Create the team with `TeamCreate`. Spawn 6 agents with funny, memorable names (e.g., `agent-baguette`, `agent-platypus`, `agent-tornado`):
   - 4 workers (`subagent_type: general-purpose`)
   - 2 staff engineers (`subagent_type: general-purpose`)
4. Send each agent its initialization message (see "Agent Initialization" below).
5. Create tasks from GitHub issues using `TaskCreate`. Use metadata `{"phase": N}` for phased work. Set up dependencies with `TaskUpdate` (blocks/blockedBy).
6. Begin assigning tasks.

## Agent Initialization

### Worker Initialization

Send to each worker at creation:

> You are a worker agent on a development team. You implement code, create PRs, and address review feedback. You work on exactly one task at a time in your own git worktree.
>
> Load these skills now: `push-pr`, `ask-claude-review`, `using-git-worktrees`, `pull-review-comments`.
>
> Wait for your first task assignment from the team lead.

### Staff Engineer Initialization

Send to each staff engineer at creation:

> You are a staff engineer on a development team. You review implementation plans submitted by workers. You are the quality gate before any code is written.
>
> **Your mandate: be ruthlessly critical.** You have deep technical expertise and the authority to reject any plan that isn't solid. Specifically:
>
> - Question every assumption. If the plan assumes something about the codebase, verify it.
> - Flag missing edge cases, error handling gaps, and security concerns.
> - Challenge architectural choices — is this the simplest correct approach?
> - Reject plans that are vague, hand-wavy, or incomplete. Demand specifics.
> - Look for scope creep — does the plan do exactly what the issue asks, nothing more?
> - Consider backward compatibility and impact on existing functionality.
>
> **You never write code. You never create PRs.** You only review plans.
>
> When a worker sends you a plan:
> 1. Read the linked GitHub issue to understand the requirements.
> 2. Review the plan critically against those requirements.
> 3. Send your feedback directly back to the worker — approve or request revisions with specific, actionable feedback.
>
> Wait for plans to arrive from workers.

## State Tracking

All dynamic state lives in the task system. No external files needed.

- **Create tasks** from GitHub issues at startup using `TaskCreate`. Include the issue number and title in the subject. Use `metadata: {"phase": N}` for phased work.
- **Track dependencies** with `TaskUpdate` (blocks/blockedBy).
- **Assign tasks** by setting the `owner` field to the worker's agent name.
- **Update descriptions** with PR links when workers report back.
- **Mark completed** when the user merges the PR.
- **After compaction**: call `TaskList` to restore full awareness of team state. Read the team config at `~/.claude/teams/{team-name}/config.json` for agent names and roles.

## Team Structure

### Workers (4)

Each worker handles exactly one task at a time. They implement code, create PRs, and address review feedback. One task, one worktree, one agent — always.

### Staff Engineers (2)

Staff engineers review worker plans before the team lead gives final approval. They never write code or create PRs.

**Plan review flow — workers communicate directly with staff engineers:**

1. Worker finishes a plan → sends it directly to both staff engineers.
2. Both staff engineers review independently → send feedback directly to the worker.
3. If either staff engineer requests revisions → worker revises → re-sends to both → loop until both approve.
4. Worker notifies team lead: "Plan approved by both staff engineers, here's the summary."
5. Team lead gives final go/no-go — verifying the plan matches the issue requirements.
6. Only then does the worker proceed to implementation.

**Escalation:** If staff engineers disagree or the review loops more than 3 times, the worker escalates to the team lead to break the deadlock.

## Task Organization

### Phased tasks (e.g., labels `phase:0`, `phase:1`)

- Work through phases sequentially.
- At the start of each phase, fetch all open issues for that phase.
- Analyze dependencies and assign tasks in the safest order.
- A phase is complete only when **ALL** its PRs have been merged by the user.
- **Never assign tasks from a future phase. Idle workers wait.**

### Flat list

- Analyze dependencies across all issues.
- Assign tasks in dependency-safe order.
- Up to 4 tasks in parallel (one per worker).

## Worker Assignment Template

**Send this complete message every time you assign a task. Never abbreviate, never reference "the usual process", never assume the agent remembers anything.**

---

> **Reset**: Discard any previous plan or task context. This is a fresh assignment. Your only active task is what follows.

**Issue**: #[NUMBER] — [TITLE]
**Context source**: [Path to relevant docs, refactoring report, or "read the issue and linked references"]
**Staff engineers**: [NAME-1], [NAME-2]

**Your Workflow — follow these steps in order, skip nothing:**

1. **Create worktree**: Run the `using-git-worktrees` skill to create a fresh worktree from latest `main`.
2. **Investigate**: Read the GitHub issue (`gh issue view [NUMBER]`) and all its comments. Study the relevant codebase areas. Read the context source above.
3. **Plan**: Write a detailed implementation plan. Do NOT write any code yet.
4. **Send plan to staff engineers**: Send your plan directly to both staff engineers listed above. They will review it independently and send feedback back to you.
5. **Revise until approved**: Address staff engineer feedback and re-send until both approve. If you loop more than 3 times or they give conflicting feedback, escalate to the team lead.
6. **Notify team lead**: Once both staff engineers approve, send the plan summary to the team lead for final approval. Wait for the go-ahead.
7. **Implement**: Write the code according to the approved plan.
8. **Self-review**: Run the `ask-claude-review` skill. Address ALL findings — no exceptions.
9. **Push PR**: Run the `push-pr` skill. The PR must include:
   - A clear title referencing the issue
   - A description explaining what changed and why
   - Appropriate labels
10. **Report back**: Tell the team lead the PR is ready for user review.

If the user leaves review comments, the team lead will send you back to address them. Run `pull-review-comments`, fix the issues, and push again. The PR is your responsibility until merged.

After the PR is merged, delete your worktree. Wait for your next assignment.

---

## Review Comment Handling

When the user reports comments on a PR:

1. Dispatch the **same worker** that created the PR — never a different one.
2. Instruct the worker to run `pull-review-comments`, address all feedback, and push fixes.
3. Repeat until the user merges.

## After a PR Is Merged

When the user confirms a PR has been merged:

1. **Pull main immediately**: Run `git pull origin main` in your working directory (the repo root, not a worktree). This ensures local `main` reflects the merged code. Workers create worktrees from local `main` — if it's stale, they start from outdated code.
2. **Mark the task completed** via `TaskUpdate`.
3. **Instruct the worker** to delete its worktree, then assign the next available task.
4. **Check phase completion**: If all tasks in the current phase are merged, advance to the next phase and fetch its issues.

## Critical Rules

| Rule | Detail |
|------|--------|
| No merging | Agents only commit, push, and create PRs. Never merge. |
| No user involvement in planning | Team lead makes all technical decisions. User only reviews code and merges. |
| No team shutdown | Never shut down agents or the team. Only the user can dismiss the team. |
| Strict phase boundaries | Never assign future-phase tasks. All current-phase PRs must be merged first. |
| One task, one worktree, one agent | Always. Delete worktree after PR merged. Fresh from latest `main` for next task. |
| Same agent owns its PR | Dispatch the original worker for review comments, never a different one. |
| Full workflow every assignment | Include the complete worker assignment template. Never assume the agent remembers. |
| Explicit reset on new tasks | Every assignment starts with the reset instruction. |
| Pull main after every merge | Run `git pull origin main` before assigning new tasks. Stale local main = stale worktrees. |
| Direct plan review | Workers send plans to staff engineers directly. Team lead only gets final approval. |
| After compaction | Re-invoke this skill, call `TaskList`, read team config. Then resume. |
