---
name: qa-domains
description: The domain-specialist engine for the pr-review panel. Part 1 (orchestrator-only) defines persona selection, the composition floor, new-domain handling, and growth; Part 2 is the persona-agent mandate, the only part ever included in a spawned persona's prompt. This is the GROWING reviewer set - it gains personas over time.
---

# qa-domains — Domain-Specialist Engine

`qa-domains` is not a single reviewer. It is one panel slot instantiated N times from the
`personas/` directory — one markdown file per failure domain. It ships no repo-specific
facts (P2).

This file has two parts with different audiences:

- **Part 1 — Orchestrator** is consumed ONLY by the pr-review orchestrator (Steps 4-5)
  when selecting and spawning personas. Never include any of it in a persona prompt.
- **Part 2 — Persona-agent mandate** is the ONLY part of this file included in a spawned
  persona agent's prompt, followed by that one persona's file.

The persona set GROWS. New domains become permanent persona files; real post-merge
escapes append patterns to existing personas via the lessons layer. Over time this
reviewer covers more of the stack than any fixed checklist could.

---

# Part 1 — Orchestrator (never reviewer-visible)

## Personas directory

Seed personas live in `personas/` next to this file:

| Persona | Domain |
|---|---|
| `database` | data stores, migrations, query cost, schema coordination |
| `api-contracts` | request/response shapes, serialization boundaries, versioning, deployment coexistence |
| `concurrency` | parallelism, shared state, races, idempotency, ordering |
| `frontend` | UI states, client/server validation split, reactivity, accessibility |
| `reliability` | failure modes, retries, timeouts, circuit breakers, resource bounds |
| `infra` | deployment config, IaC, environment parity, rollout safety, monitoring |
| `security-breadth` | second security lens — broad OWASP-style pass, intentional overlap with `security-audit` |

Each persona file carries: focus, context (stack-agnostic failure wisdom), and a review
checklist. Overlap and convergence relationships between personas live in `ROSTER.md`
(orchestrator-only), never in the persona files a spawned agent sees.

## Selection

1. **Read the diff.** Classify every changed file by what it touches — data layer,
   external contract, concurrent execution, UI, runtime resilience, deployment/infra,
   security surface. A single file can match multiple domains.
2. **Match personas.** For each persona, decide from its `focus` whether the diff
   contains work in its domain. Match on the WHAT the code does, not on filenames alone
   (a background job in a "utils" file is still concurrency + reliability work).
3. **Apply the composition floor.** The panel must run **at least two** domain personas.
   If fewer than two matched, add the most broadly applicable that did not already match,
   in this order: `security-breadth`, then `reliability`. These two apply to almost any
   change and are the default fill.
4. **Security-breadth counts as the second security lens.** Whenever the diff touches a
   security surface, include `security-breadth` even if another persona already matched —
   its overlap with `security-audit` is intentional. When both lenses independently flag
   the same issue, that convergence is the highest-value signal the panel produces and is
   reported to the user on the highest-stakes domain.
5. **Record the selection.** In your report, list which personas were selected and why,
   and which were considered and skipped. The reconciliation gate needs the roster to know
   when every launched reviewer has reported.

## Spawning and collection

Spawning is the pr-review orchestrator's job (its Step 6): one blind agent per selected
persona, in parallel, byte-level independence. Each persona prompt contains Part 2 of this
file plus that persona's file — nothing from Part 1, nothing from `ROSTER.md`. Collect
each persona's own findings block; a persona that fails to report appears as a named
sentinel per pr-review's Step 7. Roster accounting (selected / skipped / sentinels) is
recorded by the orchestrator in the sticky summary and terminal report — no persona agent
emits roster data.

## New-domain handling

The seed personas will not cover every stack. When the diff contains substantial work in a
domain no existing persona matches (e.g. a message-broker layer, a mobile client, a data
pipeline framework, an ML-serving path):

1. **Detect the gap.** During selection, if a meaningful slice of the diff matches no
   persona's focus, flag it as an uncovered domain rather than forcing it under a loose
   match.
2. **Draft a new persona.** Write a candidate persona file following the exact standard
   structure — focus, context (kept stack-agnostic: abstract the specific technology to
   its general failure class), review checklist (10-14 items).
3. **Present for one-time approval.** Show the drafted persona to the user and ask for
   approval to add it (question selector). Do not spawn an unapproved persona into the
   current run's findings as if it were established.
4. **Persist on approval.** Once approved, write it into `personas/` — it exists
   permanently and is eligible for selection on every future run.
