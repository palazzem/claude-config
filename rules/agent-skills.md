# Rule: agent-skills Overrides

The `agent-skills` plugin supplies the process; `CLAUDE.md` supplies the bar. This file holds every place this configuration replaces a plugin default, so the bar stays free of plugin mechanics. Wherever a plugin skill or command names a path or behaviour listed here, this file wins. Future overrides of the same kind belong here, one section per concern.

## Artifact paths

`<spec-dir>` is `.claude/specs/<name>/`, `<name>` a kebab-case name for the change: in the main checkout until the first layer opens, in the worktree `.claude/worktrees/<name>` from then on. Every process artifact lives there and is never staged, committed, or included in a PR unless the user asks. A spec present in the main checkout is not started; one that is absent is in flight in the worktree named after it.

- Spec → `<spec-dir>/spec.md`. Replaces `SPEC.md` at the repository root wherever `/spec`, `/plan`, `/build`, or `/build auto` names it. Module specs from a capability map sit alongside it as `<spec-dir>/spec-<module>.md`.
- Plan → `<spec-dir>/plan.md`. Replaces `tasks/plan.md`.
- Task list → `<spec-dir>/todo.md`. Replaces `tasks/todo.md` as the task list target.
- PR body → `<spec-dir>/pr/<branch>.md`, one per layer, written when the layer is built.
- `tasks/` is never created or written by these commands; in `~/.claude` it is Claude Code's own state directory.

`/plan`, `/build`, `/build auto`, and `deliver` take the spec path as their argument; `<spec-dir>` is its directory. Without one, stop and ask for it.

The check for an existing incomplete plan looks only at `<spec-dir>`.

## Layers

A plan is cut into layers, and a layer is one PR. Layers replace the phases in the plan template of `planning-and-task-breakdown`: tasks nest under the layer that ships them, and the checkpoint after a layer is its review, ticked once the review leaves nothing that blocks a merge.

A layer holds one concern:

- One conventional-commit subject names what the layer lets a user, a caller, or the layer above do once it lands, without an "and". A subject that names only the component — improve, update, rework, prepare X — names no concern.
- The build and the tests pass with only the layers below it merged.
- A preparatory refactor, a mechanical change — rename, move, formatting, dependency bump — and a behaviour change never share a layer.

A boundary between two adjacent layers exists for one of two reasons, and the plan states which:

- **kind**: the kind changes — refactor or mechanical on one side, behaviour on the other.
- **outcome**: the layer below reaches an outcome that a consumer uses the day it merges — a command, a test, a document, or a person that the spec or the code names — and the layer above starts another. The boundary names that consumer and what it uses.

A boundary for any other reason, size included, is one layer too many: two adjacent layers that would pass the three rules as one are one layer.

Each layer in the plan names its branch, its conventional-commit title, its kind — `refactor`, `mechanical`, or `behaviour` — its concern in one sentence, and the layer it builds on. The concern of a layer of several tasks is the outcome none of them reaches alone. No layer carries a size estimate: the size of a change is not knowable before the code exists.

The plan ends with a **Boundaries** table, one row per boundary between adjacent layers, columns `Between | Reason | Fact`. The reason is `kind` or `outcome`; the fact is the two kinds, or the consumer and what it uses the day the layer below merges.

- A plan with more than one layer always ships as a `gh-stack` stack, bottom first in dependency order — never one branch carrying several concerns. A single layer ships from the worktree's own branch.
- `/build` and `/build auto` open the worktree before the first layer's first task, never earlier, from the main checkout: `git fetch origin` and `git worktree add -b <branch> .claude/worktrees/<name> origin/<trunk>`, `<branch>` being the bottom layer's; move `<spec-dir>` to the same relative path inside it; `EnterWorktree` with its path. They commit each task on its layer's branch. In a stack, `gh stack init <branch>` opens the bottom layer and `gh stack add <branch>` each layer above it, before that layer's first task.
- The builder cuts again only where it finds a boundary the plan missed: it ends the layer before the task that opens one and reports `SPLIT` with the row for the Boundaries table. The tasks left become the layer directly above, and the plan is updated to match.
- Size is measured, `git diff --shortstat <base>...HEAD` against the branch the layer builds on, and reported in the PR body and the hand-back. It never cuts.
- A review that still finds a layer too large, or holding two concerns, goes to the user: an oversized PR is an exception.

## `/build auto`

- The spec requirement is satisfied by the spec path given. `SPEC.md`, `docs/SPEC.md`, and `spec/` are not consulted; when the file is missing, stop and tell the user to run `/spec`.
- The clean-baseline check runs in the worktree; anything uncommitted there stops the run.
- The plan is not committed before the first task: artifacts never enter a PR.

## Models and effort

Each row's work runs in its subagent type, never inline. None means the subagent type's frontmatter decides.

| Work | Subagent type | Model | Effort |
|---|---|---|---|
| Plan | `planner` | None | None |
| Layer review (`agent-skills:review`) | `agent-skills:code-reviewer` | `opus` | `high` |
| Final review (`agent-skills:ship`) | `agent-skills:code-reviewer` | `opus` | `high` |
| Final review (`agent-skills:ship`) | `agent-skills:security-auditor` | `opus` | `high` |
| Final review (`agent-skills:ship`) | `agent-skills:test-engineer` | `opus` | `high` |
| Web performance audit (`/webperf`) | `agent-skills:web-performance-auditor` | `opus` | `high` |

## `source-driven-development`

- `/build` and `/build auto` invoke it alongside `incremental-implementation` and `test-driven-development`; its own "When NOT to use" decides whether a task needs a lookup.
- Its fetch step runs in the `docs-researcher` agent, never inline: one agent per question, briefed with the library, the version from the dependency file, the question, and what is out of scope.
- One lookup per library, version, and question per session; reuse the earlier report.
- Citations go in the conversation and the PR body, never in code comments.
- A research request from the user uses the same agent and brief, without the skill.

## Other specs

A directory under `.claude/specs/` other than `<spec-dir>` is other work queued; a worktree under `.claude/worktrees/` other than this run's is other work in flight. Never read, overwrite, or delete either, and never count them when checking for an existing plan.

## Published PRs

A PR the session publishes is not the end of a command; the merge is. In the same turn as `gh pr create`, `gh pr ready`, `gh stack submit`, or `gh stack link`, invoke the `shepherd` skill. Report the PR to the user only once shepherd's monitor is armed. A draft is still in flight: it is shepherded when `gh pr ready` hands it over.
