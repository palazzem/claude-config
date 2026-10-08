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
5. **Publish.** Never a draft, and never `gh pr edit` afterwards: titles come from the plan, bodies from `<spec-dir>/pr/<branch>.md`. The commands are in One Layer or Several.
6. **Watch.** In the same turn, invoke `shepherd` as One Layer or Several says.
7. **Hand back.** Once the monitor is armed, report to the user: the PRs; the `agent-skills:ship` decision as returned; what was fixed after it; the commits made after it, which no reviewer saw; any recommended fix not made, and why; any layer added after it.

## One Layer or Several

A stack of one is a stack in concept, but `gh-stack` needs two layers. This table is the only place the run tells one layer from several.

| Step | One layer | Two or more |
|---|---|---|
| Open | The worktree's branch is the layer. | `gh stack init <branch>` for the bottom layer, `gh stack add <branch>` for each one above. When one layer becomes two — its builder reports `SPLIT` — `gh stack init <branch>` first adopts the worktree's branch as the bottom layer. |
| Publish | `git push -u origin <branch>`, then `gh pr create --base <trunk> --title "<title>" --body-file <file>`. | `gh stack push`; per layer, bottom-up, `gh pr create --head <branch> --base <below> --title "<title>" --body-file <file>`, `<below>` being the layer below, or `<trunk>` for the bottom layer; `gh stack link <bottom> … <top>`; verify with `gh stack view --json`. |
| Watch | `shepherd` | `shepherd --stack` |

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

## After a Review

**Each review runs once.** This is deliberate: a human reviews every PR. No reviewer is resumed and no review command is invoked a second time, also after fixes; Resuming holds the one exception. To restore a re-check after fixes, change this rule and nothing else.

| After | Fix | Leave |
|---|---|---|
| `agent-skills:review` | Critical and Required findings (`/review` names the second tier Important) | Optional, Nit, Suggestion |
| `agent-skills:ship` | Blockers and recommended fixes, each on the layer that owns the code | Acknowledged risks |

1. Check out the layer that owns the code: `gh stack checkout <branch>` when it is below the top.
2. That layer's builder, resumed with the findings, fixes, tests, and commits.
3. Below the top: `gh stack rebase --upstack --no-trunk`, resolving a conflict with the `gh-stack` skill's conflict workflow.
4. Run the full test suite on the fixed layer and on every layer above it, `gh stack up` from one to the next.
5. Tick the checkpoint of the layer reviewed. The run moves on.

Stop for the user on a layer the review reports as too large or as holding two concerns, and on a finding the builder disputes or cannot fix. A `NO-GO` alone is not a stop: its findings are fixed and the PRs are published.

## Off the Straight Run

| Event | Then |
|---|---|
| The builder reports `SPLIT` | What it built is a complete layer. Add the new layer to the plan directly above it, with its branch, title, concern, tasks, and checkpoint. The layer that split is no longer the last: it gets `agent-skills:review`, and the new layer is built next. |
| `BLOCKED` on a documentation lookup | Run a `docs-researcher` agent with the library, version, and question; resume the builder with its report. |
| `BLOCKED` on a change that belongs to a lower layer | Make it there with steps 1 to 4 of After a Review, return to the builder's branch, and resume the builder. |
| `BLOCKED` on anything else | Put its question to the user; resume the builder with the answer. |
| The builder reports deviations from the plan | Not a stop. |
| A layer is added after `agent-skills:ship` | Publish it with no review and name it in the hand-back. |

## Resuming

| The plan shows | Then |
|---|---|
| Nothing ticked | It was never approved: verify it and present it. |
| A ticked task | The worktree exists: `EnterWorktree` with the path of the one holding the plan's branches, never a second one. Continue, without asking again, at the first layer whose checkpoint is unticked. |
| That layer has unticked tasks | A fresh `layer-builder` with the layer's brief builds them and simplifies; the run goes on from Review. |
| That layer has every task ticked | Run its review: the one case where a review may repeat. |
| Every checkpoint ticked | With no PR, Publish. With a PR on the branch, Watch. |
