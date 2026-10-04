# Rule: agent-skills Overrides

The `agent-skills` plugin supplies the process; `CLAUDE.md` supplies the bar. This file holds every place this configuration replaces a plugin default, so the bar stays free of plugin mechanics. Wherever a plugin skill or command names a path or behaviour listed here, this file wins. Future overrides of the same kind belong here, one section per concern.

## Artifact paths

`<slug>` is the name of the worktree the session runs in: the last component of its path. Every process artifact lives under `.claude/specs/<slug>/` inside that worktree and is never staged, committed, or included in a PR.

- Spec → `.claude/specs/<slug>/spec.md`. Replaces `SPEC.md` at the repository root wherever `/spec`, `/plan`, `/build`, or `/build auto` names it. Module specs from a capability map sit alongside it as `.claude/specs/<slug>/spec-<module>.md`.
- Plan → `.claude/specs/<slug>/plan.md`. Replaces `tasks/plan.md`.
- Task list → `.claude/specs/<slug>/todo.md`. Replaces `tasks/todo.md` as the task list target.
- PR body → `.claude/specs/<slug>/pr/<branch>.md`, one per layer, written when the layer is built.
- `tasks/` is never created or written by these commands; in `~/.claude` it is Claude Code's own state directory.

The check for an existing incomplete plan looks only at `.claude/specs/<slug>/`.

## Layers

A plan is cut into layers, and a layer is one PR. Layers replace the phases in the plan template of `planning-and-task-breakdown`: tasks nest under the layer that ships them, and the checkpoint after a layer is its review.

A layer holds one concern:

- One conventional-commit subject names it without an "and".
- The build and the tests pass with only the layers below it merged.
- A preparatory refactor, a mechanical change — rename, move, formatting, dependency bump — and a behaviour change never share a layer.
- Each independently testable slice is its own layer. When two cuts are plausible, take the finer one.

Each layer in the plan names its branch, its conventional-commit title, its concern in one sentence, and the layer it builds on. It carries no size estimate: the size of a change is not knowable before the code exists, so the planner cuts by concern and the builder cuts again.

- A plan with more than one layer always ships as a `gh-stack` stack, bottom first in dependency order — never one branch carrying several concerns. A single layer ships from the worktree's own branch.
- `/build` and `/build auto` commit each task on its layer's branch. In a stack, `gh stack init <branch>` opens the bottom layer and `gh stack add <branch>` each layer above it, before that layer's first task.
- Whoever builds a layer measures it at every task boundary with `git diff --shortstat <base>...HEAD`, and ends the layer there when the next task is a second concern, or when the layer has passed about 300 changed lines — generated files and lockfiles aside — with tasks still to build. The tasks left become a new layer directly above, and the plan is updated to match.
- A review that still finds a layer too large, or holding two concerns, goes to the user: an oversized PR is an exception.

## `/build auto`

- The spec requirement is satisfied by `.claude/specs/<slug>/spec.md`. `SPEC.md`, `docs/SPEC.md`, and `spec/` are not consulted; when the file is missing, stop and tell the user to run `/spec`.
- The clean-baseline check treats uncommitted files under `.claude/specs/<slug>/` as the expected planning artifacts; anything else uncommitted stops the run.
- The plan is not committed before the first task: artifacts never enter a PR.

## `source-driven-development`

- `/build` and `/build auto` invoke it alongside `incremental-implementation` and `test-driven-development`; its own "When NOT to use" decides whether a task needs a lookup.
- Its fetch step runs in the `docs-researcher` agent, never inline: one agent per question, briefed with the library, the version from the dependency file, the question, and what is out of scope.
- One lookup per library, version, and question per session; reuse the earlier report.
- Citations go in the conversation and the PR body, never in code comments.
- A research request from the user uses the same agent and brief, without the skill.

## Other slugs

`.claude/specs/<other-slug>/` is another agent's work in flight. Never read, overwrite, or delete it, and never count it when checking for an existing plan.

## Published PRs

A PR the session publishes is not the end of a command; the merge is. In the same turn as `gh pr create` or `gh pr ready`, invoke the `shepherd` skill; in the same turn as `gh stack submit` or `gh stack link`, invoke `shepherd --stack`. Report the PR to the user only once shepherd's monitor is armed. A draft is still in flight: it is shepherded when `gh pr ready` hands it over.
