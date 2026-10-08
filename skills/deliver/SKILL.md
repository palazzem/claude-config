---
name: deliver
description: Delivers an approved spec as pull requests ready for a human to review and merge, one concern per PR. Use when a spec exists and the user wants it built and published in one run instead of stepping through `/plan`, `/build`, `/code-simplify`, `/review`, and `/ship` by hand, or to resume a delivery that stopped. Not for writing the spec — run `/spec` first — and not for building one task at a time under the user's eye, which is `/build`.
---

# Deliver

## Overview

One workflow takes a spec to pull requests under watch, whatever the number of layers: a delivery is a stack of layers — one PR, one concern each — and every layer is reviewed exactly once, by its position. The human who merges gets small PRs, and no review is paid for twice.

## When to Use

- A spec exists and the change should be built and published in one run.
- A delivery stopped: re-invoke to resume it (see Resuming).
- Not without a spec: stop and tell the user to run `/spec`. Not for a PR already published, which is `shepherd`; not for one task at a time, which is `/build`.

## Definitions

| Term | Meaning |
|---|---|
| `<spec-dir>` | The directory of the spec path given as the skill's argument, in the main checkout. It holds every artifact. |
| `<trunk>` | The repository's default branch. Ranges use `origin/<trunk>`; `gh` commands take `<trunk>`. |
| `<base>` | The branch a layer builds on: the layer below, or `origin/<trunk>` for the bottom layer. |
| `<top>` | The branch of the last layer. |
| Last layer | The top layer of the plan when its build ends with `DONE`. |

## The Run

The session orchestrates: it holds the spec, the plan, and the reports, and never writes the plan or code.

1. **Spec.** Stop without a spec path, or with no file there. The spec, the plan, and the approval need no worktree.
2. **Plan.** Invoke `agent-skills:planning-and-task-breakdown`. A `planner` agent, briefed with the absolute spec, plan, and task list paths, writes the plan. Verify it against the spec — every requirement is met by a task, and no task does work the spec does not ask for — and send what fails back to the same agent, resumed.
3. **Approval.** Present every layer with its title, concern, and tasks, and wait for an unambiguous yes. This is the run's only approval.
4. **Layers.** Bottom first, one at a time: a layer opens only when the checkpoint of the one below is ticked.
   1. **Open.** Before the first layer, and never earlier, `EnterWorktree`: the run's only worktree. Open the layer's branch as One Layer or Several says.
   2. **Build and simplify.** One `layer-builder` agent per layer, never two at once. Brief it with the layer's branch, title, concern, tasks, and `<base>`; the spec, plan, task list, and PR body paths, absolute; and any `docs-researcher` report in hand. It builds, simplifies, and reports `DONE`, `SPLIT`, or `BLOCKED` (see Off the Straight Run).
   3. **Review.** One review, chosen by the layer's position (see Reviews).
   4. **Fix and tick.** See After a Review.
5. **Publish.** See One Layer or Several.
6. **Watch.** See One Layer or Several.
7. **Hand back.** Report the PRs to the user.

## Reviews

| Layer | Review | Range |
|---|---|---|
| Every layer but the last | `agent-skills:review`, once | `<base>...<branch>` |
| The last layer | `agent-skills:ship`, once | `origin/<trunk>...<top>` |

The last layer gets no `agent-skills:review` of its own: a stack of one runs `agent-skills:ship` only. Ranges name branches, never `HEAD`, and the whole-stack range never starts at the local trunk. Both commands run as they are defined: deliver adds no rule to them and removes none.

A review receives three things and nothing else — never a list of things to check or verify, the builder's report, the session's reasoning, or another review's findings:

1. The range.
2. The spec path and the plan path, absolute; for `agent-skills:review`, also the layer's heading in the plan.
3. This line: "The review is read-only: no edits, commits, branch switches, or pushes."
