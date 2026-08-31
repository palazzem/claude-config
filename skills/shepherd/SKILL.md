---
name: shepherd
description: Shepherds a run's pull request from gated draft to its terminal state — merged, closed, no-change, or failed — and prints the run report. Use when the current worktree's branch has a PR and the review panel has posted on it, and again on re-invocation to resume an interrupted watch. Not for writing code, answering review threads, or fixing findings — the builder owns those. Takes no arguments.
---

# Shepherd

## Overview

Take a run's PR from gated presentation to a reported terminal. Invoking the skill is the whole interface: the current worktree's branch names the PR (`gh pr view`), and the PR body names the input issue, the confirmed type — which fixes the lane — the design-doc path (full lane), and the session ID. The PR is the run record; everything the gate and the report need is readable from it.

## When to Use

- The current worktree's branch has a PR and the panel has posted on it — the gate decides whether it presents.
- Re-invocation is resume: skip what already holds — a ready PR goes straight to Watch; a merged or closed one straight to Terminal (a run abandoned before its report still gets one).
- No PR on the current branch → stop and report; never guess a subject.
- Not for the builder's work. When a builder wrote the code, shepherd never writes code, pushes, answers threads, or fixes findings — it gates, watches, wakes, records rulings, reports, cleans. Standalone — no run record in the PR body, the session wrote the code — the session handles comments and drift itself.

## Gate

Flip draft → ready (`gh pr ready`) exactly when all three hold — the flip is the "presented to the user" moment:

1. **Panel complete** — the panel's marked angle-selection comment is on the PR and every angle it selects has its marked review posted. A selected angle without a review blocks the flip: some reviews is not the panel.
2. **Every finding thread answered** — fixed (builder resolved it), contested (open, with a marked reply), or deferred (stated reason + tracking issue). The gate checks that answers exist, never weighs them — contested threads are the user's to rule on. One unanswered marked thread blocks the flip.
3. **CI green** — whatever checks the repo runs on the PR head.

Checks still in flight → wait for them to settle; the gate reads settled state only. A clause failing after that means an upstream guarantee broke: report exactly which clause and stop for the user — never flip anyway, never repair it yourself.

## Watch

One monitor at a time, re-armed after every fire, until terminal. One watcher: `${CLAUDE_SKILL_DIR}/scripts/watch-pr.sh` runs both the pre-arm read and the armed monitor — one filter, so the read and the monitor cannot disagree. Never hand-write a replacement.

Every arm — Watch entry and every re-arm — is one fixed sequence, watermark first:

1. **Watermark** — `watch-pr.sh baseline <pr>`. Captured before the read, so an event landing mid-sequence double-fires later and is deduped — never silently lost.
2. **Read** — `watch-pr.sh watch <pr> '<watermark>' --once` prints everything standing now: unmarked activity past the watermark, a terminal, a degraded merge state. Handle every line not already handled this run before arming. A read that exits nonzero was incomplete — re-run it; never arm on one.
3. **Arm** — Monitor tool, persistent (a human reply can take days; no timeout may kill the watch), command `watch-pr.sh watch <pr> '<watermark>'` with the step-1 watermark. It exits after printing its first qualifying events. stdout is qualifying events only, one JSON object per line — `{"event":"COMMENT","id":…,"login":…}`, `{"event":"MERGED"}` — and every line wakes the session; diagnostics live on stderr.

The script's filter, for both modes, by `event`: `COMMENT`, `REVIEW`, `THREAD_REPLY` — unmarked human activity on any surface, with one carve-out: empty-body reviews never fire, because GitHub wraps every API thread reply in an empty-body review under our own account (a human's body-less approval lands in the same skip, stderr-logged); `MERGED`, `CLOSED`; `BEHIND`, `DIRTY` — merge readiness drifted (transition-only while armed, current-state in the read, so arming while already degraded still surfaces the drift). Marked activity, CI, and UNKNOWN merge state never fire — the builder owns CI at push time.

