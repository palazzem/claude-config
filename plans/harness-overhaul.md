# AI Harness Overhaul — Consolidation Plan

> **This file is the roadmap**: phase status, decision ledger (D-numbers), history. The designs
> themselves — skill specs, proposals, open questions (Q-numbers) — live in `harness-design.md`;
> read that one when reviewing or discussing the work.
>
> Living document. Every phase carries a **Decision Log** — as we work a phase, thoughts,
> decisions, and their rationale get appended there (dated). Nothing is deleted from a log;
> superseded entries get struck through.
>
> Status legend: 🔲 not started · 🟡 in progress · ✅ done · ⏸ blocked on decision

**Goal:** Rebuild the personal AI harness (`~/.claude`: skills, agents, rules, settings) around
the current Claude Code platform. Shrink what the platform now covers, keep what encodes
personal standards, and add a PR-lifecycle automation layer so the human's role converges to
"resolve ambiguity, review by observation, merge."

**Method:** Work phase by phase. Each phase that adopts an external design starts with its
customization interview (stack, tooling, models, autonomy) before any SKILL.md is written.
Decisions land in the phase's Decision Log first, then in code.

---

## 1. Current-state audit (2026-07-16)

Full analysis in session; condensed verdict per asset:

### Keep (rewrite in place)

| Asset | Why keep | What to fix |
|---|---|---|
| `skills/receiving-code-review` | Verification-before-implementation + score-calibrated push-back is the harness's soul; no built-in equivalent | De-obra-fy ("your human partner", Circle K); becomes the triage philosophy module for the new pipeline |
| `skills/push-pr` | Concrete, mechanical, correct | Model pin (sonnet) → revisit; bot-identity policy alignment |
| `skills/build-design-system` | Modern, aligned with current tooling | Nothing significant |
| `skills/brainstorming` | Question discipline + diverge-before-converge still add value; but mis-scoped as a pipeline | Redesign around the alignment-checkpoint outcome model (design doc §6.4, D11): drop HARD-GATE, review loop, and mandatory writing-plans terminal |
| ~~`skills/writing-plans`~~ | ~~TDD-granular plans~~ **Retire (D11, proposed)** — briefs a weak executor; pre-written plan code is unverified, stale, authority-inverting for Fable-class models | Surviving value (scope-slicing, verification criteria, non-goals) moves into the spec's delivery outline |
| Repo strategy (ignore-all `.gitignore` + whitelist) | Right way to version `~/.claude` | Whitelist `rules/`, `plans/`; drop dead `statusline.sh` entry |
| `CLAUDE.md` core rules | Mostly sound | Review-workflow section rewritten in Phase 5; bot-identity carve-out added |

### Replace with built-ins (delete after replacement lands)

| Asset | Replaced by |
|---|---|
| `skills/ask-claude-review` + `agents/code-reviewer` | New review pipeline wrapping `/code-review` (Phase 2) |
| `skills/pull-review-comments` | New `review-triage` skill (Phase 2) |
| `skills/using-git-worktrees` | Native `isolation: "worktree"` / `EnterWorktree` |
| `skills/swarm-development` + `agents/swe-planner`, `swe-implementer`, `staff-engineer` | `Workflow` tool + Agent tool (pending Phase 1 decision D6) |

### Delete outright (Phase 0)

- `superpowers/` — full clone of obra/superpowers, not installed as a plugin, four skills already forked from it; `pull-review-comments` still references the unresolvable `superpowers:receiving-code-review`
- `settings.json.bak`, `settings.json.orig`
- Stale README content (rewritten Phase 5)

### Broken infrastructure found

