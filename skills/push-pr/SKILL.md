---
name: push-pr
description: Use when creating or updating a GitHub pull request after commits are ready and pushed. Creates draft PRs when passed --draft or when invoked from the implement chain. Fills the repo PR template when present, otherwise generates a structured body (Problem / Changes / Verification). Handles smart diff analysis and label assignment via subagent. Updates existing PRs in place if one already exists for the branch.
argument-hint: "[base-branch] (optional - resolved from the repo profile when omitted) | [--draft] (create the PR as a draft) | optional verification block from the caller (command + expected output)"
---

# Create Pull Request

Creates or updates a GitHub PR via a `general-purpose` subagent (Agent tool, `model: "sonnet"`). The main agent resolves the inputs below, dispatches the subagent with them, and does nothing else — no commands, no context gathering, no checks.

## Inputs

| Input | Resolution |
|---|---|
| Base branch | Argument if given. Otherwise read `base_branch` from the repo profile - the per-repo JSON file at `~/.claude/profiles/<owner>-<repo>.json`; if absent, ask the user once (question selector) and write it back to the profile file. Unattended with no profile value: use the repository default branch (`gh repo view --json defaultBranchRef`) and flag the assumption in the result. |
| Draft mode | On when `--draft` is passed or when invoked from the implement chain (the chain always creates drafts: PRs stay draft while machines iterate; the review loop flips them open later with `gh pr ready`). |
| Verification block | Optional, passed by the caller (e.g., the implement chain forwards each stacked PR's verification: exact command + expected output). When provided, the body MUST contain it under a `## Verification` heading. |

## Steps (Subagent)

1. **Pre-flight checks** — if any check fails, STOP and return the failure reason.
   - Current branch is not the base branch
   - Commits exist ahead of the base branch (`git log <base-branch>..HEAD`)
   - Branch is pushed and in sync with origin
   - Check if a PR already exists (`gh pr view`); note whether to create or update

2. **Read context** — read everything in full, no truncation.
   - `git diff <base-branch>...HEAD` — complete diff
   - `git log <base-branch>..HEAD --pretty=format:"%h %s"` — all commit messages
   - `gh label list --limit 100 --json name,description` — available labels
   - `.github/pull_request_template.md` — read if present; its absence is NOT a failure

3. **Analyze changes** — for each changed file/component:
   - Identify what changed by reading the diff
   - Score relevance (1-5): 5 = core change, 1 = trivial/formatting
   - Keep only items scored 3+ for the PR description
   - Focus on: what problem this solves, the main change, notable implementation details
   - Ignore: import reordering, whitespace, minor unrelated refactors, auto-generated files

4. **Compose the body**
   - Template present: fill `.github/pull_request_template.md` with the analysis.
   - No template: generate a clean structured body with exactly these sections: `## Problem` (what this solves and why), `## Changes` (the main change plus notable details), `## Verification` (how to confirm it works).
   - Caller passed a verification block: include it verbatim under `## Verification` in either mode; if the template has no matching section, append the heading after the filled template.

5. **Select labels** — pick labels from the repository's label list that match the change type, area, and priority/size. Skip labels if none match.

6. **Create or update PR**
   - **New PR:** `gh pr create --base <base-branch> --title "..." --body "..." --label "..."`, adding `--draft` when draft mode is on
   - **Existing PR:** `gh pr edit --title "..." --body "..."` and `gh pr edit --add-label "..."` if labels changed; never toggle an existing PR's draft/ready state — that transition belongs to the review loop

7. **Return result** — output the PR URL, whether it was created or updated, draft or open, and any flagged assumptions (e.g., base branch defaulted in an unattended run).

## Rules

- **Read-only.** Never run tests, linters, type checks, or any quality validation. CI handles that.
- **Never mention AI**, automation, or that the PR was auto-generated.
- **No emoji** anywhere in titles, bodies, or labels.
- **Only use labels that exist** in the repository.
- **Title under 72 characters.** Be concise and specific.
- **Never** commit, push, merge, close, mark ready, or delete anything.
