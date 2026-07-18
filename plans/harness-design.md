# Harness Overhaul — Detailed Design (v2)

> **READ THIS FILE** when reviewing or discussing the overhaul — designs, proposals, open items.
> `harness-overhaul.md` is only the roadmap (phase status, decision ledger, history).
> **Status: DRAFT.** Most questions ruled 2026-07-17 (§9). Remaining open items in §8 — the
> review-panel architecture (§3) is the main one still under discussion.

---

## 0. Principles (set by the user, 2026-07-17 — they override everything below)

> P1, P2, and the no-emoji rule are promoted to global `CLAUDE.md` rules (Decision Making +
> Claude Code sections) so they apply in every repo, not just this one. Listed here because the
> designs below depend on them.

- **P1 — Optimal-first.** Recommendations and generated options are ranked ONLY by outcome
  quality (correctness, security, maintainability, performance, operability). Build effort,
  engineer time, and migration cost are never ranking criteria — an LLM has no concept of time,
  and calibrating to the current codebase reproduces its flaws. Always surface the green-field
  option. YAGNI governs scope (no unrequested features), never structure (never accept
  suboptimal architecture to avoid change). Optimal ≠ maximal: speculative abstraction is itself
  suboptimal. Applies to: brainstorming's approaches step, the panel's design lens,
  receiving-code-review, CLAUDE.md (Phase 5 wording).
- **P2 — Generic skills + per-repo profiles.** Skills contain zero repo-specific facts (no repo
  lists, no owner tables). Repo facts — trust tier, frontend or not, base branch, launch
  command, evidence storage — are asked ONCE when first needed (question selector) and saved to
  that repo's profile (project memory). Unattended runs that hit a missing profile fact default
  to the safe behavior (read-only / skip) and flag it in the report.
- **P3 — One-shot delivery.** The full plan is implemented at once — no incremental
  validate-then-promote gates. Everything is built complete into `skills-disabled/`; the user
  enables, trials the whole system, and iterates via feedback. Deletions (writing-plans, swarm
  stack) happen now, not after validation milestones.

## 1. Grounding facts (context for design — never configuration inside skills, per P2)

Discovered 2026-07-17: gh authenticated (`palazzem`, ssh). 6 open PRs spanning own repos, one
org (`sintagma-engineering`), one external (`bazzite-org`) — proof that autonomy must be
tier-scoped per repo. Clones under `~/workspaces/<repo>`. CI = GitHub Actions everywhere.
Several Vite/React frontend repos exist. No stacking tool installed. Playwright browsers +
bundled ffmpeg already cached. Models: session `claude-fable-5[1m]` (xhigh); `opus`, `sonnet`,
`haiku` selectable. MCP: context7 only; GitHub via `gh`.

---

## 2. Global elements

### 2.1 Bot identity (ruled: Q1, D2)

First line of every autonomously posted GitHub comment, no emoji, nothing else in the header:

```markdown
**Harness automated comment**
```

Hidden HTML markers identify upsertable comments (`<!-- pr-review-summary -->`,
`<!-- visual-evidence -->`) and mark bot-authorship for triage (posts go through the user's own
account, so the header/marker — not the account type — is the machine-readable signal).
The "never mention AI" CLAUDE.md rule is narrowed to authored artifacts the user reviews and
owns (PR descriptions, commit messages).

### 2.2 Per-repo profile (ruled: Q2 "ask per repo" + P2)

A per-repo record maintained in that repo's Claude project memory (`repo-profile` memory file).
Fields (extensible): `trust` (full-autonomy | read-only), `frontend` (yes/no), `base_branch`,
`launch_command`, `evidence_storage`, `stacking` (graphite | none). Every skill that needs a
field: read profile → if absent, ask once and save → if unattended, safe default (read-only /
skip) + flag in the report. No skill ships a repo list.

Trust semantics: **full-autonomy** = post comments, auto-fix, resolve bot threads, push (incl.
rebase + force-push-with-lease per Q6). **read-only** = observe and report to the user only;
no comments, no resolves, no pushes.

### 2.3 Severity scale

`CRITICAL / HIGH / MEDIUM / LOW / NIT` across panel findings, triage buckets, and the rewritten
receiving-code-review calibration:

| Severity | Triage default | Push-back requires |
|---|---|---|
| CRITICAL / HIGH | implement (actionable if concrete + localized) | concrete codebase evidence |
| MEDIUM | consider | logical reasoning |
| LOW / NIT | resolve silently, reason in report | n/a |

Posting (ruled: Q5b): **every verified finding gets an inline resolvable comment**, all
severities — complete thread-level audit trail. The sticky summary aggregates verdict,
convergences, and round history.

### 2.4 Model assignment (D4 — user decides per component; table pending sign-off, §8 O2)

