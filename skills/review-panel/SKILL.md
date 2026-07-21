---
name: review-panel
description: Run the multi-persona review panel on any pull request - one the implement chain is building or any foreign PR. Spawns one reviewer agent per selected persona (once per PR, blind and parallel), verifies findings with the skeptic, and posts one batched inline review. On later rounds the same reviewers are woken to re-check. Invoked standalone via /review-panel or by name from the implement skill.
argument-hint: "[pr-number-or-url] (optional) - defaults to the current branch's PR"
---

# Review Panel

One panel per PR, spawned once. Reviewers and the skeptic are persistent agents: the first round spawns them; every later round wakes the same agents via SendMessage, so their context - the diff they read, the findings they made - survives and nothing is re-derived. Never re-spawn a panel that already exists for a PR; wake it.

Hard rails: never merge, never close, never change PR state (draft/ready) - the caller owns lifecycle. The GitHub review event is always `COMMENT`. Every autonomously posted body begins with the exact line `**Harness automated comment**`. No emoji anywhere.

## Round 1

### 1. Resolve the target

`$ARGUMENTS` as PR number or URL, else the current branch's PR (`gh pr view --json number,url`). Gather: head SHA, base branch, changed file list, commit log, full diff, repo visibility (`gh repo view --json visibility`). If the change was built from a spec (linked in the PR body, in a tracking issue, or supplied by the caller), note its location - it is passed to the personas that need design intent.

### 2. Select the personas

All personas live in this skill's `personas/` directory, one file each:

| Persona | Lens | Model |
|---|---|---|
| `fresh-eyes` | first-look senior engineer: bugs, edge cases, error handling, clarity | default |
| `breaker` | failure hypotheses: malformed input, dependencies down, scale, rollout, observability | default |
| `tests` | do the tests protect the code; TDD evidence for bugfixes | default |
| `standards` | house rules: comments, docstrings, suppressions, DRY, naming | default |
| `correct-design` | is this the right design; conformance to the approved spec | default |
| `security-audit` | deep security: data-flow trace and concrete exploit per finding | `fable` |
| `database` | data stores, migrations, query cost, schema coordination | `fable` |
| `api-contracts` | contract shapes, serialization, deploy-window coexistence | default |
| `concurrency` | races, ordering, idempotency of side effects | `fable` |
| `frontend` | UI states, client/server validation split, reactivity, accessibility | default |
| `infra` | deployment config, IaC, rollout safety, monitoring | default |
| `reliability` | retries, timeouts, resource bounds, cache invalidation | default |
| `security-breadth` | broad OWASP-style sweep; second security lens | default |

The Model column is this harness's single source of truth for reviewer model assignment. `default` means spawn with no model parameter, so the `reviewer` agent's own frontmatter applies. A named model is an override for a persona whose misses are the most expensive to recover from - the skeptic can refute a bad finding but can never recover one that was never made. Pass it as the call-site model on that persona's spawn, and pass nothing for every other persona.

Selection is your judgment, scaled to the impact of the change. Read the diff, judge what the change touches and what could go wrong, and pick the personas (and how many) whose lens that impact deserves. `fresh-eyes` is always included - code is always reviewed at least once. Calibration examples: a typo-level documentation change gets `fresh-eyes` alone; architectural docs or ADRs add `correct-design` and the domain personas the document touches; application code typically adds `breaker`, `tests`, and `standards`; executable code on a security surface adds `security-audit`, and its deliberate overlap with `security-breadth` is worth having - when both flag the same issue independently, that dual-lens convergence is the panel's highest-value signal. Match domains by what the code does, not by filenames. Record the selected personas and the reasoning, plus what was considered and skipped.

### 3. Spawn the panel - blind and parallel

One `reviewer` agent per selected persona, all in a single message of parallel Agent tool calls, each with the stable name `reviewer-<persona>-<owner>-<repo>-pr<number>`. Each prompt contains only:

1. The absolute path of its persona file, with the instruction to read and adopt it.
2. The repo, PR number, and head SHA - the reviewer fetches the diff itself.
3. For `correct-design` (and any persona whose file asks for design intent): the spec location and the instruction to fetch it before reviewing.

Spawn each persona on the model its row in the selection table names: a call-site model only where the table names one, nothing at all where it says `default`.

Blindness is mandatory: no prompt mentions other reviewers, a panel, verification, or skeptics. Each reviewer is told it is the sole reviewer of this change. A reviewer that fails or returns garbage is relaunched once with identical parameters - the same model included, so a relaunch never silently downgrades a persona; if it fails again, mark coverage as partial for that persona in the report - never silently.

### 4. Verify with the skeptic

Collect every reviewer's findings block. Dedup findings that hit the same file within 5 lines or state the same concern; a merged finding lists every persona that flagged it, sorts first, and is called out - convergence raises priority but never skips verification. Then spawn one `skeptic` agent named `skeptic-<owner>-<repo>-pr<number>` and send it every CRITICAL, HIGH, and MEDIUM finding with provenance and severity stripped - no persona tag, no severity label, nothing that anchors authority. LOW and NIT findings post unverified. Refuted findings are dropped from posting and listed in the report with the refutation reason.

The skeptic may also adjust a surviving finding's deferral: a deferred nit whose fix is one obvious line can be promoted to fix-now, and a fix-now medium whose fix would widen the PR's scope can be demoted to deferred - each with the reasoning stated.

### 5. Post one batched review

Post exactly one GitHub review per round (github-comment skill, batch mode, event `COMMENT`): inline comments for findings with a line anchor, the review body for `general` findings plus the round summary - verdict, coverage, convergences, and the list of deferred findings so follow-up PRs can pick them up. Per-finding body:

```
**Harness automated comment**

[<persona>] <SEVERITY> <fix-now | deferred>

<finding body>

Deferred because: <reason>

Verification: <skeptic-sustained | unverified (LOW/NIT)>
```

The `Deferred because:` line is mandatory on every deferred finding and omitted entirely on fix-now findings. State why this PR is the wrong place to fix it - scope it would widen, a dependency it waits on, a decision it needs. A deferred finding outlives the PR as a tracking issue, and this line is the only record of the reasoning that reaches it.

Verdict (wording only, never a request-changes event): BLOCKED with any surviving CRITICAL; REQUEST CHANGES with any surviving HIGH; APPROVE WITH NITS when only MEDIUM/LOW/NIT survive; APPROVE when nothing actionable remains.

Public repos: security findings never carry exploit detail inline - post a neutral marker (persona, severity, one sentence that a security-relevant issue was identified here, details withheld on a public repository) and put the full finding in the terminal report only. Never post absolute operational numbers; use ratios.

### 6. Report

Always end with a terminal report to the caller: selected and skipped personas with the selection reasoning and the model each one actually ran on, coverage status, every finding with its disposition (posted fix-now / posted deferred / refuted with reason / redacted, with the unredacted detail here), convergences, verdict. If posting was impossible (no comment access), the report carries everything the review would have posted.

## Later rounds - wake, never re-spawn

When the caller asks for a re-check (fixes were pushed, or a standalone user asks again):

1. Wake each existing reviewer via SendMessage: "PR #N changed since your review (new head <sha>). Verify each of your findings was addressed or validly rebutted, and review the changes as new material." Wake the skeptic the same way with the fresh CRITICAL/HIGH/MEDIUM findings.
2. Steps 4-6 repeat on the results. A finding rebutted by the builder with evidence the reviewer accepts is closed; one the reviewer restates goes back in the round's review.
3. The caller owns round counting and any cap; this skill runs the round it is asked for.
