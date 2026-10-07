---
name: deliver
description: Delivers an approved spec as pull requests a human can review — one concern per PR, each built, simplified, and independently reviewed before it is published, stacked when there is more than one. Use when a spec exists and the user wants it built and published in one run instead of stepping through `/plan`, `/build`, `/code-simplify`, `/review`, and `/ship` by hand, or to resume a delivery that stopped. Not for writing the spec — run `/spec` first — and not for building one task at a time under the user's eye, which is `/build`.
---

# Deliver

## Overview

One run from a spec to pull requests under watch. The session orchestrates: it holds the spec, the plan, and the reports, and delegates the work that would fill its context. Each layer — one PR, one concern — is built, simplified, and reviewed before the next one opens, so no layer is built on unreviewed code and nothing unreviewed reaches a human.

## When to Use

- A spec exists and the change should be built and published.
- Re-invocation is resume — see Resuming.
- No spec: stop and tell the user to run `/spec`. A PR already published: `shepherd`, or `shepherd --stack` for a stack.

## The Run

```text
spec → plan → APPROVAL → layer 1 → layer 2 → … → gate → publish → watch
                         └ open → build → simplify → review → settle
```

`<slug>` is the worktree's name and artifacts live in `.claude/specs/<slug>/`. `<trunk>` is the repository's default branch. `<base>` is the branch a layer builds on: `<trunk>` for the bottom layer, the layer below for every other.

1. **Spec.** `.claude/specs/<slug>/spec.md` exists and `git status --porcelain` shows nothing outside `.claude/specs/<slug>/`. Otherwise stop.
2. **Plan.** The session reads the spec and invokes `agent-skills:planning-and-task-breakdown`, to know what a plan must hold. With no plan yet, a `planner` agent writes it: briefed with the spec, plan, and task list paths, it writes both files and reports the layers. The session then verifies the plan against the spec — every requirement is met by a task, and no task does work the spec does not ask for — and sends what fails back to the same agent, resumed. The plan is cut into layers, each naming its branch, its conventional-commit title, its concern, its tasks, and a checkpoint.
3. **Approval.** Present the plan as a summary — every layer with its title, concern, and tasks — and wait for an unambiguous yes; a hedge is not a yes. This is the only approval the run asks for.
4. **Layers.** Bottom first, one at a time. A layer goes through the whole Layer Loop — built, simplified, reviewed, settled — before the next one opens.
5. **Gate.** On the top layer, invoke `agent-skills:ship` over the whole change, `<trunk>...HEAD`. `GO` with no recommended fix: publish. Otherwise every blocker and every recommended fix is fixed on the layer it belongs to (see Fixing a Lower Layer), and the gate runs once more. That second run decides: `GO` publishes, with any recommended fix it still lists reported to the user alongside the PRs; `NO-GO` goes to the user.
6. **Publish.** Never a draft, and never `gh pr edit` afterwards: titles come from the plan, bodies from `.claude/specs/<slug>/pr/<branch>.md`.
   - One layer: `git push -u origin HEAD`, then `gh pr create --title "<title>" --body-file <file>`.
   - A stack: `gh stack push`; per layer, bottom-up, `gh pr create --head <branch> --base <base> --title "<title>" --body-file <file>`; `gh stack link <bottom> … <top>`; verify with `gh stack view --json`.
7. **Watch.** In the same turn, invoke `shepherd`, or `shepherd --stack` for a stack. Report the PRs to the user once its monitor is armed.

## Delegation

The session decides and orchestrates; a subagent does every piece of work that would fill the session's context. The session never writes the plan or a layer's code itself, and it reads reports, not diffs.

| Work | Runs in |
|---|---|
| Reading the spec, verifying the plan, asking for approval | The session |
| Writing the plan | A `planner` subagent |
| Opening, splitting, and rebasing layers; ticking checkpoints | The session |
| Building, simplifying, and fixing a layer | A `layer-builder` subagent — always, one per layer, also when the plan has a single layer |
| Reviewing a layer | An `agent-skills:code-reviewer` subagent, in a fresh context, at effort `xhigh` |
| Documentation lookups | A `docs-researcher` subagent |
| The gate | The session invokes `agent-skills:ship`: its personas review as subagents, and the session merges their reports |
| Publishing and watching | The session |

## The Layer Loop

A layer runs these four steps in order, and the next layer opens only when the last of them is done. Nothing is built on a layer whose review has not settled: every later fix to a lower layer rebases all the layers above it.

1. **Open.** In a stack, `gh stack init <branch>` opens the bottom layer and `gh stack add <branch>` each one above it. A single layer stays on the worktree's branch.
2. **Build and simplify.** One `layer-builder` agent builds the layer, never two running at once. Brief it with the spec, plan, and task list paths, the layer's branch, title, concern, and tasks, `<base>`, the PR body path, and any `docs-researcher` report already in hand. Every later change to the layer goes back to the same builder, resumed; one that cannot be resumed is replaced by a fresh builder with the same brief, which skips the tasks already ticked.
3. **Review.** One `agent-skills:code-reviewer` agent, spawned with model `opus` and effort `xhigh`, reviews the layer in a fresh context. Give it the spec path, the layer's concern and tasks, and the range `<base>...<branch>` — the code, never the builder's account of it. Ask it also to measure the range and to report a layer that is too large, or that holds a second concern.
4. **Settle.** Act on the review until nothing in it blocks a merge, then tick the layer's checkpoint in the plan. Only then does the next layer open.