| Component | Work | Proposed model |
|---|---|---|
| Panel reviewers | deep code review | session (Fable 5) |
| Skeptic verifiers | adversarial refutation | opus — deliberately a DIFFERENT model than the reviewers (breaks model monoculture: a Fable-level hallucination shared by reviewer and skeptic is invisible to a Fable skeptic) |
| review-triage | judgement + code fixes | session |
| Brainstorming + spec writing | design dialogue | session |
| Spec red-team | spec critique | session |
| pr-shepherd loop runner | polling, classification, dispatch | haiku |
| CI log classification (flaky vs legit) | log reading | sonnet |
| Lint autofix / description sync | mechanical | sonnet |
| visual-evidence capture | playwright driving | haiku |
| push-pr subagent | PR body authoring | sonnet (unchanged) |
| stacked-prs restack operations | mechanical git | sonnet |

### 2.5 State & filesystem

Skill state under `~/.claude/state/<skill>/` (gitignored). Repo facts in per-repo profiles
(§2.2), never in state files. All new skills built complete under `skills-disabled/` (P3).

---

## 3. Review panel (`pr-review`) — ARCHITECTURE UNDER DISCUSSION (§8 O1)

### 3.1 What the sources actually do (answering D5/Q4/Q14)

- **Paul D'Ambra (PostHog)** runs a **library of independent reviewer skills**, each a separate,
  individually-maintained identity with its own growing reference files: `qa-team` (itself an
  orchestrator: classifies changed files, spawns domain-specialist sub-agents chosen by persona,
  informed by an **incident-patterns library** distilled from real production incidents),
  `paul-reviewer` (his personal standards, grounded in his real past reviews),
  `xp-reviewer` (XP/simple-design philosophy + c2wiki wisdom), `security-audit` (systematic
  audit format: Description / Data flow / Exploit / Fix / Confidence, usable standalone).
  `qa-swarm` is only the thin orchestrator that runs them blind + parallel and posts.
- **stamphog is not a panel** — it's a single showstopper reviewer behind deterministic gates
  (an approval gate, which we shelved). "PostHog's review panel" in practice = Paul's reviewer
  skills above.
- Neither source has a pre-posting verification stage: Paul's findings are consumed by humans
  and by triage's strict actionability rules; stamphog's single reviewer can only tighten gates.

### 3.2 Where the v1 proposal was anchored (acknowledged)

v1 consolidated the existing 7 ask-claude-review mandates into 6 and scaled by diff size. That
kept the old harness's checklist categories as the quality baseline — exactly the calibration
bias P1 forbids. What it lost from the source architecture: reviewers as independent identities
with **reference libraries that grow** (the panel learns), heterogeneity of KIND (domain
specialists + philosophy + deep audit find different bugs than checklists), and content-based
composition.

### 3.3 v3 — post-adversarial proposal (`PROPOSED`, supersedes v2)

v2 was attacked by three adversarial skeptics (adopt-verbatim advocate, transfer critic,
failure-mode attacker; full verdicts in the session report, 2026-07-17). Scorecard: 2
divergences overturned, 6 modified, 4 sustained, plus 6 cross-cutting adoptions none of us had
listed. The panel below is what survived.

**Calibration inversion (system-wide, from the attack).** PostHog's reviewers are recall-biased
(flag everything; humans filter cheaply). Our consumer is an autonomous fix pipeline, so every
reviewer prompt is **precision-biased**: report only findings you would stake an auto-fix on.
The verification stage is a backstop, not a substitute for this inversion.

**Roster** (each reviewer independently invocable/testable for calibration, bundled under
`pr-review/reviewers/`):

| Reviewer | Identity | Notes from the attack |
|---|---|---|
| `fresh-eyes` | ALWAYS ON, unchecklisted generalist: senior engineer seeing the change first time — does it do what the commits claim, obvious bugs, error handling, races | absorbs v2's `correctness`; adopted verbatim from qa-team generalist-a (overturned DIV-2) |
| `breaker` | ALWAYS ON, unchecklisted generalist: adversarial bug-hypothesis GENERATOR — malformed/huge/malicious input, races, deploy-coexistence, misuse; also owns the observability/safe-rollout instinct (log-before-limit, flag risky behavior, measurability) | adopted verbatim from generalist-b; the skeptic (refuter) cannot replace it |
| `security-audit` | deep method reconstructed from its output contract: data-flow trace → exploit construction → fix → confidence | least-faithful adoption in the panel (body is store-only) → least trusted by auto-fix, most iterated |
| `qa-domains` | content-selected domain specialists (db, API, concurrency, frontend, reliability, infra) — includes a SECOND security lens (breadth persona), intentional overlap with security-audit | grounded in a seed of PostHog's stack-agnostic Cross-Cutting Anti-Patterns; **no git-history mining** (poison loop); grows only from real post-merge escapes via the defined capture step below |
| `tests` | dedicated: TDD evidence, behavior-not-implementation, no duplicate tests, coverage | guards the pipeline against its own auto-written tests; per-domain test signals also woven into qa-domains personas |
| `simple-design` | XP four rules + P1: flags least-diff fixes that entrench bad structure, proposes green-field | its findings are design judgment — NEVER auto-implementable |
| `standards` | house rules seeded from CLAUDE.md, formatted as care-abouts with why + worked example (not a bare checklist) | grows from triage push-backs via the capture step |

