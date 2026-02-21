---
name: push-pr
description: Use when creating or updating a GitHub pull request after commits are ready and pushed. Handles template discovery, smart diff analysis, and label assignment via subagent. Updates existing PRs if one already exists for the branch.
args: <base-branch> (required) — the target branch for the PR (e.g., main, develop, dev)
---

# Create Pull Request

Creates or updates a GitHub PR via a `general-purpose` subagent (`model: "sonnet"`). The main agent dispatches the subagent and does nothing else — no commands, no context gathering, no checks. If no base branch arg is provided, ask the user before dispatching.

## Steps (Subagent)

1. **Pre-flight checks** — if any check fails, STOP and return the failure reason.
   - Current branch is not the base branch
   - Commits exist ahead of the base branch (`git log <base-branch>..HEAD`)
   - Branch is pushed and in sync with origin
   - PR template exists at `.github/pull_request_template.md`
   - Check if a PR already exists (`gh pr view`); note whether to create or update

2. **Read context** — read everything in full, no truncation.
   - `git diff <base-branch>...HEAD` — complete diff
   - `git log <base-branch>..HEAD --pretty=format:"%h %s"` — all commit messages
   - `gh label list --limit 100 --json name,description` — available labels
   - `.github/pull_request_template.md` — PR template

3. **Analyze changes** — for each changed file/component:
   - Identify what changed by reading the diff
   - Score relevance (1-5): 5 = core change, 1 = trivial/formatting
   - Keep only items scored 3+ for the PR description
   - Focus on: what problem this solves, the main change, notable implementation details
   - Ignore: import reordering, whitespace, minor unrelated refactors, auto-generated files

4. **Fill template and select labels** — fill the PR template with the analysis, then pick labels from the repository's label list that match the change type, area, and priority/size. Skip labels if none match.

5. **Create or update PR**
   - **New PR:** `gh pr create --base <base-branch> --title "..." --body "..." --label "..."`
   - **Existing PR:** `gh pr edit --title "..." --body "..."` and `gh pr edit --add-label "..."` if labels changed

6. **Return result** — output the PR URL and a one-line summary. State whether it was created or updated.

## Rules

- **Read-only.** Never run tests, linters, type checks, or any quality validation. CI handles that.
- **Template required.** If `.github/pull_request_template.md` is missing, fail immediately.
- **Never mention AI**, automation, or that the PR was auto-generated.
- **Only use labels that exist** in the repository.
- **Title under 72 characters.** Be concise and specific.
- **Never** commit, push, merge, close, or delete anything.