- All 4 agents whitelist ~10 `mcp__serena__*` tools; **serena is not configured anywhere** (only context7 is). Restrictive `tools:` lists carry dead entries and lock agents out of new tools.
- All agents pin `model: opus[1m]`; session model is `claude-fable-5[1m]`.
- `swarm-development` depends on `TeamCreate`/`team_name`/`shutdown_request` from the experimental agent-teams API; `team_name` is now deprecated (single implicit team) — the protocol likely no longer executes as written. `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` still set in settings.
- `rules/context7.md` is live config but untracked (gitignore doesn't whitelist `rules/`).
- README documents skills that no longer exist (`writing-bug-report`, `writing-prd`), wrong reviewer count.
- `hooks/` empty; no hooks configured despite hook-able hard rules.

---

## 2. External designs analyzed (2026-07-16)

| Source | Concept | Verdict |
|---|---|---|
| pauldambra `qa-swarm` | Heterogeneous reviewer panel → structured findings → convergence dedup → inline PR comments + sticky upserted verdict summary; mandatory bot-identifier header | **Adopt** (fused with review-triage, Phase 2). Replace PostHog-store reviewers with own mandates; consider wrapping `/code-review` |
| pauldambra `review-triage` | Every unresolved thread → exactly one bucket: actionable (fix+push+silent resolve) / nit (silent resolve, reason in report) / ambiguous (autonomy ladder before deferring) / human-touched (never touch, never reply). Never posts replies. Context-engineered fetches (1500-char heads, refetch-before-act). Terminal state: only ambiguous+human left | **Adopt** (Phase 2). Highest-value item; autonomy ladder fuses with receiving-code-review's push-back calibration |
| haacked `babysit-prs` | Idempotent sweep over all open PRs; state file (head SHA, CI conclusion, last comment) makes quiet PRs cost zero API calls; dispatches per-PR skills; driven by `/loop`; never force-push/merge | **Adopt** (Phase 3). Fills the "PR created → human is the polling loop" gap. Copy the quiet/active state design faithfully (incl. the updatedAt-only-when-terminal-green subtlety) |
| PostHog `pr-approval-agent` (stamphog) | Label-triggered CI system: deterministic gates first (deny-list, size ceilings, tiers), LLM showstopper review that can tighten but never loosen, fail-closed everywhere, approve-as-real-review, sticky comment otherwise, evidence bundles | **Adopt last, downscoped** (Phase 6, optional). Per-repo infra, not a skill; empirical calibration won't transfer to low-volume personal repos — thresholds will be judgment, admit it. Consider gates+verdict-comment without approval authority first |
| Stacked small PRs (prompt) | <400-line single-concern PRs, each with tests + observable proof (command + expected output) | **Adopt** (Phase 4). Force multiplier: makes panels sharp, triage decisive, gates passable. Requires stacking-tool decision (D8) |
| Frontend visual evidence (prompt) | Per UI PR: screenshot per state, GIF of key interaction, before/after, attached to PR, re-captured on head-SHA change | **Adopt** (Phase 4). Zero overlap with anything existing; playwright plugin currently disabled; GitHub image-attachment needs a storage decision (D9) |

---

## 3. Target architecture

```
authoring                      review                         merge
─────────                      ──────                         ─────
brainstorming ─► writing-plans ─► stacked PRs (<400 lines, observable)
                                      │
                                      ▼
                              pr-review (panel: /code-review wrap + custom mandates)
                                      │  posts inline threads + sticky verdict
                                      ▼
                              review-triage (burn down: fix / resolve / defer)
                                      │  visual-evidence for UI PRs
                                      ▼
        /loop ─► babysit-prs ─► sweeps ALL open PRs: CI, threads, freshness
                                      │
                                      ▼
                     [optional] approval gate (stamphog-lite, per repo)
                                      │
                                      ▼
                        human: resolve ambiguity, observe, merge
```

Target skill inventory when done:
`brainstorming` (redesigned, D11), `receiving-code-review` (rewritten), `push-pr`,
`pr-review` (new), `review-triage` (new), `review-cycle` (new), `babysit-prs` (new),
`stacked-prs` (new), `visual-evidence` (new), `build-design-system`, plus built-ins
(`/code-review`, `/verify`, `/loop`, `Workflow`). `writing-plans` retired per D11.

---

## 4. Cross-cutting decisions

Numbered so phase logs can reference them. **OPEN items block dependent phases.**

| # | Decision | Status | Current position |
|---|---|---|---|
| D1 | Adoption set | ✅ Ruled | Adopt review pipeline + babysit + conventions. stamphog NOT adopted — Phase 6 shelved. **Staged rollout:** every new skill is built under `skills-disabled/` (not loaded by the harness) and promoted to `skills/` individually once validated |
| D2 | Bot identity on autonomous GitHub posts | ✅ Ruled | Compact bot header on every autonomous post; "never mention AI" narrowed to authored artifacts the user reviews and owns (PR descriptions, commits) |
| D3 | Panel core: wrap `/code-review` vs fully custom | ✅ Ruled | Fully custom panel — full control over reviewer identities, models, output format. Consequence: the panel must ship its own adversarial verification stage, since the built-in's verify pass is lost |
| D4 | Model policy for agents/skills | ✅ Ruled | User decides per component, explicitly. Proposed assignment table in design doc §2.4, pending sign-off (O2) |
| D5 | Pipeline shape | 🟡 Pending nod | v2 recommendation mirrors the sources: 3 skills — pr-review (generation), review-triage (dual-mode consumption), pr-shepherd (loop); no separate review-cycle (design doc §3.4, O4) |
| D6 | Swarm stack fate | ✅ Ruled | Delete swarm-development + 3 swe/staff agents. Successor for staff-engineer: single read-only `skeptic` agent (verification stage + spec red-team), pending panel ruling O1/O3 |
| D7 | Hooks adoption | **OPEN** | Candidates: PreToolUse guard on `git commit` (block "Generated with Claude" mentions), lint/format post-edit. Keep minimal; explore in Phase 5 |
| D8 | PR stacking tool | ✅ Ruled | Graphite (`gt`) |
| D9 | Visual-evidence storage | ✅ Ruled (provisional) | Commit into the PR branch under `.github/pr-evidence/`; user will revisit at first real use |
| D10 | Which repo pilots the approval gate; approval authority or verdict-comment only | **OPEN** | Phase 6 interview; verdict-comment-only recommended first |
| D11 | Authoring pipeline: brainstorming outcome model + writing-plans fate | ✅ Ruled | Brainstorming redesigned per design doc §6.4 (auto-suggest never block; spec home by context); **writing-plans deleted now** — no validation milestone (P3) |
| D12 | Rollout model (supersedes D1's staged promotion) | ✅ Ruled | P3 one-shot delivery: the full plan is built at once into `skills-disabled/`; user enables, trials the complete system, iterates via feedback. Phases 2–4 collapse into one Build phase |
| D13 | Global principles | ✅ Ruled | Optimal-first option generation, generic-skills + per-repo profiles, no-emoji professional output — promoted to global CLAUDE.md rules (Decision Making + Claude Code sections) |
| D14 | Staging mechanism (supersedes D12's `skills-disabled/` directory, keeps its one-shot delivery) | ✅ Ruled | The Build phase runs on a dedicated git worktree/branch (`harness-v2`): skills are built live under `skills/` on the branch, which is not the harness's active config until merged. The branch is the trial gate — the user trials from the worktree, then merges to enable. `skills-disabled/` is not used and gets no `.gitignore` whitelist |

### Decision Log

- 2026-07-16 — Plan created. D1–D3 were asked and not yet answered; carried as OPEN.
- 2026-07-16 — Constraint noted: session model `claude-fable-5[1m]`, effort xhigh; only MCP is context7; gh CLI authenticated; token economy explicitly not a concern (CLAUDE.md).
- 2026-07-17 — D1 ruled: adopt pipeline + babysit + conventions; stamphog shelved. User added a staged-rollout mechanism: build new skills in `skills-disabled/`, promote to `skills/` one at a time.
- 2026-07-17 — D2 ruled: bot header on all autonomous posts; CLAUDE.md carve-out wording lands in Phase 5.
- 2026-07-17 — D3 ruled: fully custom panel (against the wrap recommendation) — full control over reviewers preferred; Phase 2 gains a mandatory verification stage to compensate.
- 2026-07-17 — Phase 0 executed. Extra finding: agents' `mcp__plugin_context7_context7__*` tool names were stale too (context7 now runs as a global MCP server, not a plugin) — replaced with `mcp__context7__*`.
- 2026-07-18 — D14: the `harness-v2` worktree/branch replaces `skills-disabled/` as the staging and trial mechanism for the Build phase. One-shot delivery (P3/D12) is unchanged — everything is still built complete before the user trials it; only the isolation mechanism moved from a disabled directory to a branch. Earlier `skills-disabled/` references in this file are historical.

---

## Phase 0 — Foundation & hygiene ✅ (2026-07-17)

No decisions needed; safe regardless of D1–D10.

- [x] Delete `superpowers/` clone
- [x] Delete `settings.json.bak`, `settings.json.orig`
- [x] `.gitignore`: whitelist `rules/`, `plans/`, `skills-disabled/`; remove `statusline.sh` entry
- [x] Commit `rules/context7.md` and this plan
- [x] Remove `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` env from settings.json
- [x] Strip dead `mcp__serena__*` entries from all agent `tools:` lists (interim fix; agents may be deleted later per D6)
- [x] Fix stale plugin-scoped context7 tool names in agents (`mcp__plugin_context7_context7__*` → `mcp__context7__*`); drop the "Use Serena tools" instruction from swe-planner

### Decision Log

- 2026-07-16 — Serena cleanup is interim: if D6 deletes the swe/staff agents, only surviving agents need the fix.
- 2026-07-17 — Executed and committed. Teams env flag removed while D6 is still open: whichever way D6 goes (delete swarm, or rebuild on the current built-in teams surface), the legacy experimental flag has no place in the outcome.

---

## Phase 1 — Architecture decisions 🟡 (blocks 2, 3, 4)

Resolve D1–D6 with the user. Output: updated decision table above + target inventory confirmed.

- [x] D1 adoption set confirmed
- [x] D2 bot-identity policy ruled (CLAUDE.md wording lands in Phase 5)
- [x] D3 panel core chosen
- [ ] D4 model policy ruled
- [ ] D5 separability confirmed
- [ ] D6 swarm fate ruled
- [ ] Detailed design document (`plans/harness-design.md`) discussed and approved — gates Phases 2–4

### Decision Log

- 2026-07-16 — Seeded with recommendations from the two analysis sessions (see §4).
- 2026-07-17 — D1–D3 ruled (see §4 log). Remaining: D4 (model policy), D5 (separability sign-off), D6 (swarm fate).
- 2026-07-17 — User: phases alone aren't enough — the work itself must be designed and discussed before Phases 2–4. Created `plans/harness-design.md`: discovery-grounded per-skill designs (pr-review, review-triage, review-cycle, babysit-prs, stacked-prs, visual-evidence, receiving-code-review rewrite), trust-tier model for cross-owner autonomy, interaction map, and a numbered interview backlog. Approval of that document is now a Phase 1 exit criterion.
- 2026-07-17 — In-depth brainstorming review (user-requested) → D11 proposed: brainstorming redesigned around alignment-checkpoint outcomes; writing-plans retired, delivery outline moves into the spec. Design doc §6.4; questions Q13–Q16. File roles clarified after user confusion: overhaul = roadmap, design = the document to read.
- 2026-07-17 — Full interview executed (5 selector batches, user-requested "all at once"). Rulings in design doc §9. Major redirections: babysit → per-PR `pr-shepherd` (not a global sweeper); rebase+force-push-with-lease allowed; no repo lists in skills (per-repo profiles via ask-once memory); optimal-first principle set after user critique of effort/migration-biased option generation; panel architecture reopened as big-picture discussion (design doc §3, open item O1); P3 one-shot delivery replaces staged promotion (D12). Global principles promoted to CLAUDE.md (D13). Remaining opens: O1–O4 (design doc §8) + D7 (hooks, never asked).

---

## Build phase — FINAL execution plan (approved 2026-07-18)

Design finalized in `harness-design.md` (§8-bis chain, v1→v5). Phases 2–4 below are SUPERSEDED
by this task list; kept for history only. One-shot delivery (D12): all tasks built completely
into `skills-disabled/`, then user trial.

| # | Task | Delivers | Status |
|---|---|---|---|
| 0 | Foundations: boundaries + memory prompts into CLAUDE.md (Decision Making overhaul done 2026-07-18); `builder` (Opus) + `skeptic` (Opus) agents; repo-profile + lesson-format conventions (frontmatter, path globs, INDEX.md, CLAUDE.md import); `gh-inline-comment` command (wrap cli/cli#359 technique); remove 5 skills + 4 agents | ground | ✅ |
| 1 | `brainstorming`: understanding template (task · who · enables · request · acceptance criteria); **Stage 2 Design Overview gate** (unlimited-resources design, options ranked by outcome only, green-field present) + platform-context probe; breaker red-team over both stages incl. banned-criteria hunt; storage ask | W1 | ✅ |
| 2 | `implement`: Fable brief (carries the **architecture lock**) → persistent Opus `builder` per PR (single-agent + Workflow modes; escalation contract incl. architecture deviations) → worktree → stacked PRs (Graphite) → tests → **draft PR**; manual entry, automatic chain | W2 | ✅ |
| 3 | `pr-review`: 7 reviewers (fresh-eyes, breaker, tests, standards, correct-design w/ conformance-to-approved-design + banned-criteria lens, security-audit, qa-domains persona engine) with lesson-scoped loading; Opus skeptics + reproducers; per-reviewer inline-vs-general posting; bounded re-rounds (max 3, only on major changes) | W3 | ✅ |
| 4 | `review-triage`: fixes via resumed builder; resolve/escalate buckets; lesson commits ride the PR; two message types; **draft→OPEN flip when humans enter** | W3 | ✅ |
| 5 | `pr-shepherd`: Haiku maintenance routine (rebase, conflicts, flaky rerun, lint, description sync, pings); code work dispatched to builder; merge detection → Fable learning pass; cleanup | W4 | ✅ |
| 6 | Learning layer: target-repo `.claude/lessons/` + INDEX.md + glob/domain-scoped retrieval; capture writers in triage/shepherd/brainstorming; Fable merge pass; staging for post-merge finds | L | ✅ |
| 7 | `visual-evidence`: auto per repo profile (frontend), screenshots per state + interaction GIFs on the PR | W3 extra | ✅ |
| 8 | Reconciliation: **README.md describing the entire workflow with a mermaid diagram** (pipeline, roles, triggers, learning loop, how to enable); CLAUDE.md workflow section; commit-message guard hook; align `push-pr`; slim `receiving-code-review`; final commit | closes | ✅ |

## Phase 2 — Review pipeline core 🔲 SUPERSEDED (see Build phase final plan above)

Start with the user's customization interview: stack, tooling, available models, autonomy
boundaries — what gets auto-fixed vs. only reported, what may be posted to GitHub.

All new skills in this phase are built under `skills-disabled/` (D1 staged rollout).

- [ ] Interview (per user's original prompt for this skill)
- [ ] Rewrite `receiving-code-review`: own voice, keep push-back calibration, absorb the autonomy ladder (just-do-it / recommend-and-flag / stop-and-ask)
- [ ] Build `pr-review`: fully custom panel per D3, personal mandates (DRY, comments, no-workarounds, tests, perf — inherited from ask-claude-review's 7), convergence dedup, inline comments as single review, sticky upserted verdict summary with round history, bot header per D2
- [ ] Verification stage inside `pr-review`: adversarial verify pass on every finding before posting — independent skeptic agents prompted to refute, not self-review by the finder (compensates for not wrapping `/code-review`, D3)
- [ ] Build `review-triage`: bucket invariant (actionable/nit/ambiguous/human — every thread ends in exactly one), human-participation gate (any human in thread → never touch, never reply), silent resolves with report audit trail, 1500-char fetch heads + refetch-before-act, stale-review SHA-sniffing, terminal condition = only ambiguous+human left
- [ ] Thin fused entry point (`/pr-review` then `/review-triage`, loop until terminal)
- [ ] Verify end-to-end on a real PR in a low-stakes repo (run from `skills-disabled/` by direct path)
- [ ] Promote to `skills/`; retire `ask-claude-review`, `pull-review-comments`, `agents/code-reviewer`; update CLAUDE.md workflow references

### Decision Log

- 2026-07-16 — Key fusion insight: the autonomy ladder and receiving-code-review's score-calibrated burden of proof are the same mechanism; unify rather than layering both.
- 2026-07-16 — Context-economy details from review-triage (truncated fetches, one-full-body-at-a-time) are load-bearing for /loop affordability — copy faithfully, don't simplify away.
- 2026-07-17 — D3 fell to fully custom: the panel owns finding verification now. Without it we'd rebuild ask-claude-review's core flaw (unverified findings flowing straight into triage).

---

## Phase 3 — Outer loop (babysit-prs adaptation) 🔲

Ground the interview in discoverable facts (open PRs, gh auth, clone layout under
`~/workspaces/`) before asking anything; then ask only what's left: extras menu (CI
monitoring, branch freshness, flaky reruns, lint/format autofix, drifted artifacts,
description sync) and runner model (D4).

- [ ] Discovery: enumerate open PRs, clone/worktree layout, CI systems in use
- [ ] Interview (per user's original prompt)
- [ ] Build `babysit-prs`: single idempotent sweep; state file keyed by PR URL (head SHA, CI conclusion, last-comment ts); quiet/active classification incl. updatedAt-only-when-terminal-green rule; dispatch `review-triage` per active PR via spawned agent; chosen extras; hard rails (never force-push/merge/close); state pruning; summary table
- [ ] CI-failure handling: decide sub-skill vs inline classification (flaky vs legit) — his `ci-monitor` has no direct equivalent here
- [ ] Wire to `/loop`; document cadence guidance
- [ ] Unattended dry-run across all open PRs, then a supervised live run
- [ ] Build under `skills-disabled/`; promote to `skills/` only after the supervised live run (D1 staged rollout)

### Decision Log

- 2026-07-16 — Mendral flake-reporting and dotfiles worktree lib are the non-portable pieces; worktree logic maps to native worktree support.

---

## Phase 4 — Working conventions 🔲

- [ ] D8: pick stacking tool; trial on one real feature
- [ ] Build `stacked-prs` skill: <400-line single-concern rule, stack ordering, per-PR tests + observable proof (command + expected output — integrates `/verify`), restack-after-merge procedure for the chosen tool
- [ ] Update `writing-plans`: plan tasks map to stack units; observable proof becomes part of each task's definition of done
- [ ] D9: pick evidence storage
- [ ] Re-enable playwright plugin in settings.json
- [ ] Build `visual-evidence` skill: state screenshots (empty/loading/error/populated), interaction GIF, before/after on behavior change, attach per D9, head-SHA keyed re-capture (same state pattern as babysit — consider making it a babysit dispatch task)
- [ ] Verify on a real frontend PR (diet-app or resource-planner)
- [ ] Both skills built under `skills-disabled/`; promote individually once validated (D1 staged rollout)
- [ ] Redesign `brainstorming` per design doc §6.4 (D11): adaptive process, alignment-checkpoint outcomes, spec format with delivery outline
- [ ] Retire `writing-plans` after the spec format is validated on one real feature (D11); update `swe-planner`/CLAUDE.md references per D6 outcome

### Decision Log

- 2026-07-16 — Rationale for the 400-line cap: stamphog's data shows auto-review reliability collapsing past ~800 substantive lines; personal cap set at half that.

---

## Phase 5 — Rules, agents, docs reconciliation 🔲

- [ ] Rewrite CLAUDE.md review-workflow section around the new pipeline; add D2 bot-identity carve-out
- [ ] Execute D6: delete or rebuild swarm assets; repoint brainstorming's spec-review step
- [ ] Soften brainstorming HARD-GATE scope
- [ ] D7: implement chosen hooks (commit-message guard first candidate)
- [ ] Rewrite README.md to match reality
- [ ] Sweep: no skill references a deleted skill/agent; no dead tool entries; no stale model pins
- [ ] Final commit + tag the overhaul

### Decision Log

- (empty)

---

## Phase 6 — Approval gate (stamphog-lite) ⛔ shelved (D1, 2026-07-17)

Preserve the invariants exactly: fail closed, never request changes, never merge, LLM
tightens but never loosens. Re-derive policy from own history knowing the data is thin —
mine git history for deny-list candidates, calibrate ceilings from merged PRs, present the
full gate config for sign-off before writing code. Leave results uncommitted for review.

- [ ] D10: pilot repo + authority level (verdict-comment-only first)
- [ ] Interview: CI system, trigger label, escalation routing (no CODEOWNERS), LLM/SDK, credential delivery to CI
- [ ] History mining + proposed gate config → sign-off gate
- [ ] Build: gates → classify → LLM pipeline + workflow file, evidence bundle
- [ ] Dry-run mode on recent merged PRs before enabling the label trigger

### Decision Log

- 2026-07-16 — Honesty note: PostHog calibrated on 356 approved + ~440 denied PRs; personal repos have dozens. Thresholds here are judgment informed by their published numbers, not local data.
- 2026-07-17 — Not adopted in D1; shelved. Revisit only if a repo gains branch-protection approval requirements or PR volume that justifies the infrastructure.

---

## Status tracker

Per D12 (one-shot delivery), Phases 2–4 collapse into a single **Build** phase executed at once.

| Phase | Status | Blocked on |
|---|---|---|
| 0 — Foundation & hygiene | ✅ | — |
| 1 — Architecture decisions + detailed design | ✅ (approved 2026-07-18) | — |
| Build — final task list 0–8 above, one shot on the `harness-v2` branch (D14) | 🟡 in progress | user trial + merge |
| 6 — Approval gate | ⛔ shelved | — |