> **USER RULING 2026-07-18 — final roster:** `fresh-eyes`, `tests`, `standards`,
> `correct-design` (renamed and re-mandated from simple-design: correctness of design is the
> criterion — if simplicity is right, do it right; if the problem needs complexity, build the
> complexity right), `security-audit`, `qa-domains`. `breaker` was not in the user's list —
> flagged as a recall gap (it was the panel's only adversarial bug-hypothesis generator);
> pending user decision: re-add as 7th, or fold its "how does this break" mandate into
> fresh-eyes. qa-domains confirmed as the GROWING reviewer set (see growth mechanism below).

**Composition floor** (overturned DIV-7): generalists always on; content-based specialist
selection with a minimum — if fewer than 2 specialists qualify, add the most broadly applicable
(security breadth, reliability). `tests` and `standards` run on every code diff.

**Execution**: blind, parallel, byte-level independence (no reviewer knows the roster, count,
or that convergence analysis exists). Reviewers reason in their native voice first and emit the
structured findings block only as their final step (modified DIV-9 — structure-cold truncates
the reasoning that finds subtle bugs). **Reconciliation gate**: the panel is complete only when
every launched reviewer has reported (failures appear as named sentinels, never silently
missing) — partial coverage is reported as partial, never handed to auto-fix as complete.

**Convergence** (dedup ±5 lines / same concern): raises confidence and priority ONLY. It never
skips verification (overturned from v2 — same-model reviewers make agreement correlated, not
independent; a convergent CRITICAL was getting the least verification exactly where the stake
was highest).

**Verification stage** (redesigned): keyed to ACTION, not severity —
- Any finding bound for auto-fix: skeptic refutation (provenance and severity stripped from the
  prompt to prevent authority-anchoring) AND an executable reproducer — a failing test or
  concrete exploit trace — before the fix is written (this is CLAUDE.md's TDD-for-bugfix rule
  applied to the pipeline itself). After the fix: the reproducer passes and the suite is green
  before anything is pushed.
- Post-only findings: one skeptic for CRITICAL/HIGH/MEDIUM; LOW/NIT post unverified.
- Skeptics run on a DIFFERENT model than the reviewers (model-monoculture break; §2.4 amended:
  skeptics → opus). Skeptics are read-only agents (the `skeptic` agent definition, D6), prompted
  to refute with codebase evidence, refute-by-default-if-uncertain.
- Security findings: never auto-fixed without a reproducer; both security lenses' convergence
  reported to the user; on PUBLIC repos, exploit details are NEVER posted inline — the finding
  posts as a neutral marker and the full detail goes to the user's terminal report only
  (public-repo redaction, adopted from qa-swarm and extended).

**Auto-fix eligibility carve-outs** (new): findings from `simple-design` (design judgment) and
test-authoring findings from `tests` route to "consider"/stop-and-ask — never auto-implemented.
An auto-written passing test would encode current behavior as correct; an auto-applied
restructure is an unsupervised rewrite.

**Growth capture (defined mechanism — without it the "learning panel" is vapor):** two writers,
both explicit steps, not aspirations: (1) review-triage's report step — every user push-back or
override is distilled to one care-about entry appended to `standards`' reference file; (2)
pr-shepherd's terminal step + a manual `/panel-lesson` entry point — a post-merge escape (bug
traced to a reviewed PR, revert observed) is distilled into the repo's incident-patterns memory
(P2: per-repo, never in the skill).

**Loop guards** (new): triage's fix commits are marked (commit trailer); the round-check
excludes them so the panel never re-reviews its own auto-fixes into a fix→flag→fix loop. The
sticky summary lists every auto-fixed finding with its commit SHA — the audit trail survives
even though the threads self-resolve.

**Workflow around the panel** (unchanged from v1): round-check via marker SHA (doc-only diffs
never re-trigger), one GitHub review carrying all inline comments, sticky upserted summary with
round history, informational verdict ladder (never an actual request-changes review, never
merge), posting gated by the repo profile's trust tier — now also by repo VISIBILITY (public
repos get the redaction rules regardless of tier).

### 3.4 Pipeline shape (D5 — recommendation, pending nod: §8 O4)

Adopt the source architecture literally — three skills, no separate review-cycle:

- **`pr-review`** — generation: panel → verify → post (this section).
- **`review-triage`** — consumption, dual-mode like Paul's: standalone it re-runs `pr-review`
  itself when substantive changes exist since the last round, then triages; as a shepherd
  sub-step it only triages (the shepherd owns panel runs).
- **`pr-shepherd`** — the per-PR loop (§5) that orchestrates both.

---

## 4. `review-triage` — thread burn-down (design stable, rulings applied)