On a `COMMENT`/`REVIEW`/`THREAD_REPLY` fire, the agent that wrote the code handles it — the PR body says which. Harness run record in the body (session ID, issue, lane) → a builder wrote it → wake a fresh `builder` (Agent tool, `subagent_type: "builder"`): the spawn prompt carries the worktree path, issue number, lane, confirmed type, design-doc path (full lane), and the PR number — no pr-body template on a wake: the PR already exists — and tells it to read the PR itself, handle the new activity, and check its CI after any push. No run record → standalone: the session wrote the code, so the session handles the activity itself — read the PR, fix or answer, push, check CI after any push; a design question in a comment goes to the user directly. Then re-arm.

On a `BEHIND`/`DIRTY` fire, wake the run's builder to update the branch — rebase protocol and post-push CI are its own rules. Prefer resuming the builder that implemented the run (SendMessage) while it is still reachable this session — it holds conflict context; otherwise spawn fresh with the same run context and the mission "the base moved / conflicts — update the branch." Standalone — no run record, no builder machinery — the session updates the branch itself, as it handles comments.

Then handle the builder's return and re-arm:

- `DONE` → re-arm.
- `HALT` → put the question and options to the user; after the ruling, full lane → amend the design doc in place, fast lane → post the ruling as a `**Claude Harness**` comment on the input issue; then a fresh builder resumes. Record every halt and ruling for the report.
- `FAILURE` → Needs-input with the builder's report verbatim; only user-approved next steps touch GitHub. The user resumes the run or ends it — an ended run is the FAILED terminal.
- `NO-CHANGE` → propose the conclusion with its evidence; on the user's confirmation, post the findings as a marked comment on the input issue → NO-CHANGE terminal.

A `MERGED` or `CLOSED` fire is final and is Terminal — no merge-state, tree-diff, ancestry, or remote-branch check follows it. Closed-unmerged is the user's emergency stop: the abandonment terminal, reported like any other.

## Terminal

Report first, cleanup second — always both, at every terminal (merged, closed, no-change, failed).

1. Merged or closed: one `gh pr view` — the only PR read after the fire — for the report's facts and to confirm the state the watcher printed. A state that contradicts the watcher: print both, stop for the user, clean nothing.
2. Print the run report in the session from the template below. Sources: the PR (body, commits, threads, reviews), marked comments on the input issue, and this session's own record. All five sections, in that order, always present — a section with nothing to report says `none`. Lessons come exclusively from the human's feedback during this run — never from agent output, and nothing to do with auto-memory.
3. Clean up — no confirmation, no post-checks, every failure ignored: `ExitWorktree(action: "remove", discard_changes: true)`, then unconditionally from the main checkout `git worktree remove --force <worktree>` and `git branch -D <branch>` (the tool removes only what `EnterWorktree` created this session; the git pair covers the rest). Merged or closed: one `git push origin --delete <branch>`. Failed: the remote branch and its open PR are pushed work and stay — only user-approved next steps touch GitHub. The design doc stays at its recorded path in the main checkout — the user's record, the user's cleanup.
4. Sync the main checkout. Merged: `git pull -p`, picking up the merged commit and pruning remote-tracking refs for branches GitHub deleted — only when the checkout sits on the default branch; on any other branch `git fetch --prune` and say so — never pull into a branch the user has checked out. Closed: `git fetch --prune`. A pull the working tree refuses: report it, don't stash.

### Run report

Replace each italic placeholder; keep the section order.

