---
name: deliver
description: Delivers an approved spec as pull requests ready for a human to review and merge, one concern per PR. Use when a spec exists and the user wants it built and published in one run instead of stepping through `/plan`, `/build`, `/code-simplify`, `/review`, and `/ship` by hand, or to resume a delivery that stopped. Not for writing the spec — run `/spec` first — and not for building one task at a time under the user's eye, which is `/build`.
---

# Deliver

## Overview

One workflow takes a spec to pull requests under watch, whatever the number of layers: a delivery is a stack of layers, one PR and one concern each, so the human who merges gets small PRs.

## When to Use

- A spec exists and the change should be built and published in one run.
- A delivery stopped: re-invoke to resume it (see Resuming).
- Not without a spec: stop and tell the user to run `/spec`. Not for a PR already published, which is `harness:shepherd`; not for one task at a time, which is `/build`.

## Definitions

| Term | Meaning |
|---|---|
| `<spec>` | The spec issue's number, given as the skill's argument. |
| `<name>` | The spec issue's title in kebab-case. |
| `<run-dir>` | `.claude/runs/<name>/`: in the main checkout until the first layer opens, in the run's worktree from then on. It holds every artifact, is never staged or committed, and goes with the worktree when `harness:shepherd` removes it. |
| `<trunk>` | The repository's default branch. Ranges use `origin/<trunk>`; `gh` commands take `<trunk>`. |
| `<base>` | The branch a layer builds on: the layer below, or `origin/<trunk>` for the bottom layer. |
| `<top>` | The branch of the last layer. |
| Last layer | The top layer of the plan when its build ends with `DONE`. |

## Workflow

The session orchestrates: it holds the spec, the plan, and the reports, and never writes the plan or code.

1. **Spec.** Stop without a spec issue, or when it is closed. Read it with `gh issue view <spec>`. Its confirmation was the run's only approval: nothing is presented to the user before the hand-back. With a worktree `.claude/worktrees/<name>`, the run is in flight (see Resuming); without one, the plan happens in the main checkout, with no worktree.
2. **Plan.** Invoke `agent-skills:planning-and-task-breakdown`. A `harness:planner` agent, briefed with `<spec>` and the plan and task list paths, writes the plan. Verify four things, and send what fails back to the same agent, resumed: every requirement is met by a task; no task does work the spec does not ask for; every boundary between adjacent layers has a row in the Boundaries table; every row's fact holds — the kinds are as stated, and an `outcome`'s consumer exists in the spec or the code.
3. **Layers.** Bottom first, one at a time: a layer opens only when the checkpoint of the one below is ticked.
   1. **Open.** Before the first layer, and never earlier, from the main checkout and in this order: `git fetch origin`, then `git worktree add -b <branch> .claude/worktrees/<name> origin/<trunk>`, `<branch>` being the bottom layer's; move `<run-dir>` to the same relative path inside that worktree, creating the parent directory first; `EnterWorktree` with the worktree's path. It is the run's only worktree, and every artifact is read and written there from then on. Open the layer's branch as One Layer or Several says.
   2. **Build and simplify.** One `harness:layer-builder` agent per layer, never two at once. Brief it with the layer's branch, title, concern, tasks, and `<base>`; `<spec>`; the plan, task list, and PR body paths, all in `<run-dir>`; and any `harness:docs-researcher` report in hand. It builds, simplifies, and reports `DONE`, `SPLIT`, or `BLOCKED` (see Off the Straight Run).
   3. **Review.** One review, chosen by the layer's position (see Reviews).
   4. **Fix and tick.** See After a Review.
4. **Publish.** Never a draft: `<title>` comes from the plan, `<body>` is `<run-dir>/pr/<branch>.md`, ending with the issue references the Layers rule names. The commands are in One Layer or Several.
5. **Watch.** In the same turn, invoke `harness:shepherd`: one watch covers every layer published.
6. **Hand back.** Once the monitor is armed, report to the user: each success criterion of the spec, met or unmet, with its evidence; the PRs, each with the size its builder reported; the final review's ship decision; what was fixed after it; the commits made after it, which no reviewer saw; any recommended fix not made, and why; any layer added after it; and, per layer, every simplification its builder logged — from its simplify step and from every review round — applied with its commit, or left with the reason.

