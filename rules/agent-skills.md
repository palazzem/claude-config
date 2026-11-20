# Rule: agent-skills Overrides

This file holds every place this configuration replaces an `agent-skills` plugin default. Wherever a plugin skill or command names a path or behaviour listed here, this file wins. Future overrides of the same kind belong here, one section per concern.

## Spec

- `/spec` writes the spec as a Claude Doc named after the change, never `SPEC.md`. Module specs from a capability map are tabs of that doc. Diagrams and charts are Docs widgets.
- The user reviews it through doc comments; answer and edit in the doc.
- Confirmation is the user's unambiguous yes in chat once every comment thread is resolved. It is the run's only approval.
- On confirmation, publish the spec as a GitHub issue labelled `spec` — creating the label where the repository lacks it — titled with the spec's title. Its body is the doc's Markdown with each widget converted to a Mermaid block carrying the same nodes, edges, labels, and data; a widget no Mermaid diagram type carries goes to the user before publishing. A spec over the 65,536-character issue body limit becomes a parent issue holding the capability map, with one sub-issue per module.
- A spec written for an existing issue is a new issue whose body opens with `Solves #<n>`.
- Delete the doc once the issue exists.
- Every success criterion names the command, test, or observation that proves it.

`/plan`, `/build`, `/build auto`, and `harness:deliver` take the spec issue's number as their argument and read it with `gh issue view`. Without one, stop and ask for it.

## Run artifacts

`<run-dir>` is `.claude/runs/<name>/`, `<name>` the spec issue's title in kebab-case: in the main checkout until the first layer opens, in the worktree `.claude/worktrees/<name>` from then on. Agents write and read it; it is never presented to the user, staged, committed, or included in a PR. A run is in flight when its worktree exists.

- Plan → `<run-dir>/plan.md`. Replaces `tasks/plan.md`. It is never presented for approval: the session verifies it against the spec and the run goes on.
- Task list → `<run-dir>/todo.md`. Replaces `tasks/todo.md` as the task list target.
- PR body → `<run-dir>/pr/<branch>.md`, one per layer, written when the layer is built.
- `tasks/` is never created or written by these commands; in `~/.claude` it is Claude Code's own state directory.

A repository whose `.gitignore` lacks `.claude/runs/` gets it in a one-time `chore: ignore agent run artifacts` PR, from its own worktree, before the run writes its first artifact. The run does not wait for that PR to merge.

The check for an existing incomplete plan looks only at `<run-dir>`.

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
- `/build` and `/build auto` open the worktree before the first layer's first task, never earlier, from the main checkout: `git fetch origin` and `git worktree add -b <branch> .claude/worktrees/<name> origin/<trunk>`, `<branch>` being the bottom layer's; move `<run-dir>` to the same relative path inside it; `EnterWorktree` with its path. They commit each task on its layer's branch. In a stack, `gh stack init <branch>` opens the bottom layer and `gh stack add <branch>` each layer above it, before that layer's first task.
- The builder cuts again only where it finds a boundary the plan missed: it ends the layer before the task that opens one and reports `SPLIT` with the row for the Boundaries table. The tasks left become the layer directly above, and the plan is updated to match.
- Size is measured, `git diff --shortstat <base>...HEAD` against the branch the layer builds on, and reported in the PR body and the hand-back. It never cuts.
- A review that still finds a layer too large, or holding two concerns, goes to the user: an oversized PR is an exception.
- The top layer's PR body ends with `Closes #<spec>`, plus `Closes #<n>` for the issue the spec solves; every other layer's ends with `Part of #<spec>`. Both issues close when the whole stack reaches the trunk.
- The hand-back reports each success criterion of the spec as met or unmet, with its evidence.

## `/build auto`

- The spec requirement is satisfied by the spec issue given. `SPEC.md`, `docs/SPEC.md`, and `spec/` are not consulted; when the issue is missing or closed, stop and tell the user to run `/spec`.
- The single checkpoint is the spec's confirmation: the plan is not presented.
- The clean-baseline check runs in the worktree; anything uncommitted there stops the run.
- The plan is not committed before the first task: artifacts never enter a PR.

## Models and effort

Each row's work runs in its subagent type, never inline. None means the subagent type's frontmatter decides.

| Work | Subagent type | Model | Effort |
|---|---|---|---|
| Plan | `harness:planner` | None | None |
| Layer review (`agent-skills:review`) | `agent-skills:code-reviewer` | `fable` | `high` |
| Final review (`agent-skills:ship`) | `agent-skills:code-reviewer` | `fable` | `high` |
| Final review (`agent-skills:ship`) | `agent-skills:security-auditor` | `fable` | `high` |
| Final review (`agent-skills:ship`) | `agent-skills:test-engineer` | `fable` | `high` |
| Web performance audit (`/webperf`) | `agent-skills:web-performance-auditor` | `opus` | `high` |

## `source-driven-development`

- `/build` and `/build auto` invoke it alongside `incremental-implementation` and `test-driven-development`; its own "When NOT to use" decides whether a task needs a lookup.
- Its fetch step runs in the `harness:docs-researcher` agent, never inline: one agent per question, briefed with the library, the version from the dependency file, the question, and what is out of scope.
- One lookup per library, version, and question per session; reuse the earlier report.
- Citations go in the conversation and the PR body, never in code comments.
- A research request from the user uses the same agent and brief, without the skill.

## Other runs

A directory under `.claude/runs/` other than `<run-dir>` is other work queued; a worktree under `.claude/worktrees/` other than this run's is other work in flight. Never read, overwrite, or delete either, and never count them when checking for an existing plan.

## Published PRs

A PR the session publishes is not the end of a command; the merge is. In the same turn as `gh pr create`, `gh pr ready`, `gh stack submit`, or `gh stack link`, invoke the `harness:shepherd` skill. Report the PR to the user only once shepherd's monitor is armed. A draft is still in flight: it is shepherded when `gh pr ready` hands it over.
