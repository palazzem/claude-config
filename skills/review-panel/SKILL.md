---
name: review-panel
description: Run the multi-persona review panel on any pull request - one the implement chain is building or any foreign PR. Spawns one reviewer agent per selected persona (once per PR, blind and parallel), verifies findings with the skeptic, and posts one batched inline review. On later rounds the same reviewers are woken to re-check. Invoked standalone via /review-panel or by name from the implement skill.
argument-hint: "[pr-number-or-url] (optional) - defaults to the current branch's PR"
---

# Review Panel

One panel per PR, spawned ONCE. Reviewers and the skeptic are persistent agents: the first round spawns them; every later round wakes the SAME agents via SendMessage, so their context - the diff they read, the findings they made - survives and nothing is re-derived. Never re-spawn a panel that already exists for a PR; wake it.

Hard rails: never merge, never close, never change PR state (draft/ready) - the caller owns lifecycle. The GitHub review event is always `COMMENT`. Every autonomously posted body begins with the exact line `**Harness automated comment**`. No emoji anywhere.

## Round 1

### 1. Resolve the target

`$ARGUMENTS` as PR number or URL, else the current branch's PR (`gh pr view --json number,url`). Gather: head SHA, base branch, changed file list, commit log, full diff, repo visibility (`gh repo view --json visibility`). If the change was built from a spec (linked in the PR body, in a tracking issue, or supplied by the caller), note its location - it is passed to the personas that need design intent.

### 2. Select the personas

All personas live in this skill's `personas/` directory, one file each:

| Persona | Lens | When |
|---|---|---|
| `fresh-eyes` | first-look senior engineer: bugs, edge cases, error handling, clarity | ALWAYS |
| `breaker` | failure hypotheses: malformed input, dependencies down, scale, rollout, observability | ALWAYS |
| `tests` | do the tests protect the code; TDD evidence for bugfixes | ALWAYS |
| `standards` | house rules: comments, docstrings, suppressions, DRY, naming | ALWAYS |
| `correct-design` | is this the right design; conformance to the approved spec | any non-trivial code diff (skip only for pure formatting, renames, comment or doc edits, config or dependency bumps) |
| `security-audit` | deep security: data-flow trace and concrete exploit per finding | any executable source touched (application or library code, scripts, CI workflows, IaC, templates rendering external input) |
| `database` | data stores, migrations, query cost, schema coordination | diff touches its domain |
| `api-contracts` | contract shapes, serialization, deploy-window coexistence | diff touches its domain |
| `concurrency` | races, ordering, idempotency of side effects | diff touches its domain |
| `frontend` | UI states, client/server validation split, reactivity, accessibility | diff touches its domain |
| `infra` | deployment config, IaC, rollout safety, monitoring | diff touches its domain |
| `reliability` | retries, timeouts, resource bounds, cache invalidation | diff touches its domain; default fill |
| `security-breadth` | broad OWASP-style sweep; second security lens | diff touches a security surface; default fill |

Domain matching goes by WHAT the code does, not filenames. Floor: at least two domain personas per run - backfill with `security-breadth`, then `reliability`. Include `security-breadth` whenever the diff touches a security surface even if other domains matched: its overlap with `security-audit` is deliberate, and when both flag the same issue independently, that dual-lens convergence is the panel's highest-value signal - call it out. Record selected and skipped personas in the report.

### 3. Spawn the panel - blind and parallel

One `reviewer` agent per selected persona, all in a SINGLE message of parallel Agent tool calls, each with the stable name `reviewer-<persona>-pr<number>`. Each prompt contains only:

1. The absolute path of its persona file, with the instruction to read and adopt it.
2. The repo, PR number, and head SHA - the reviewer fetches the diff itself.
3. For `correct-design` (and any persona whose file asks for design intent): the spec location and the instruction to fetch it before reviewing.

Blindness is mandatory: no prompt mentions other reviewers, a panel, verification, or skeptics. Each reviewer is told it is the sole reviewer of this change. A reviewer that fails or returns garbage is relaunched once; if it fails again, mark coverage `partial: <persona>` in the report - never silently.

### 4. Verify with the skeptic

Collect every reviewer's findings block. Dedup findings that hit the same file within 5 lines or state the same concern; a merged finding lists every persona that flagged it, sorts first, and is highlighted - convergence raises priority but never skips verification. Then spawn ONE `skeptic` agent named `skeptic-pr<number>` and send it every CRITICAL, HIGH, and MEDIUM finding with provenance and severity STRIPPED - no persona tag, no severity label, nothing that anchors authority. LOW and NIT findings post unverified. Refuted findings are dropped from posting and listed in the report with the refutation reason.

### 5. Post one batched review

Post exactly ONE GitHub review per round (github-comment skill, batch mode, event `COMMENT`): inline comments for findings with a line anchor, the review body for `general` findings plus the round summary - verdict, coverage, convergences. Per-finding body:

```
**Harness automated comment**

[<persona>] <SEVERITY>

<finding body>

Verification: <skeptic-sustained | unverified (LOW/NIT)>
```

Verdict (wording only, never a request-changes event): BLOCKED = any surviving CRITICAL; REQUEST CHANGES = any surviving HIGH; APPROVE WITH NITS = only MEDIUM/LOW/NIT; APPROVE = nothing actionable.

**Public repos:** security findings never carry exploit detail inline - post a neutral marker (persona, severity, one sentence that a security-relevant issue was identified here, details withheld on a public repository) and put the full finding in the terminal report only. Never post absolute operational numbers; use ratios.

### 6. Report

Always end with a terminal report to the caller: selected and skipped personas, coverage status, every finding with its disposition (posted / refuted + reason / redacted, with the unredacted detail here), convergences, verdict. If posting was impossible (no comment access), the report carries everything the review would have posted.

## Later rounds - wake, never re-spawn

When the caller asks for a re-check (fixes were pushed, or a standalone user asks again):

1. Wake each existing reviewer via SendMessage: "PR #N changed since your review (new head <sha>). Verify each of your findings was addressed or validly rebutted, and review the changes as new material." Wake the skeptic the same way with the fresh CRITICAL/HIGH/MEDIUM findings.
2. Steps 4-6 repeat on the results. A finding rebutted by the builder with evidence the reviewer accepts is closed; one the reviewer restates goes back in the round's review.
3. The caller owns round counting and any cap; this skill runs the round it is asked for.