```markdown
**Run report — #<issue> <title> — <MERGED | CLOSED | NO-CHANGE | FAILED>**

- **Lane:** _confirmed type → lane, e.g. `spec → full (confirmed at /deliver)`_
- **Stages:** _the stages this run actually executed, in order, with loop counts where one repeated, e.g. `design (2 skeptic rework loops) → implement → review-panel → shepherd`_
- **Halts:** _one entry per halt, `·`-separated: what fired → how the user ruled; `none` when the run never halted_
- **Review loops:** _panel: rounds, findings count, dispositions — n fixed, n contested (who prevailed), n deferred → #tracking-issue · human: rounds, comments, disposition_
- **Lessons** (from human feedback only): _one entry per lesson: what the human corrected → the takeaway; `none` when the human changed nothing_
```

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "Only a flaky check is red; the rest holds — flip it." | The gate is all three clauses on settled state. A failing clause means an upstream guarantee broke: name the clause and stop for the user. Never flip with a clause unmet, never repair it yourself, never flip a ready PR back to draft. |
| "This finding is a one-line fix; pushing it is faster than waking a builder." | When a builder wrote the code, shepherd writes none: it gates, watches, wakes, records rulings, reports, cleans. A shepherd fix has no builder rules behind it — no rebase protocol, no post-push CI check. |
| "A quick `gh api` call is simpler than the script for this one read." | `watch-pr.sh` is the read and the monitor — one filter, so they cannot disagree. A hand-written read applies a second filter and silently drops or duplicates events. |
| "The read showed nothing; skip the baseline and arm." | The watermark is captured before the read so an event landing mid-sequence double-fires and is deduped rather than lost. Arming on an older watermark reopens that window. |
| "A second monitor on CI would catch failures sooner." | CI, marked activity, and UNKNOWN merge state never wake the session — the builder owns CI at push time. Two monitors double-fire; one at a time, re-armed after every fire. |
| "The watcher printed MERGED; let me confirm the merge state and the remote branch." | The watcher's word is final. One `gh pr view` for the report's facts is the whole follow-up; a state that contradicts it is printed and handed to the user, not investigated. |
| "The builder that implemented this is still reachable; reuse it for the comment." | Comment wakes and post-ruling resumes are fresh spawns. Only a drift fire may resume the implementing builder — it holds the conflict context a fresh one lacks. |
| "Remove the worktree first; the report can be written from memory." | Report first, cleanup second, always both. Cleanup ignores every failure, so a run whose report waits on it can end unreported. |
| "The worktree has uncommitted changes — better ask before discarding." | At a merged or closed terminal: discard without confirmation and without post-checks. The PR is the record; the worktree is not. |
| "The run failed; deleting the remote branch keeps the repo tidy." | Pushed work is safe. At a FAILED terminal nothing touches the remote branch or the PR without the user's approval. |
| "The report is useful — post it on the PR or save it in the repo." | The run report is printed in the session only. Never posted, committed, or saved. |
| "The main checkout is on a feature branch; pull anyway to pick up the merge." | Never pull into a branch the user has checked out. Off the default branch: `git fetch --prune` and say so. A pull the working tree refuses is reported, not stashed around. |

## Red Flags

- `gh pr ready` before the panel's angle-selection comment and every selected review are on the PR, or while a check is still in flight.
- A commit, push, thread reply, or `gh pr edit` from the shepherd session on a PR whose body carries a run record.
- `gh api` or `gh pr view` polling written inline instead of `watch-pr.sh`; a read without a baseline first; an arm whose watermark is not the one just captured.
- Two monitors alive for the same PR, or a monitor armed with a timeout.
- Any merge-state, tree-diff, ancestry, or remote-branch check after a `MERGED` or `CLOSED` event beyond the single `gh pr view`.
- A builder resumed on a comment wake or a post-ruling resume; a fresh builder spawned on a drift fire while the implementing one is still reachable.
- Worktree removal or branch deletion output before the run report, or a question asked before discarding at a merged or closed terminal.
- `git push --delete` or a PR close at a FAILED terminal.
- A run report missing a section, sourcing a Lesson from agent output, or posted or written anywhere.

## Verification

At every terminal, before ending:

- [ ] The terminal is established: the watcher printed `MERGED` or `CLOSED` and the single `gh pr view` agrees, or the user ended the run (FAILED) or confirmed the conclusion (NO-CHANGE).
- [ ] The run report printed in the session with all five sections in order, `none` where empty, and every Lessons entry traces to a human correction made during this run.
- [ ] Every halt and ruling recorded during the run appears in the report.
- [ ] Cleanup ran after the report, in order — worktree removal, local branch deletion, and on merged or closed the remote branch deletion — with failures ignored and no post-check.
- [ ] FAILED: no command touched the remote branch or the PR.
- [ ] The main checkout synced — `git pull -p` on the default branch after a merge, `git fetch --prune` otherwise — and a skipped or refused pull was reported.
- [ ] No monitor is armed for the PR, and the report was neither posted nor saved anywhere.
