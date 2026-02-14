---
name: push-pr
description: Use when creating or updating a GitHub pull request after commits are ready and pushed. Handles template discovery, smart diff analysis, and label assignment via subagent. Updates existing PRs if one already exists for the branch.
---

# Create Pull Request

## Overview

Creates or updates a GitHub PR using a subagent that analyzes the full diff, fills the repository's PR template intelligently, and assigns appropriate labels. If a PR already exists for the current branch, it updates the title and description instead of creating a new one.

**Core principle:** The main agent NEVER creates or updates the PR directly. All work is delegated to a subagent that has full context.

## Main Agent Responsibility

**Dispatch a subagent using the Task tool. Do nothing else.**

- Do not run any commands
- Do not check anything
- Do not gather context
- Just dispatch the subagent immediately

## Subagent Requirements

### Pre-flight Checks

Before doing anything, verify all conditions. **If ANY check fails (except for existing PR), STOP and return the failure reason to the user.**

1. Current branch is not main/master
2. Commits exist ahead of the base branch
3. Branch is pushed to origin (local and remote are in sync)
4. Check if a PR already exists for this branch (use `gh pr view` to check)
   - If a PR exists: proceed to **update** the existing PR (see "Update Existing PR" section)
   - If no PR exists: proceed to **create** a new PR
5. A PR template exists in the repository (check common locations: `.github/PULL_REQUEST_TEMPLATE.md`, `.github/pull_request_template.md`, `docs/pull_request_template.md`, `PULL_REQUEST_TEMPLATE.md`)

### Context Gathering

Read the **complete** diff and commit history. No truncation, no summarization.

- Full diff between base branch and HEAD
- All commit messages in the branch
- Available repository labels
- The PR template content

### Change Analysis

For each changed file or component:
1. Identify what changed
2. Score relevance (1-5): 5 = core feature change, 1 = trivial/formatting
3. Drop items scored 1-2 from the PR description

**Focus on:** What problem this solves, the main change, notable implementation details.

**Ignore:** Import reordering, whitespace changes, minor unrelated refactors, auto-generated files.

### Label Selection

Retrieve available labels from the repository, then select matching ones:
- Type of change (bug, feature, enhancement, docs, etc.)
- Area affected (if area labels exist)
- Priority/size (if such labels exist)

Only use labels that exist in the repository.

### Template Filling

Fill the repository's PR template:
- Be concise and specific
- Use technical language appropriate for code review
- Reference specific files/functions when relevant
- Include only changes scored 3+
- **NEVER mention AI, automation, or that this was auto-generated**

### Create PR

Create the PR with:
- Concise title (under 72 characters)
- Filled template as body
- Selected labels

### Update Existing PR

If a PR already exists for the branch, update it instead of creating a new one:

1. Use `gh pr edit` to update the PR:
   - `--title` to set the new title
   - `--body` to set the new description (filled template)
2. Update labels if needed using `gh pr edit --add-label` or `--remove-label`
3. The same template filling and change analysis rules apply as for new PRs

### Return Result

Output the PR URL and a one-line summary. Indicate whether the PR was created or updated.

## Red Flags

The subagent should stop and ask the user if:
- Diff is extremely large (>2000 lines) - suggest splitting
- No meaningful changes detected
- Branch appears to be a long-running branch with merge commits

## What This Skill Does NOT Do

- Commit changes
- Push branches
- Merge PRs
- Handle draft PRs (user can request `--draft` flag if needed)
- Close or delete PRs