| The review holds | Then |
|---|---|
| A Critical or Required finding | The layer's builder, resumed with the findings, fixes it on the layer's branch, and the reviewer is resumed on the fix commits. |
| The layer is too large, or holds two concerns | Stop for the user: an oversized PR is an exception. Granted, the layer goes on through this table; refused, it is split as the user directs. |
| Optional or Nit findings only, or nothing | The layer is settled. |

A finding the builder disputes, or one still standing after two fix rounds, goes to the user.

### When a Builder Reports `SPLIT`

The builder ended the layer on a task boundary: what it built is a complete layer, and the tasks left are a new one. Update the plan — the new layer sits directly above, with its own branch, title, concern, and checkpoint — then review and settle the layer as built before opening the new one.

When the plan had a single layer, `gh stack init <branch>` first adopts the worktree's branch as the bottom layer; `gh stack add <new-branch>` then opens the next, and from there the plan is a stack.

### When a Builder Reports `BLOCKED`

| It is blocked on | Then |
|---|---|
| A documentation lookup it could not run | Run the `docs-researcher` agent with its library, version, and question, and resume the builder with the report. |
| A change that belongs to a lower layer | Fix the lower layer (see Fixing a Lower Layer), return to the builder's branch, and resume it. |
| Anything else | Stop and put its question to the user; resume the builder with the answer. |

## Fixing a Lower Layer

A fix belongs to the layer that owns the code, never to the top of the stack:

```bash
gh stack checkout <branch>
# the layer's builder, resumed, fixes, tests, and commits here
gh stack rebase --upstack --no-trunk
gh stack up
```

Repeat `gh stack up` to the top, running the full test suite on every layer on the way: each layer passes on its own, not only the top. The session resolves a conflict in the rebase with the `gh-stack` skill's conflict workflow.

No fix goes unreviewed: the layer's reviewer is resumed on the fix commits before anything builds on them, and a fix made for the gate is reviewed by the gate's next run.

## Resuming

- A plan with nothing ticked was never approved: verify it and present it.
- Otherwise continue, without asking again, at the first layer whose checkpoint is unticked: a fresh `layer-builder` with the layer's brief builds its unticked tasks and simplifies, then the layer is reviewed and settled.
- Every checkpoint ticked and no PR: Gate.
- A PR on the branch: `shepherd`, or `shepherd --stack` for a stack.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The spec is short; the session can write the plan." | Planning reads the codebase, and that fills the context the run needs for every layer after it. A `planner` writes the plan; the session verifies it. |
| "It is a single small layer; the session can build it." | Layer building always runs in a `layer-builder`. The session's context is for the plan and the reports. |
| "The layers are small; build them all, then review once." | A fix in a lower layer rebases every layer above it, and those were built on the unreviewed code. Each layer settles before the next opens. |
| "The builder wrote this layer and its report is clean." | The author's context is what a review must not share. The reviewer gets the range, not the story. |
| "Review first, simplify after — that is the order the plugin lists." | Whatever changes after the review is unreviewed. Simplify, then review. |
| "Only one task is left after the `SPLIT`; have the builder finish it here." | The builder ended the layer at its boundary. The task left is a layer: open it. |
| "The reviewer calls it too large, but it is one concern." | An oversized PR is an exception, and exceptions are the user's to grant. |
| "Every layer passed review; the gate is ceremony." | A layer review never sees two layers at once. The gate is the only look at the whole change. |
| "These two layers don't touch; run both builders at once." | They share one worktree and one stack. One builder at a time. |
| "Publish drafts now and finish the fixes on the PR." | A PR handed to a human is ready for review. Publishing follows the gate. |

## Red Flags

- The session writing the plan, building a layer, or fixing a finding itself.
- A layer opened while the checkpoint of the one below it is unticked.
- Two `layer-builder` agents running at once, or one briefed with more than one layer.
- A reviewer briefed with the builder's report or reasoning.
- A commit on a layer after its last review that neither the reviewer nor the gate saw.
- `gh pr create` before the gate says `GO` or the user accepts its blockers; `--draft`; `gh stack submit` for a layer of more than one commit; `gh pr edit` to repair a title or a body.
- The PRs reported to the user before `shepherd`'s monitor is armed.

## Verification

Before reporting the run:

- [ ] The plan was written by a `planner` and verified against the spec by the session, and every layer was built by a `layer-builder`.
- [ ] Every layer in the plan has a branch, a ticked checkpoint, and a PR body file, and `git log --oneline <base>..<branch>` shows only its tasks, its simplification, and its fixes.
- [ ] Every layer's review ended with no Critical or Required finding, covered its fix commits, and settled before the next layer opened.
- [ ] The gate's last run returned `GO` on the final state of the top layer, or the user accepted its blockers; recommended fixes it still listed are in the report to the user.
- [ ] After the last lower-layer fix, the full test suite passed on every layer from that one to the top.
- [ ] Every PR is open and not a draft, with the plan's title and the body file's text; for a stack, `gh stack view --json` lists every layer with its PR.
- [ ] Nothing under `.claude/specs/<slug>/` was staged or committed.
- [ ] `shepherd`'s monitor is armed.