## One Layer or Several

A stack of one is a stack in concept, but `gh-stack` needs two layers. This table is the only place the run tells one layer from several.

| Step | One layer | Two or more |
|---|---|---|
| Open | The worktree's branch is the layer. | `gh stack init <branch>` for the bottom layer, `gh stack add <branch>` for each one above. When one layer becomes two — its builder reports `SPLIT` — `gh stack init <branch>` first adopts the worktree's branch as the bottom layer. |
| Publish | `git push -u origin <branch>`, then `gh pr create --base <trunk> --title "<title>" --body-file <body>`. | `gh stack push`; per layer, bottom-up, `gh pr create --head <branch> --base <below> --title "<title>" --body-file <body>`, `<below>` being the layer below, or `<trunk>` for the bottom layer; `gh stack link <bottom> … <top>`; verify with `gh stack view --json`. |

## Reviews

| Layer | Review | Range |
|---|---|---|
| Every layer but the last | The layer review, once: `agent-skills:code-review-and-quality` in an `agent-skills:code-reviewer` agent | `<base>...<branch>` |
| The last layer | The final review, once: `agent-skills:shipping-and-launch`, with its `code-reviewer`, `security-auditor`, and `test-engineer` agents started in one turn and merged into the ship decision | `origin/<trunk>...<top>` |

The last layer gets no layer review of its own: a stack of one runs the final review only. Ranges name branches, never `HEAD`, and the whole-stack range never starts at the local trunk. Each review runs as its skill and agents define it: deliver adds no rule and removes none.

A review receives three things and nothing else — never a list of things to check or verify, the builder's report, the session's reasoning, or another review's findings:

1. The range.
2. `<spec>` and the plan path, in `<run-dir>`; for the layer review, also the layer's heading in the plan.
3. This line: "The review is read-only: no edits, commits, branch switches, or pushes."

## After a Review

**Each review runs once.** This is deliberate: a human reviews every PR. No reviewer is resumed and no review runs a second time, also after fixes; Resuming holds the one exception. To restore a re-check after fixes, change this rule and nothing else.

| After | Fix | Leave |
|---|---|---|
| The layer review | Critical and Required findings, and every finding that simplifies | Other Optional and Nit findings |
| The final review | Blockers, recommended fixes, and every finding that simplifies, each on the layer that owns the code | Acknowledged risks |

A finding simplifies when its fix removes code, a module, a mode, a thread, a dependency, or a configuration entry, with no loss of what the spec requires, whatever severity the reviewer gave it. The builder applies it as its simplify step would, or leaves it with the reason, and logs it either way.

1. Check out the layer that owns the code: `gh stack checkout <branch>` when it is below the top.
2. That layer's builder, resumed with the findings and the name of the review that raised them — a fresh one with the layer's brief when it cannot be resumed — fixes, tests, and commits.
3. Below the top: `gh stack rebase --upstack --no-trunk`, resolving a conflict with the `gh-stack:gh-stack` skill's conflict workflow.
4. Run the full test suite on the fixed layer and on every layer above it, `gh stack up` from one to the next.
5. After the final review, its rollback plan becomes the rollback section of the PR bodies: each step goes in the body of the layer whose code it undoes.
6. Tick the checkpoint of the layer reviewed. The run moves on.

Stop for the user on a layer the review reports as too large or as holding two concerns, and on a finding the builder disputes or cannot fix. A `NO-GO` alone is not a stop: its findings are fixed and the PRs are published.

## Off the Straight Run

| Event | Then |
|---|---|
| The builder reports `SPLIT` | What it built is a complete layer. Add the new layer to the plan directly above it — branch, title, kind, concern, tasks, checkpoint — and the row the builder reported to the Boundaries table. The layer that split is no longer the last: it gets the layer review, and the new layer is built next. |
| `BLOCKED` on a documentation lookup | Run a `harness:docs-researcher` agent with the library, version, and question; resume the builder with its report. |
| `BLOCKED` on a change that belongs to a lower layer | Make it there with steps 1 to 4 of After a Review, return to the builder's branch, and resume the builder. |
| `BLOCKED` on anything else | Put its question to the user; resume the builder with the answer. |
| The builder reports deviations from the plan | Not a stop. |
| A layer is added after the final review | Publish it with no review and name it in the hand-back. |

