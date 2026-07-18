---
name: pr-review
description: Use to run the multi-reviewer panel on a pull request - when the implement chain reaches the review stage on a draft PR, when substantive new commits land on a PR that was reviewed before, or manually via /pr-review on any PR or the current branch. Spawns blind parallel reviewers, verifies findings with skeptic agents, and posts one batched inline review plus an upserted sticky summary, gated by repo trust tier and visibility.
argument-hint: [pr-number-or-url] (optional) - target PR; defaults to the PR of the current branch
---

# PR Review Panel

Generation half of the review loop: panel of blind reviewers -> reconciliation -> convergence -> skeptic verification -> post. Consumption (fixes, thread burn-down) belongs to `review-triage`; the per-PR loop belongs to `pr-shepherd`. This skill is the ONLY place panel reviewers are spawned.

Hard rails, no exceptions:

- Never merge, never close, never change PR state (draft/ready) - the caller owns lifecycle.
- Never post an actual request-changes review. The GitHub review event is always `COMMENT`; "REQUEST CHANGES" is verdict wording only.
- Every autonomous GitHub post begins with the exact line `**Harness automated comment**`.
- No emoji anywhere - findings, summaries, reports.

## Step 1: Resolve target and profile

1. If `$ARGUMENTS` is a PR number or URL, use it. Otherwise detect the current branch's PR with `gh pr view --json number,url`. No PR found -> review the current branch's diff against the profile `base_branch`, output the terminal report only, skip every posting step.
2. Gather PR facts: `gh pr view <n> --json number,url,title,body,headRefOid,headRefName,baseRefName,isDraft` and `gh repo view --json owner,name,visibility`.
3. Read the repo profile - the harness's per-repo project memory, one JSON file per repository at `~/.claude/profiles/<owner>-<repo>.json`. Fields used here: `trust` (full-autonomy | read-only), `base_branch`. If a needed field is missing: interactive session -> ask the user once via the question selector and write the answer back to the profile file; unattended run -> use the safe default (`trust: read-only`) and flag the defaulted field in the terminal report.
4. Posting gates, applied independently:
   - `trust: read-only` -> run the FULL review (all steps below), but nothing is posted; the terminal report is the only output.
   - `visibility` public -> public-repo redaction rules apply regardless of trust tier (Step 9).

State lives under `~/.claude/state/pr-review/<owner>-<repo>-<pr>.json`: last reviewed SHA (fallback marker for read-only repos), reproducers, redacted security payloads, refuted-findings log. Repo facts never go in state files.

## Step 2: Round check

Find the sticky summary comment and its recorded SHA:

```bash
gh api "repos/<owner>/<repo>/issues/<pr>/comments" --paginate \
  --jq '[.[] | select(.body | contains("<!-- pr-review-summary"))][0] | {id, body}'
```

The marker line `<!-- pr-review-summary sha=<sha> round=<n> -->` records the last reviewed SHA and round number. On read-only repos (no posted summary) read the same facts from the state file.

Skip the round entirely (short terminal note, nothing posted) when any of these holds:

| Condition | Check |
|---|---|
| HEAD unchanged | `headRefOid` equals the marker SHA |
| Docs-only delta | every path in `git diff <marker_sha>..HEAD --name-only` is documentation (`*.md`, `docs/`, `LICENSE`, images) |
| Own fixes only | every commit in `git log <marker_sha>..HEAD` carries the `Harness-Fix: true` trailer (check `%(trailers:key=Harness-Fix,valueonly)`) - the panel never re-reviews its own autonomous fixes without substantive change |

Chain-mode exemption: an explicitly passed round number is a deliberate re-round decision by the loop owner, made because major fixes were applied - fixes that necessarily carry the `Harness-Fix: true` trailer. The "Own fixes only" skip therefore does NOT apply when the caller passes a round number; "HEAD unchanged" and "Docs-only delta" still do. Without this exemption every requested re-round would self-cancel and the bounded loop could never run.

No marker and no state -> this is round 1; proceed.

## Step 3: Gather context

Ensure the PR head is available locally (fetch or check out the head branch), then collect:

```bash
git diff <base>...<head> --name-only
git diff <base>...<head>
git log <base>..<head> --format='%h %s'
```

The panel always reviews the FULL PR diff. On round 2+, additionally compute the delta since the marker SHA and mark it in every reviewer prompt as "changed since the last review round" so attention lands on what moved.

## Step 4: Select the roster

The seven reviewer definitions live in this skill's `reviewers/` directory. Selection:

| Reviewer | Definition | When |
|---|---|---|
| fresh-eyes | `reviewers/fresh-eyes.md` | ALWAYS |
| breaker | `reviewers/breaker.md` | ALWAYS |
| tests | `reviewers/tests.md` | ALWAYS |
| standards | `reviewers/standards.md` | ALWAYS |
| correct-design | `reviewers/correct-design.md` | any non-trivial code diff (skip only for pure formatting, renames, comment or doc edits, config value bumps, dependency bumps) |
| security-audit | `reviewers/security-audit.md` | any executable source touched (application or library code, scripts, CI workflow definitions, infrastructure code, templates rendering external input) |
| qa-domains | `reviewers/qa-domains.md` | content-matched personas per that file's Part 1 (orchestrator) selection rules; one agent per matched persona |

