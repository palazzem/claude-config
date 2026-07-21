---
name: push-pr
description: Use when creating or updating a GitHub pull request after commits are ready and pushed. Creates draft PRs when passed --draft or when invoked from the implement chain. Dispatches a shepherd agent that analyzes the diff, fills the repo PR template when present (otherwise a structured Problem / Changes / Verification body), and assigns labels. Updates an existing PR's description in place when the implementation has drifted from what it says.
argument-hint: "[base-branch] (optional - defaults to the repository default branch) | [--draft] (create the PR as a draft) | optional verification block from the caller (command + expected output) | optional caller notes that must appear in the body (spec link, size justification, evidence artifact)"
---

# Create Pull Request

Resolve the inputs below, then dispatch one `shepherd` agent (Agent tool) with them. Do nothing else - no commands, no context gathering, no checks. The shepherd owns the whole procedure and the model it runs on; never pass a model at the call site.

A shepherd is spawned fresh for every invocation and holds no state between them. Whoever invokes this skill dispatches it directly: the builder for a PR it is implementing, the main agent for a standalone invocation.

## Inputs

| Input | Resolution |
|---|---|
| Repository and base branch | Base branch from the argument if given, otherwise the repository default branch (`gh repo view --json defaultBranchRef -q .defaultBranchRef.name`). |
| Checkout path | The worktree or checkout the commits live in. |
| Mode | `create` when no PR exists for the branch; `refresh` when one exists and the caller reports the description no longer matches the implementation. The shepherd re-checks this itself with `gh pr view`. |
| Draft mode | On when `--draft` is passed or when invoked from the implement chain - the chain always creates drafts, and the review loop flips them open later with `gh pr ready`. |
| Verification block | Optional, passed by the caller (the implement chain forwards each PR's exact command and expected output). When provided, the body must carry it under `## Verification`. |
| Caller notes | Facts the caller must get into the body that the diff cannot supply: the spec link when the spec lives on GitHub, a justification when the change exceeds the builder's soft size cap, a reference to a visual-evidence artifact. The builder owes these; it supplies them here rather than composing body prose itself. |

## Result

Relay the shepherd's report: the PR URL, created or refreshed, draft state, what it preserved rather than regenerated, whether it changed the title, whether the verification section is stale, and any assumption it flagged. Relay the title decision in particular - it is the signal that a human's rename was or was not overwritten, and it is worthless if it stops here. If its pre-flight failed, relay the failure reason unchanged - do not attempt the work yourself.