## Resuming

| State | Then |
|---|---|
| No worktree `.claude/worktrees/<name>` | The run has not started. A plan in `<run-dir>` in the main checkout: verify it and go on from Layers. |
| The worktree exists | It is in flight: find it with `git worktree list` and `EnterWorktree` with its path, never a second one. Continue, without asking again, at the first layer whose checkpoint is unticked. |
| That layer has unticked tasks | A fresh `harness:layer-builder` with the layer's brief builds them and simplifies; the run goes on from Review. |
| That layer has every task ticked | Run its review and go on from After a Review. |
| Every checkpoint ticked | With no PR, Publish. With a PR on the branch, Watch. |

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The spec is short and the layer is small; the session can write both." | Planning and building fill the context the run needs for every layer after. A `harness:planner` writes the plan, a `harness:layer-builder` the layer. |
| "The layers are small; build them all, then review." | A fix in a lower layer rebases every layer built on it. A layer's checkpoint is ticked before the next opens. |
| "Review first, simplify after — that is the order the plugin lists." | The layer has one review: it reads the code that ships. Simplify, then review. |
| "Only one task is left after the `SPLIT`; have the builder finish it here." | The builder ended the layer at its boundary. The task left is a layer: open it. |
| "This layer will run long; cut it now so the PRs stay small — or the review calls it too large, but it is one concern." | Size is a fact, not a reason: a boundary needs a kind change or an outcome. The size goes in the hand-back, and an oversized PR is the user's exception to grant. |
| "These two layers don't touch; run both builders at once." | They share one worktree. One builder at a time. |
| "Resume the reviewer to confirm the fix, to be safe." | After a fix, the full test suite guards against regressions. |
| "A code review on the last layer first — or a layer review then the final review on a single PR." | The final review is the last layer's review. Anything before it reads the same code twice. |
| "Tell the reviewer what to check; it saves time." | The reviewer's agent and skill decide the method. A check list narrows the review to what the session already thought of. |
| "It is only Optional; the reviewer said so." | A finding that simplifies is fixed whatever its label: severity measures risk, not cost, and a simpler design is nearly always labelled Optional. |
| "`NO-GO`: stop and ask the user." | A `NO-GO` is findings. Fix them and publish; the decision is in the hand-back. |
| "Publish drafts now and finish the fixes on the PR." | A PR handed to a human is ready for review. Fix, then publish. |

## Red Flags

- A second worktree, or two `harness:layer-builder` agents running at once.
- The plan presented to the user, or a wait for approval after the spec's confirmation.
- A range ending in `HEAD` or starting at the local trunk.
- `gh stack submit` for a layer of more than one commit.

## Verification

- [ ] The plan was written by a `harness:planner` and verified against the spec by the session, and every layer was built, and every finding fixed, by a `harness:layer-builder`.
- [ ] Every boundary between adjacent layers has a row in the plan's Boundaries table, the rows added after a `SPLIT` included, and no layer was cut on size.
- [ ] Every layer has a ticked checkpoint and a PR body file, and `git log --oneline <base>..<branch>` shows only its tasks, its simplification, and its fixes.
- [ ] The run shows one layer review per layer but the last and one final review, each briefed with its three inputs, the final review's three reviewers started in one turn.
- [ ] After the last fix, the full test suite passed on every layer from the fixed one to the top.
- [ ] Every PR is open and not a draft, with the plan's title and the body file's text; the top layer's body closes `<spec>`, and every other layer's names it.
- [ ] No worktree existed before the first layer opened, `<run-dir>` is in the worktree and no longer in the main checkout, and `git log --name-only origin/<trunk>..<top>` and `git status --porcelain` show nothing under it.
- [ ] `harness:shepherd`'s monitor is armed, and the hand-back holds every item of step 6.
