# Rule: agent-skills Overrides

The upstream `agent-skills` plugin supplies process; engineering rules supply the quality bar. These overrides apply to Claude commands and Codex skills, including instructions loaded from upstream resources.

## Artifact paths

`<slug>` is the last component of the current worktree path. New artifacts live in `.harness/work/<slug>/`: `spec.md`, `spec-<module>.md`, `plan.md`, and `todo.md`. They are never staged, committed, or included in a PR. Replace upstream `SPEC.md`, `tasks/plan.md`, and `tasks/todo.md` with these paths. Never write a runtime `tasks/` directory.

Before work, inspect only this slug's new directory and legacy `.claude/specs/<slug>/`. Resume existing legacy work there, or explicitly migrate that one worktree's artifacts. If both locations contain process artifacts, stop and resolve the conflict; never silently choose. Never read, overwrite, delete, or count another slug's work. An incomplete-plan check is confined to this worktree's selected directory.

## Build auto

`build auto` (also `build all`) requires `spec.md` in that selected directory. If absent, stop and request `spec`; root `SPEC.md`, `docs/SPEC.md`, arbitrary documentation, and another worktree's spec do not satisfy it. A clean baseline may exclude only this worktree's selected process artifacts; other uncommitted changes must be resolved. Plan if needed, then execute tasks in dependency order with acceptance checks, regression tests, and scoped commits. Never commit the plan. Default `build` handles one pending task.

## Authorization and completion

Preserve prior authorization: a user-approved spec, plan, implementation, or publication does not require repetitive approval. Ask only for a material unresolved decision or a newly unauthorized action. Apply the same acceptance, testing, and completion contracts in both clients. Codex invokes `$spec`, `$plan`, `$build`, `$test`, `$constraints`, `$review`, `$webperf`, `$code-simplify`, and `$ship`; these are distinct from native slash commands. Claude retains its existing plugin commands.

## Published PRs

An authorized publishing workflow may run `gh pr create` and `gh pr ready`. A PR handed to a human must be ready for review. Invoke `shepherd` in the same turn as publication/ready, or `shepherd --stack` after `gh stack submit`/`gh stack link`. Shepherd maintains an already published PR and never readies one itself. Human review and merge remain mandatory; never approve, merge, close, push tags, or push to protected branches.

Arm native monitoring when supported and verify that it started. Codex monitoring lasts only while the task is active, with persisted state for explicit resume; do not claim automatic wake-up or durable monitoring. Always report the PR and actual monitoring status, even if monitoring is unavailable, interrupted, or paused. Publication is followed by maintenance until human merge, terminal closure, or explicit handoff with resumable state.