qa-domains floor: minimum 2 personas per run. If fewer than 2 match the diff content, backfill with the most broadly applicable personas: `security-breadth` first, then `reliability`.

Orchestrator-only roster map: read `reviewers/ROSTER.md` for the overlap and convergence relationships between reviewers and personas. It informs backfill choices and Step 8's convergence handling, and it is NEVER included in - or paraphrased into - any reviewer prompt.

correct-design context: locate the approved design overview and include it in correct-design's prompt only. Chain mode: the caller passes the architecture lock (the brief at `~/.claude/state/implement/<branch-slug>/brief.md` carries the approved Design Overview verbatim; the checkpoint reference links the spec). Manual runs: the PR body's or linked spec's Decisions section. Implementation drift from the approved overview is a finding; if no overview can be found, note the skipped conformance check in the terminal report.

## Step 5: Lesson-scoped loading

Before spawning, read `<repo_root>/.claude/lessons/INDEX.md` (one line per lesson: summary + domains). Missing index -> skip this step silently.

1. From the index, select candidate lessons whose domains are relevant to this diff.
2. Open each candidate; keep it only if its frontmatter `globs` match at least one changed path (a lesson with no globs matches any path).
3. Route each kept lesson to the selected reviewers whose mandate covers one of its domains: testing lessons -> tests; security -> security-audit and the security-breadth persona; design or architecture -> correct-design; conventions or style -> standards; a qa-domains persona's domain -> that persona. Lessons that match the diff but no specialist mandate -> fresh-eyes and breaker.
4. Include lesson bodies in the matching reviewer's prompt under a "Repository lessons" section. Never give any reviewer the full lesson corpus - each reviewer sees only lessons matching its domain and the diff paths.

## Step 6: Launch the panel - blind and parallel

Launch every selected reviewer in a SINGLE message with parallel Agent tool calls. Reviewers inherit the session model - do not pass a `model` param.

Byte-level independence is mandatory. No reviewer prompt or reviewer-visible content may contain:

- names or descriptions of other reviewers, or that other reviewers exist
- the roster size or persona count
- that convergence analysis, verification, or skeptics exist
- any reference to a panel or team

Each agent is told it is the sole reviewer of this change.

Each reviewer prompt contains, in order:

1. The full body of its definition file from `reviewers/` (for a qa-domains persona: the "Part 2 - Persona-agent mandate" section of `reviewers/qa-domains.md` - never Part 1 - followed by that persona's file from `reviewers/personas/`).
2. The precision-bias line, verbatim: "report only findings you would stake an automated fix on".
3. Its "Repository lessons" section (Step 5), if any.
4. The PR context: changed file list, commit log, full diff, and (round 2+) the since-last-round delta markers.
5. The closing instruction, verbatim: "Reason through the change in your own voice first - your analysis, in your reviewer identity. Only as the final step of your response, emit the structured findings block exactly as your Output format section specifies."

Each definition file's own Output format section is the single output contract for that reviewer - never inject a second one. The orchestrator parses the native formats: the `STRUCTURED_FINDINGS ... END_STRUCTURED_FINDINGS` pipe block (fresh-eyes, breaker, tests, standards, qa-domains personas; empty sentinel `NO_FINDINGS`) and the YAML `findings:` block (correct-design, security-audit; empty sentinel `findings: []`). Every format's `line` field carries either a number - the reviewer wants an inline comment on that line - or the word `general` - the reviewer wants a top-level PR comment; Step 9 routes on it.

## Step 7: Reconciliation gate

The panel is complete only when every launched reviewer has reported. A reviewer that failed, timed out, or returned garbage appears in the collected results as a named sentinel:

```
REVIEWER FAILED: <reviewer tag>
```

Relaunch a failed reviewer once. If it fails again, keep the sentinel and mark coverage `partial: <failed tags>` in both the sticky summary and the terminal report. Partial coverage is reported as partial - it is never handed downstream as a complete review.

## Step 8: Convergence and verification

### Convergence

Dedup findings that hit the same file within 5 lines or state the same concern; merge into one finding listing every reviewer tag. Convergence RAISES priority and confidence only - convergent findings sort first and are highlighted, but convergence never skips or lightens verification (same-model reviewers make agreement correlated, not independent). When security-audit and the security-breadth persona converge on the same finding, flag that dual-lens convergence explicitly in the summary and terminal report.

### Action-keyed verification

First classify each deduped finding by the action triage would take:

- **Auto-fix bound**: CRITICAL or HIGH, concrete (specific defect + specific fix), and localized (contained in the diff's files, no cross-cutting redesign). Carve-outs - NEVER auto-fix bound regardless of severity: any correct-design finding (design judgment), any test-authoring finding from tests (an auto-written passing test would encode current behavior as correct). These route to the post-only path.
- **Post-only**: everything else.

Then verify:

| Path | Requirement |
|---|---|
| Auto-fix bound | 2 skeptic agents in parallel; BOTH must fail to refute. Then produce a failing reproducer - a failing test or a concrete exploit or execution trace - before any fix may be written. No reproducer producible -> demote to post-only, mark "not auto-fix eligible: no reproducer". Security findings are never auto-fix eligible without a reproducer. |
| Post-only CRITICAL / HIGH / MEDIUM | 1 skeptic must fail to refute |
| LOW / NIT | post unverified |

Skeptic mechanics: spawn the `skeptic` agent via the Agent tool with `model: "opus"` (deliberately a different model than the reviewers - a shared hallucination is invisible to a same-model skeptic). The skeptic prompt carries the claim (file, line, alleged defect, proposed fix) with provenance and severity STRIPPED - no reviewer tag, no severity label, nothing that anchors authority. Skeptics are read-only, refute with codebase evidence, and refute by default when uncertain.

Refuted findings are dropped from posting entirely; they appear in the terminal report with the refutation reason. Store reproducers in the state file so `review-triage` can run them before and after its fix.

### Verdict (informational only)

| Verdict | Condition |
|---|---|
| BLOCKED | any surviving CRITICAL |
| REQUEST CHANGES (wording only) | any surviving HIGH |
| APPROVE WITH NITS | only MEDIUM / LOW / NIT survive |
| APPROVE | no surviving actionable findings |

## Step 9: Post

Skip this entire step when trust is read-only or no PR exists - terminal report only.

### Inline findings - one batched review

Every finding whose reviewer chose `line: <n>` posts as an inline comment via the `gh-inline-comment` skill, batched as ONE GitHub review (event `COMMENT`) - never one review per finding. Comment body:

```
**Harness automated comment**

[<reviewer tag>] <SEVERITY>

<finding body: defect + concrete fix>

Verification: <2 skeptics + reproducer | 1 skeptic | unverified>
```

Convergent findings use `[convergent: <tag1> + <tag2>]`.

### General findings

Findings with `line: general` post as top-level PR comments, same body format, bot header first.

### Public-repo redaction

On public repositories, regardless of trust tier:

- Security findings never carry exploit details inline - no data-flow trace, no exploit construction, no payloads. The posted comment is a neutral marker: bot header, `[<reviewer tag>] <SEVERITY>`, and one sentence stating a security-relevant issue was identified here with details withheld on a public repository. The full finding goes to the terminal report and the state file only.
- Never post absolute operational numbers (event counts, user counts, revenue). Use ratios or percentages.

### Sticky summary - upsert in place

Exactly one summary comment per PR. If Step 2 found a comment id, PATCH it (`gh api "repos/<owner>/<repo>/issues/comments/<id>" -X PATCH -F body=@<file>`); otherwise create it (`gh pr comment <n> --body-file <file>`). Body shape:

```markdown
**Harness automated comment**
<!-- pr-review-summary sha=<head_sha> round=<n> -->

## Review round <n> at <short_sha>: <VERDICT>

<1-2 sentences explaining the verdict. Coverage note here if partial.>

### Key findings

<bullets grouped by severity, current round only, convergent findings first>

### Convergences

<findings flagged independently by 2+ reviewers; call out security dual-lens convergence>

### Auto-fix log

<one line per autonomously fixed finding: finding summary - commit SHA. Carry prior
entries forward; append new Harness-Fix commits landed since the previous marker SHA.
The audit trail survives here even though inline threads self-resolve.>

### Escalations

<items awaiting the user's decision - findings pushed back with uncertainty. Carried
forward until resolved.>

<details>
<summary>Previous rounds (<count>)</summary>

<one line per prior round: round <k> at <short_sha> - <verdict>: <one-line disposition>.
Collapse the previous round's detail into its one line when updating.>

</details>
```

## Step 10: Terminal report

Always produced, whatever the posting gates did. Contents: target PR and round; roster launched, sentinels, coverage status; every finding with its disposition (posted inline / posted general / refuted + reason / redacted with full unredacted detail here); convergences; verdict; any profile field that fell back to a safe default in an unattended run.

## Bounded loop contract (chain mode)

When invoked from the implement chain (W3, on a draft PR). The caller - the loop owner - is the implement skill's review-loop section, executed by the main agent:

1. The caller passes the round number; round 1 always runs. A passed round number activates Step 2's chain-mode exemption.
2. After `review-triage` applies fixes, re-run the panel ONLY if major changes were applied - logic or design fixes. Mechanical changes (lint, formatting, renames, comment edits, description sync) never re-trigger a round.
3. Maximum 3 rounds total per PR, then terminal regardless of state.
4. This skill never flips the PR out of draft and never sends the human-facing messages - the chain owns both. After the chain hands the PR to humans, later pushes never auto-re-spawn the panel; manual `/pr-review` remains available on any PR.