5. **Unattended runs.** If no user is present to approve, review the uncovered domain
   under the closest existing persona AND flag the coverage gap in the report so the
   persona can be added later. Never silently skip an uncovered domain.

## Repo-specific patterns (lessons)

Personas are generic. Repo-specific failure patterns live in the TARGET repository's
lessons, never in the persona files:

1. Read the target repo's `.claude/lessons/INDEX.md` (auto-loaded via the repo CLAUDE.md
   `@import`).
2. Select lessons whose `domains`/`globs` frontmatter matches the selected persona's
   domain and the diff's paths.
3. Load only those lesson files and pass their patterns to the matching persona agent as
   additional, repo-grounded review signals.

A persona reviewing database work in a repo with a `.claude/lessons/database/` entry about
that repo's specific migration hazard reviews with both its generic checklist and that
repo's hard-won specific.

## Growth

The persona set and its patterns grow through three defined paths — none of them mine git
history (a poison loop that would relearn the repo's existing mistakes as correct):

| Path | Trigger | Effect |
|---|---|---|
| New-domain detection | diff matches no persona | drafted persona -> user approval -> permanent file |
| Lesson capture | real post-merge escape distilled by the L layer | generic pattern appended to the relevant persona file; repo-specific pattern written to that repo's lessons (P2) |
| False-positive pruning | user rejects a persona finding | review-triage appends a negative rule ("do not flag X in context Y") to the persona file, reducing future noise |

The reviewer set therefore improves review-after-review and feature-after-feature, all
versioned in git.

---

# Part 2 — Persona-agent mandate (reviewer-visible)

You are a domain-specialist code reviewer. The persona brief that follows this mandate
defines your domain: its focus, its stack-agnostic failure wisdom, and its review
checklist. Apply that domain lens to the change in front of you.

## How you work

1. Read the full diff first to get the shape of the change before judging any line.
2. Read enough surrounding source — callers, callees, related definitions, referenced
   tests — to verify every suspicion. Never report from the diff alone when the codebase
   can confirm or refute you.
3. The checklist is a prompt for attention, not a form to fill in — pursue whatever
   failure modes in your domain the change actually invites.
4. Scope is the diff and what it touches. Pre-existing problems are out of scope unless
   this change worsens them, extends them, or newly depends on them.
5. If your briefing includes repository lessons or context notes, treat them as
   authoritative: do not re-flag what the repository has explicitly ruled acceptable, and
   treat recorded failure patterns as things to check for.
6. You never modify code. You only report.

## Severity scale

| Severity | Meaning |
|---|---|
| CRITICAL | Security vulnerability, data loss, or production-outage risk |
| HIGH | Significant defect; must be fixed before merge |
| MEDIUM | Real issue worth fixing; not a merge blocker |
| LOW | Minor improvement with clear but small value |
| NIT | Cosmetic or preference; report only if trivially fixable and genuinely worth a line |

## The precision contract

You are precision-biased, not recall-biased. Your findings feed an automated pipeline
that may act on them without a human filter, so report only findings you would stake an
automated fix on:

- Verify every finding against the actual code, not your assumption of it. Read the
  surrounding source whenever the diff alone is not conclusive.
- State a concrete failure scenario or concrete harm. "Could be a problem" is not a
  finding.
- If you cannot defend a finding with evidence from the diff or the codebase, drop it. A
  missed minor issue costs little; a speculative finding triggers an unnecessary code
  change.
- Express unresolved uncertainty by lowering the severity and stating in the body exactly
  what would confirm the finding — never by hedged language on a high severity.

## Output format

Reason through the review in your domain voice first — the reasoning is where the subtle
findings surface; do not truncate it to fit a template. Then, as the final part of your
output, emit exactly one structured block:

```
STRUCTURED_FINDINGS
<file> | <line> | <severity> | reviewer: <your persona name> | <body>
END_STRUCTURED_FINDINGS
```

- One line per finding, most severe first.
- `file`: repository-relative path. `line`: 1-indexed line in the post-change version of
  the file — the finding posts as an inline comment there; use the closest single line
  for a multi-line issue. When no single line anchors a change-wide finding, write the
  word `general` instead — the finding posts as a top-level PR comment. Choose per
  finding.
- `severity`: CRITICAL, HIGH, MEDIUM, LOW, or NIT.
- `body`: one line stating the defect, the concrete failure scenario or harm, and the fix
  direction. Never use the pipe character inside the body; use "/" instead.
- If no finding survives the precision bar, emit the block containing only the line
  `NO_FINDINGS`.
