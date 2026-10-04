---
name: deliver
description: Delivers an approved spec as pull requests a human can review — one concern per PR, each built, simplified, and independently reviewed before it is published, stacked when there is more than one. Use when a spec exists and the user wants it built and published in one run instead of stepping through `/plan`, `/build`, `/code-simplify`, `/review`, and `/ship` by hand, or to resume a delivery that stopped. Not for writing the spec — run `/spec` first — and not for building one task at a time under the user's eye, which is `/build`.
---

# Deliver

## Overview

One run from a spec to pull requests under watch. The session orchestrates: it holds the plan and the reports, and each layer — one PR, one concern — is built, simplified, and reviewed before the next one opens. No layer is built on unreviewed code, and nothing unreviewed reaches a human.

## When to Use

- A spec exists and the change should be built and published.
- Re-invocation is resume — see Resuming.
- No spec: stop and tell the user to run `/spec`. A PR already published: `shepherd`.

## The Run

```text
spec → plan → APPROVAL → layer 1 → layer 2 → … → gate → publish → watch
                         └ open → build → simplify → review → settle
```

`<slug>` is the worktree's name and artifacts live in `.claude/specs/<slug>/`. `<trunk>` is the repository's default branch. `<base>` is the branch a layer builds on: `<trunk>` for the bottom layer, the layer below for every other.

1. **Spec.** `.claude/specs/<slug>/spec.md` exists and `git status --porcelain` shows nothing outside `.claude/specs/<slug>/`. Otherwise stop.
2. **Plan.** With no plan, invoke `agent-skills:planning-and-task-breakdown`. The plan is cut into layers, each naming its branch, its conventional-commit title, its concern, and its tasks.
3. **Approval.** Present every layer and wait for an unambiguous yes; a hedge is not a yes. This is the only gate of the run.
4. **Layers.** Bottom first, one at a time, each through the Layer Loop to its end before the next opens.
5. **Gate.** On the top layer, invoke `agent-skills:ship` over the whole change, `<trunk>...HEAD`. `GO`: publish. `NO-GO`: fix each blocker on the layer that owns the code (see Fixing a Lower Layer) and run the gate again.
6. **Publish.** Never a draft, and never `gh pr edit` afterwards: titles come from the plan, bodies from `.claude/specs/<slug>/pr/<branch>.md`.
   - One layer: `git push -u origin HEAD`, then `gh pr create --title "<title>" --body-file <file>`.
   - A stack: `gh stack push`; per layer, bottom-up, `gh pr create --head <branch> --base <base> --title "<title>" --body-file <file>`; `gh stack link <bottom> … <top>`; verify with `gh stack view --json`.
7. **Watch.** In the same turn, invoke `shepherd`, or `shepherd --stack` for a stack. Report the PRs to the user once its monitor is armed.

## The Layer Loop

**Open.** In a stack, `gh stack init <branch>` opens the bottom layer and `gh stack add <branch>` each one above it. A single layer stays on the worktree's branch.

**Build and simplify.** Who builds depends on the plan:

- *One layer* — the session builds it. For each task, invoke `agent-skills:incremental-implementation` with `agent-skills:test-driven-development`, and `agent-skills:source-driven-development` where a library is involved, one commit per task, applying the split check of the Layers rule at every task boundary. Then invoke `agent-skills:code-simplification` over `git diff <base>...HEAD` and commit the result apart. Then write the PR body.
- *A stack* — one `layer-builder` agent per layer, never two alive at once. Brief it with the spec, plan, and task list paths, the layer's branch, title, concern, and tasks, `<base>`, the PR body path, and any `docs-researcher` report already in hand. The session reads its report, not its diff.

**Review.** One `agent-skills:code-reviewer` agent per layer, in a fresh context. Give it the spec path, the layer's concern and tasks, and the range `<base>...<branch>` — the code, never the builder's account of it.

**Settle.**

| The review holds | Then |
|---|---|
| A Critical or Important finding | The layer's author — the same `layer-builder`, resumed with the findings, or the session — fixes it on the layer's branch, and the reviewer is resumed on the fix commits. |
| The layer is too large, or holds two concerns | Stop for the user: an oversized PR is an exception. |
| Suggestions only, or nothing | The layer is done. Open the next one. |

A finding the author disputes, or one still standing after two fix rounds, goes to the user.

### When a Builder Reports `SPLIT`

The builder ended the layer on a task boundary: what it built is a complete layer, and the tasks left are a new one. Update the plan — the new layer sits directly above, with its own branch, title, and concern — then review the layer as built and open the new one.

A single layer the session is building splits the same way: `gh stack init <branch>` adopts the worktree's branch as the bottom layer, `gh stack add <new-branch>` opens the next, and from there the plan is a stack.

### When a Builder Reports `BLOCKED`

Stop and put its question to the user. After the answer, resume the same builder with it.

## Fixing a Lower Layer

A gate blocker belongs to the layer that owns the code, never to the top of the stack:

```bash
gh stack checkout <branch>
# the layer's author fixes, tests, and commits here
gh stack rebase --upstack --no-trunk
gh stack top
```

Run the full test suite on the top layer afterwards. The next gate run reviews the fix.

## Resuming

- A plan with no ticked task was never approved: present it.
- A plan with unticked tasks: continue at the first layer that has one, skipping Approval.
- Every task ticked and no PR: Gate.
- A PR on the branch: `shepherd`.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The layers are small; build them all, then review once." | A fix in a lower layer rebases every layer above it, and those were built on the unreviewed code. Each layer settles before the next opens. |
| "I wrote this layer and I know it is fine." | The author's context is what a review must not share. The reviewer gets the range, not the story. |
| "Review first, simplify after — that is the order the plugin lists." | Whatever changes after the review is unreviewed. Simplify, then review. |
| "Only one task is left after the `SPLIT`; have the builder finish it here." | The builder ended the layer on the Layers rule. The task left is a layer: open it. |
| "The reviewer calls it too large, but it is one concern." | An oversized PR is an exception, and exceptions are the user's to grant. |
| "Every layer passed review; the gate is ceremony." | A layer review never sees two layers at once. The gate is the only look at the whole change. |
| "These two layers don't touch; run both builders at once." | They share one worktree and one stack. One builder at a time. |
| "Publish drafts now and finish the fixes on the PR." | A PR handed to a human is ready for review. Publishing follows the gate. |

## Red Flags

- A layer opened while the one below it has a Critical or Important finding standing.
- Two `layer-builder` agents alive at once, or one briefed with more than one layer.
- A reviewer briefed with the builder's report or reasoning.
- In a stack, layer code written by the session instead of the layer's builder.
- A commit on a layer after its last review that neither the reviewer nor the gate saw.
- `gh pr create` before the gate says `GO`; `--draft`; `gh stack submit` for a layer of more than one commit; `gh pr edit` to repair a title or a body.
- The PRs reported to the user before `shepherd`'s monitor is armed.

## Verification

Before reporting the run:

- [ ] Every layer in the plan has a branch, and `git log --oneline <base>..<branch>` shows only its tasks, its simplification, and its fixes.
- [ ] Every layer's review ended with no Critical or Important finding, and covered its fix commits.
- [ ] The gate returned `GO` on the final state of the top layer.
- [ ] Every PR is open and not a draft, with the plan's title and the body file's text; for a stack, `gh stack view --json` lists every layer with its PR.
- [ ] Nothing under `.claude/specs/<slug>/` was staged or committed.
- [ ] `shepherd`'s monitor is armed.
