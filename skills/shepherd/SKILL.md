---
name: shepherd
description: Present a run's PR and watch it to its terminal — flip draft → ready when the gate holds, wake the builder on human comments and merge drift, detect merge/close, print the run report, clean up. No arguments; it finds the run's PR from the current worktree's branch.
---

# Shepherd

Take a run's PR from gated presentation to a reported terminal. Invoking the skill is the whole interface: the current worktree's branch names the PR (`gh pr view`), and the PR body names the input issue, the confirmed type — which fixes the lane — the design-doc path (full lane), and the session ID. The PR is the run record; everything the gate and the report need is readable from it.

- No PR on the current branch → stop and report; never guess a subject.
- Re-invocation is resume: skip what already holds — a ready PR goes straight to Watch; a merged or closed one straight to Terminal (a run abandoned before its report still gets one).

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
2. **Read** — `watch-pr.sh watch <pr> '<watermark>' --once` prints everything standing now: unmarked activity past the watermark, a terminal, a degraded merge state. Handle every line not already handled this run before arming.
3. **Arm** — Monitor tool, persistent (a human reply can take days; no timeout may kill the watch), command `watch-pr.sh watch <pr> '<watermark>'` with the step-1 watermark. It exits after printing its first qualifying events; stdout is qualifying events only — every line wakes the session; diagnostics live on stderr.

The script's filter, for both modes: `COMMENT`, `REVIEW`, `THREAD_REPLY` — unmarked human activity on any surface, with one carve-out: empty-body reviews never fire, because GitHub wraps every API thread reply in an empty-body review under our own account (a human's body-less approval lands in the same skip, stderr-logged); `MERGED`, `CLOSED`; `BEHIND`, `DIRTY` — merge readiness drifted (transition-only while armed, current-state in the read, so arming while already degraded still surfaces the drift). Marked activity, CI, and UNKNOWN merge state never fire — the builder owns CI at push time.

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
2. Print the run report in the session from `${CLAUDE_SKILL_DIR}/run-report-template.md`. Sources: the PR (body, commits, threads, reviews), marked comments on the input issue, and this session's own record.
3. Clean up — no confirmation, no post-checks, every failure ignored: `ExitWorktree(action: "remove", discard_changes: true)`, then unconditionally from the main checkout `git worktree remove --force <worktree>` and `git branch -D <branch>` (the tool removes only what `EnterWorktree` created this session; the git pair covers the rest). Merged or closed: one `git push origin --delete <branch>`. Failed: the remote branch and its open PR are pushed work and stay — only user-approved next steps touch GitHub (AC-15). The design doc stays at its recorded path in the main checkout — the user's record, the user's cleanup.
4. Sync the main checkout. Merged: `git pull -p`, picking up the merged commit and pruning remote-tracking refs for branches GitHub deleted — only when the checkout sits on the default branch; on any other branch `git fetch --prune` and say so — never pull into a branch the user has checked out. Closed: `git fetch --prune`. A pull the working tree refuses: report it, don't stash.

## Never

- Flip a PR to ready with any gate clause unmet, or flip a ready PR back to draft.
- Write code, push, answer threads, or fix findings when a builder wrote the code — shepherd gates, watches, wakes, records rulings, reports, cleans; the builder does everything else. Standalone — no run record in the PR body, the session wrote the code — the session handles comments and drift itself.
- Check merge state, tree diff, ancestry, or the remote branch after a `MERGED` or `CLOSED` fire — the watcher's word is final; one `gh pr view` is the whole follow-up.
- Ask before discarding the worktree at a merged or closed terminal, or verify the cleanup afterwards — discard, delete, move on.
- Hand-write a watcher or filter PR activity outside `watch-pr.sh` — it is the read and the monitor.
- Wake on marked comments or CI events, or run two monitors at once.
- Reuse a builder on a comment wake or a post-ruling resume — those are fresh spawns; only a drift fire may resume the implementing builder.
- Clean up before the report prints, or end at a terminal without printing it.
- Touch the remote branch or PR at a FAILED terminal without the user's approval — pushed work is safe.
- Post or persist the run report anywhere — in-session only.