Everything from v1 holds, with rulings: buckets (actionable / nit / ambiguous / human — every
unresolved thread ends in exactly one, never seen-but-unhandled); any human participation makes
the whole thread untouchable (no fix, no resolve, **never any reply** — replies to humans come
from the PR author); ambiguous bot threads go through the autonomy ladder (just-do-it /
do-and-flag / stop-and-ask) built on the rewritten receiving-code-review calibration (§2.3);
silent resolves with the run report as the only audit trail; 1500-char fetch heads with
refetch-before-act; stale bot reviews SHA-sniffed and skipped; stateless — GitHub is the queue.
**Ruled**: one commit per actioned thread, single push at the end of the run (Q5). Trust tier
from the repo profile; read-only repos get classification + report only. Terminal: only
ambiguous + human threads remain.

---

## 5. `pr-shepherd` — per-PR ownership loop (REDESIGNED per Q7 ruling)

**Not a global sweeper.** One shepherd owns ONE PR from creation to merge — the user's model:
several feature agents each finish by shepherding their own PR, so nobody has to be told to
rebase, watch CI, or fix review fallout. Typically started right after `push-pr` (which offers
it), or invoked on any PR.

**Loop** (self-paced via dynamic `/loop` — ruled Q8; the model picks each interval from what
it's waiting on: short while CI runs, long when quiet):

1. **Cheap state check** — one `gh pr view` against cached `{head_sha, ci_conclusion,
   last_comment_at}` (state under `~/.claude/state/pr-shepherd/<owner>-<repo>-<n>.json`).
   Nothing changed → reschedule, zero further calls.
2. **Freshness** — behind base → rebase onto base and force-push-with-lease (ruled Q6; conflicts
   the model can't safely resolve → flag to user, skip iteration).
3. **CI** — failing checks: read failed logs, classify flaky (rerun via `gh run rerun --failed`)
   vs legit (fix on the branch, commit; goes out with the batch push).
4. **Mechanical upkeep** (ruled Q6): lint/format autofix; description sync when the diff has
   drifted from the PR body (via push-pr's analysis).
5. **Review** — new commits since last panel round → `pr-review`; unresolved threads →
   `review-triage` (sub-step mode). Frontend repo (profile) → `visual-evidence` re-capture when
   HEAD moved.
6. **Terminal states** — merged → cleanup (delete branch, worktree, state file) + final report;
   closed → report; **blocked-on-human** (CI green, only ambiguous + human threads left) →
   notify user with the deferred list, drop to a slow heartbeat until the PR changes.

Hard rails: never merge, never close, never mark-ready; force-push only `--force-with-lease`
and only on the PR's own branch; read-only repos (profile) → observe + report only. Two
consecutive failures of the same sub-task → stop retrying, flag in report.

---

## 6. Authoring & conventions

### 6.1 `stacked-prs` (ruled: Q9 Graphite, Q10 soft cap)

Graphite (`gt`) is the stacking tool (install + `gt auth` are part of setup; repo enablement
recorded in the profile). Skill: map the spec's delivery outline → stack units; each PR ≤ 400
substantive changed lines (docs/lockfiles/snapshots excluded) — **soft cap**: exceeding requires
a stated justification in the PR body; single concern per PR; each PR ships its own tests and a
**Verification section**: exact command + expected output (feeds `/verify`). Restacks via
`gt restack`/`gt submit` after merges or mid-stack fixes.

### 6.2 `visual-evidence` (ruled: Q11 provisional, Q12 via profile)

Capture: playwright via `npx` (browsers cached), screenshots per state (empty/loading/error/
populated, derived from the diff's changed routes/components), key-interaction video → GIF via
playwright's bundled ffmpeg, before/after (base-branch worktree) when behavior changed. Trigger:
automatic for PRs in repos whose profile says `frontend: yes` — asked once per repo, never a
list in the skill (P2); manual anywhere. Storage (provisional ruling, revisit at first real
use): committed into the PR branch under `.github/pr-evidence/<pr>/<sha>/`, embedded in an
upserted evidence comment (`<!-- visual-evidence -->`, §2.1 header). Evidence manifest keyed by
head SHA drives re-capture when the shepherd sees HEAD move.

### 6.3 `receiving-code-review` rewrite

As v1: keep the verification-before-implementation core, forbidden performative responses,
YAGNI check (scope-scoped per P1), graceful correction, GitHub reply mechanics for human
threads. Change: own voice; severity calibration (§2.3); autonomy ladder as the autonomous
mode; swarm-context section deleted (D6); P1 added — reviewer suggestions are also evaluated
optimal-first (a reviewer proposing a band-aid over a structural fix gets pushed back with the
green-field alternative).

### 6.4 `brainstorming` redesign + `writing-plans` deletion (ruled: Q13, Q15, Q16/D11)

As designed in v1 §6.4 with rulings applied: outcome = alignment checkpoint (spec / decision
record / plain summary), next step always the user's explicit choice. Trigger (Q15):
auto-suggest on genuinely ambiguous or new-feature work, never blocking; `/brainstorming`
invocable anytime; the HARD-GATE is dead. Spec home (Q13): by context — repo/issue-tracked work
→ GitHub tracking issue; explorations → markdown file (location asked once, remembered).
Approaches step runs under P1: green-field option always present, effort/migration never rank.
Spec format: Problem & goal · Context & constraints · Decisions (chosen + rejected, with why) ·
Non-goals · Delivery outline (ordered PR-sized outcomes + observable verification each; feeds
stacked-prs) · Open questions. **writing-plans is deleted now** (Q16, P3), not after a
validation milestone. **Spec red-team (ruled, user 2026-07-17): a standard step of every
brainstorm** — after the checkpoint artifact is drafted, an adversarial review of the spec runs
(skeptic agent) with the explicit goal of surfacing blind spots the user didn't think about;
findings are presented to the user (not auto-fixed), then the spec is finalized.

---

## 7. Interaction map (v2)

```
brainstorming ──spec + delivery outline──► stacked-prs (gt) ──PR(s)──► push-pr
                                                                          │ offers
                                                                          ▼
                                    pr-shepherd (one per PR, self-paced loop)
                                    │  freshness (rebase+FWL) · CI fix/rerun
                                    │  lint autofix · description sync
                                    ├──new commits──► pr-review (panel → skeptics → post)
                                    ├──open threads──► review-triage (sub-step mode)
                                    ├──frontend (profile)──► visual-evidence
                                    └──terminal: merged → cleanup · blocked → notify user
standalone: /pr-review, /review-triage (dual-mode: re-runs pr-review when warranted)
foundations: per-repo profiles (P2) · skeptic agent (verification + spec red-team)
           · receiving-code-review (evaluation core) · push-pr (unchanged role)
```

---

## 8. Open items

| # | Item | Waiting on |
|---|---|---|
| O1 | Panel architecture ruling: v3 post-adversarial proposal (§3.3) — approve / adjust | user, after reading the adversarial report |
| O2 | Model assignment table (§2.4) sign-off — user decides per component (D4) | user |
| O3 | ~~Spec red-team policy~~ RULED: standard step of every brainstorm — adversarial spec review to surface blind spots, findings presented to the user | — |
| O4 | Pipeline shape (D5): 3 skills, review-triage dual-mode, no review-cycle (§3.4) | user nod |
| — | Evidence storage revisit | deferred by user to first real use |

## 8-bis-v5. Delta: W1 Design Overview gate (2026-07-18)

User concern (metrics-from-mobile example): without a design gate, Fable may pick a
structurally weaker architecture (local queue) over the correct one (Terraform-enabled pub/sub
+ abstracted consumer) and the error surfaces only after implementation tokens are spent.
Resolution:

- **W1 becomes two gated stages**: Stage 1 Understanding (template) → user approves; Stage 2
  **Design Overview** — recommended high-level architecture per the Decision Making procedure
  (unlimited-resources design, 2–3 genuinely different options ranked by outcome quality only,
  green-field always present, rejected alternatives named) → breaker red-team attacks both
  stages with the explicit test "would this design differ if effort were free?" → user
  approves the direction → recorded in the checkpoint's Decisions section.
- **Architecture lock**: the brief carries the approved overview; builder deviation from it
  requires escalation to the main agent; the `correct-design` reviewer receives the approved
  overview and checks implementation conformance (drift = finding). Three gates against a
  wrong design surviving.
- **Platform-context probe**: when the design touches system boundaries (messaging, storage,
  deployment), Stage 2 asks about available infrastructure once; answers persist (infra facts →
  repo profile, platform decisions → lessons) so later brainstorms start informed.
- Task impact: Task 1 gains Stage 2 + probe; Task 2 gains the architecture lock; Task 3 gains
  correct-design conformance.

## 8-bis-v4. Deltas after third feedback round (2026-07-18)

- **PR lifecycle**: DRAFT for the whole W2↔W3 machine loop; flipped to OPEN the moment humans
  enter — i.e., when either message type fires (type 1 "ready for final review" or type 2
  "escalations for you"). Open = humans involved, draft = machines iterating.
- **L location confirmed**: lessons live in the TARGET repository's own `.claude/lessons/`
  (e.g. `menta/.claude/lessons/…`), committed to that repo. The global `~/.claude` is only the
  harness config; the earlier path reading was a coincidence of this session's cwd.
- **L primitives vs convention (user asked: reinventing the wheel?)**: no platform primitive
  does versioned, glob-scoped lesson retrieval. Native pieces we ride: repo-level CLAUDE.md
  auto-load + its @import syntax (imports `.claude/lessons/INDEX.md` so the index enters
  context automatically — no rule to remember), and plain files in git. The scoped-retrieval
  leg (frontmatter domains + path globs, consumers load only matching lessons) is OUR
  convention, borrowed as best practice from Cline Memory Bank / .cursor-rules-style
  glob-scoping. Claude Code's own auto-memory primitive was evaluated and rejected for this
  purpose (unversioned, worktree-path-keyed — the exact failures identified earlier).
- **Trigger map (auto vs manual)**:
  | Skill | Trigger |
  |---|---|
  | brainstorming | MANUAL (may auto-SUGGEST on ambiguous asks; never auto-runs) |
  | implement | MANUAL entry — then the chain is AUTOMATIC: W2 → draft PR → W3 loop → flip OPEN → W4 shepherd → merge → Fable learning pass |
  | pr-review / review-triage | AUTO inside the chain; MANUAL ad-hoc on any PR |
  | push-pr | AUTO inside implement (draft mode); MANUAL as before |
  | pr-shepherd | AUTO at the OPEN flip; MANUAL attachable to any PR |
  | visual-evidence | AUTO in W3 when repo profile says frontend; MANUAL anywhere |
  | gh-inline-comment | internal command, agent-facing only |
  | receiving-code-review | behavioral — applies whenever review feedback is handled |
  | build-design-system | MANUAL (unchanged) |
  | lesson capture / merge pass | AUTO at events / AUTO on merge detection |

## 8-bis-v3. Deltas after second feedback round (2026-07-18)

- **W1**: the reasoning sentence was an example — the deliverable is a STANDARD TEMPLATE with
  pointed fields: the task · who it's for · what the output enables · the request · acceptance
  criteria. The always-on adversarial design review uses the BREAKER persona adapted to
  designs (generative hole-finding, not just refutation).
- **W2**: implementability verified against the harness: Agent tool + agent frontmatter support
  per-agent `model` (opus/haiku/sonnet/fable); Workflow `agent()` takes model overrides;
  subagents escalate via SendMessage to main. The split is real, not aspirational.
- **W3 continuity (user's staleness concern — investigated, REAL if naive, solved by design)**:
  named agents are resumable with context intact (a SendMessage to a completed agent resumes it
  from its transcript; a new Agent call starts fresh — documented harness semantics). Therefore:
  **ONE PERSISTENT `builder` AGENT (Opus) PER PR**, spawned in W2, resumed by name for every
  triage fix round and every shepherd-dispatched CI fix until merge. No cold re-reads; the
  builder keeps the implementation rationale for the PR's whole life; prompt-cache hits on
  resume. Spawning a fresh fixer per round is explicitly forbidden in the design.
- **W4**: shepherd is a HAIKU routine doing only: rebase, conflicts, flaky rerun, lint,
  description sync, pings (two message types). All code fixes → resumed builder. On merge:
  the learning pass runs on a FABLE-class agent — it learns from artifacts (the PR's full paper
  trail: panel comments, triage commits, escalations, your comments), not from having been
  present; escalations during the build are the core agent's other high-signal learning input.
- **L (redesigned per user: no /reflect, no extra PRs)**: **lessons ride the PR that taught
  them** — capture events during W2/W3 write lesson files into the working tree
  (`.claude/lessons/<domain>/<slug>.md`), committed alongside fixes, merged with the PR, and
  reviewed by the user in their mandatory final review (learning stays human-gated with zero
  extra PRs). Post-merge escapes ride the fix PR. The Fable merge pass distills anything missed
  into `~/.claude/state/lessons/<repo>/` staging → rides the next PR. **Retrieval at scale**
  (avoid reading 200 irrelevant files): each lesson has frontmatter (domain tags + path globs);
  a one-line-per-lesson `INDEX.md` is regenerated at write time; consumers (builder, each
  panel reviewer) read the index and load only lessons matching the diff's paths/domains.
  Prior art this follows: Claude Code memory index pattern, Cline Memory Bank, glob-scoped
  editor rules (.cursor/rules) — index + scoped loading, no retrieval infra.
- 2.4: the user never writes code (director role) — post-ready blind window is void.
- Breaker: in, token usage monitored on first real implementation.

## 8-bis. Reset framing — v2 after user feedback (2026-07-18)

Final-solution mandate: design all-or-nothing; ignore legacy constraints found in current
skills/CLAUDE.md. Changes vs v1 of this framing:

- **W1** captures the REASONING, not just the request — elicit the template "I'm working on
  [larger task] for [who it's for]. They need [what the output enables]. With that in mind:
  [request]" plus observable acceptance criteria.
- **W2** — model split: **Fable = brain** (authors the in-depth implementation brief, always
  available for escalation/advice), **Opus 4.8 = builder** (executes implementation; works as a
  single subagent OR inside a Workflow; escalation contract: blocked → ask the main agent).
  No local panel round: implement → tests → **push a DRAFT PR immediately** — the panel reviews
  on GitHub so the conversation is followable and the paper trail is native.
- **W3** — the in-depth review loop, runs ON the draft PR, panel spawned HERE (never by the
  shepherd): panel round → skeptic verification → post to the PR (**each reviewer chooses
  inline vs general comment**; inline posting via the gh technique in
  https://github.com/cli/cli/issues/359#issuecomment-4390129612, to be wrapped as a dedicated
  command/skill at build time) → triage fixes (Opus) → **re-trigger the panel only if major
  changes were applied** (bounded, max 3 rounds) → terminal: flip draft→ready + message.
  After W3 converges, ONLY humans review — later pushes never re-spawn the panel (manual
  /pr-review remains available).
  Exactly two human-facing message types: **(1)** "ready for your final review — push back or
  merge"; **(2)** "escalated items — panel comments pushed back with uncertainty, your call."
- **W4** — maintenance only: rebase/conflicts/CI/lint/description until merge; pings using the
  two message types; cleanup; final lesson-completeness pass (see L). Never spawns reviewers.
- **L** — two-tier, hardened by adversarial review of the user's proposal:
  staging lessons captured AT EVENTS (user PR comment resolved, rejected finding, escape) into
  `~/.claude/state/lessons/<owner>-<repo>/` — canonical per repo, immune to the
  worktree-project-dir mismatch that would scatter Claude-primitive memories; shepherd's
  merge-time pass completes missing lessons from the PR history; `/reflect` distills staging →
  repo-specific rules committed IN the repository **via a small PR the user approves**
  (learning itself is human-reviewed) + generic lessons → persona/standards files in
  claude-config (already versioned); consumed staging cleared, raw lessons preserved in the
  distillation PR body as provenance.
- **Panel**: breaker re-added provisionally (cost watch). Cross-model integrity chain:
  Opus writes code → Fable panel reviews it → Opus skeptics attack Fable's findings → Opus
  implements fixes. Every artifact is checked by a different model than the one that made it.

## Previous framing (v1, superseded) — the four workflows

The user reframed the goal to cut through accumulated detail: "rewrite all skills/agents to
implement workflows that keep consistent delivery quality." The system is FOUR WORKFLOWS plus
ONE LEARNING LAYER; every skill below serves one of them:

- **W1 UNDERSTAND** (`brainstorming`): structured questioning to capture context and WHAT (not
  how); deliverable = a detailed understanding message; red-team for blind spots; user approves
  and says where to store it.
- **W2 BUILD** (implementation flow): any change = worktree → implement (small stacked PRs,
  tests) → LOCAL panel review round + fixes (pre-PR, per the user's sequence) → push PR.
- **W3 REVIEW** (`pr-review` + `review-triage`): panel → verify → post → triage fixes/resolves
  → repeat until only human-decision items remain; those are ESCALATED VIA PR COMMENTS
  (user note: human review is mandatory; escalation posts are allowed — an exception to
  triage's never-post rule, bot-headed, top-level, never inside human threads).
- **W4 KEEP-GREEN** (`pr-shepherd`): owns the PR to merge — rebase/conflicts/CI/lint,
  dispatches W3 on new commits/comments, pings the user when it's their turn, cleans up.
- **L LEARN** (memory layer + `reflect`): every human intervention becomes a lesson so future
  reviews need less of the user ("the more I review now, the less I have in the future").
  Capture events: user PR comment resolved → lesson; user rejects a panel finding → negative
  lesson (noise pruning); post-merge bug on reviewed code → escape lesson; periodic /reflect
  distillation. User's memory-construction prompt adopted: one lesson per file, one-line
  summary, why included, update-don't-duplicate, delete-wrong.

User's "state the boundaries" prompt (assessment vs action; evidence before state-changing
commands) and "construct memory" prompt go into CLAUDE.md as global rules (build task).

**qa-domains growth mechanism (answering the user's question):** qa-domains is one reviewer
slot instantiated N times from a `personas/` directory — one markdown file per domain persona
(mandate + checklist + patterns). Seeded with ~6 generic domains (database, API, concurrency,
frontend, reliability, infra + security breadth). Selection: orchestrator matches diff content
→ spawns one agent per matched persona (min 2). Three growth paths: (a) new-domain detection —
repo stack with no matching persona → orchestrator drafts a persona file, user approves once,
it exists permanently; (b) lesson capture (L) appends distilled patterns to the relevant
persona (generic → skill repo; repo-specific → that repo's memory, per P2); (c) false-positive
pruning — rejected findings append negative rules ("don't flag X in context Y"). Reviewer set
therefore grows review-after-review and feature-after-feature, versioned in git.

## 9. Ruling log

- 2026-07-17 — Document created (v1) from discovery + the four analyzed sources.
- 2026-07-17 — In-depth brainstorming review → §6.4; writing-plans retirement proposed (D11).
- 2026-07-17 — Full interview (5 batches). Ruled: Q1 header = "**Harness automated comment**",
  no emoji (user: professional). Q2 = ask-per-repo → per-repo profiles (P2 generalized this).
  Q3/D4 = user decides per component; table §2.4 pending (O2). D6 = delete swarm stack; skeptic
  agent proposed as staff-engineer successor. Q5 = batch push. Q5b = everything inline.
  Q6 = all four extras + rebase & force-push allowed (never-force-push rail replaced by
  force-with-lease). Q7 = NOT a global sweeper — per-PR shepherd owned by the PR's author agent
  (§5 redesigned). Q8 = self-paced dynamic loop. Q12 = auto for frontend repos via profile, no
  repo lists (P2). Q9 = Graphite. Q10 = soft cap. Q11 = commit into PR branch, provisional.
  Q13 = by context. Q15 = auto-suggest never block. Q16/D11 = delete writing-plans NOW; P3
  one-shot delivery set ("full plan implemented at once, then I trial and give feedback").
- 2026-07-17 — Q4/Q14/D5 pushed back as wrong-local-choice questions → §3 rewritten as the
  big-picture panel discussion: sources' real architecture (§3.1), v1's anchoring named (§3.2),
  optimal-first v2 proposal (§3.3). P1 optimal-first principle recorded from the user's
  critique of effort/migration-biased option generation.
- 2026-07-17 — User side note ruled O3: adversarial spec review is a STANDARD brainstorming
  step (blind-spot hunting), findings presented to the user, never skipped.
- 2026-07-17 — Panel deep-dive requested (theirs vs mine, per-divergence justification,
  adversarially produced). Fetched the actual reviewer bodies: qa-team (8 specialist personas +
  2 always-on generalists, blind, cache-aware staggered launch, org incident library),
  paul-reviewer (voice from real reviews), xp-reviewer (four rules + smell catalogue);
  security-audit remains store-only (interface known, body not). Divergence inventory
  DIV-1..DIV-12 written; three adversarial skeptics dispatched (adopt-verbatim, transfer
  critic, failure-mode attacker). §3 will be finalized from their surviving verdicts.
- 2026-07-18 — FINAL APPROVAL round: user agreed to the complete design; last addition — the
  claude-config README.md must describe the entire workflow with a mermaid diagram (Task 8).
  Execution plan (tasks 0–8) captured as the Build phase in harness-overhaul.md. Phase 1
  closed.
- 2026-07-18 — Decision Making section of CLAUDE.md overhauled at user request (recurring
  Fable/Opus failure: designs weighing time/people/migration): named failure mode, banned-
  criteria list, unlimited-resources design procedure, explicit-deviation rule, pre-answer
  self-check. Harness enforcement points: brainstorming's design step embeds the self-check
  and its breaker red-team explicitly hunts smuggled human-economics; the correct-design
  reviewer flags designs shaped by banned criteria (task list updated).
- 2026-07-18 — Second feedback round → §8-bis-v3: understanding template; W2 implementability
  verified; persistent-builder answer to the context-staleness concern (evidence: named-agent
  resume semantics); shepherd demoted to haiku routine; Fable merge-time learning pass;
  L redesigned — lessons ride the PR, index + glob-scoped retrieval, /reflect dropped;
  breaker reused as brainstorming's adversarial reviewer; final skill/agent inventory fixed
  (remove 5 skills + 4 agents, keep 2, rewrite 2, new 6 skills + 2 agents).
- 2026-07-18 — Feedback round on the reset: W1 reasoning template; W2 draft-PR-first with
  Fable-brains/Opus-builder split and escalation contract; W3 owns panel spawning with bounded
  re-rounds and per-reviewer inline-vs-general posting (gh inline technique to be wrapped as a
  command); W4 maintenance-only; L hardened via adversarial review (state-dir staging →
  /reflect → versioned rules via human-approved PR); breaker re-added provisionally;
  two message types defined. §8-bis rewritten as v2.
- 2026-07-18 — User reset: four-workflow framing adopted (§8-bis); panel roster ruled (6
  reviewers, correct-design replaces simple-design with a correctness-not-simplicity mandate;
  breaker pending); qa-domains confirmed as the growing set with the persona-directory
  mechanism; review loop must evolve via memory (L layer defined); escalation-via-PR-comment
  exception added to triage; two user prompts (boundaries, construct-memory) queued for
  CLAUDE.md.
- 2026-07-17 — Adversarial verdicts in; §3.3 rewritten as v3. Overturned: DIV-2 (always-on
  generalists adopted verbatim, unanimous), DIV-7 (composition floor). Modified: DIV-3 (seed
  format + defined growth capture), DIV-4 (no convergence skip; verify the FIX via reproducer;
  different-model skeptics; provenance stripped), DIV-6 (no git-history mining — poison loop;
  seed from stack-agnostic anti-patterns, grow from real escapes), DIV-9 (reason in voice,
  structure last; design findings never auto-fix), DIV-11 (two security lenses; security never
  auto-fixes without reproducer; public-repo exploit redaction). Sustained: DIV-1 (with
  per-reviewer testability), DIV-5 (tests reviewer + carve-out), DIV-8 (no copy persona),
  DIV-10 (no cache protocol; reconciliation gate kept), DIV-12. Cross-cutting adoptions:
  precision-bias inversion (recall-biased reviewers are wrong for an auto-fix consumer),
  reconciliation/completeness gate, self-review loop guard (marked fix commits), audit-trail
  preservation in sticky summary, observability/safe-rollout lens homed in `breaker`,
  visibility-aware posting (public repos redact regardless of trust tier).
