# Harness overhaul: three-skill, three-agent delivery system

## The task

Rebuild the delivery workflow of this harness from ten interlocking skills and anonymous agent spawns into a minimal architecture: three skills that map one-to-one to process phases, three agent definitions that act as contracts, and no cross-skill coordination protocols.

## Who it is for

The harness operator, and every session that delivers code through the brainstorm, implement, review, and merge chain.

## What the output enables

- A workflow that can be understood by reading three skill files, where each skill owns a whole phase instead of sharing a loop through handoff protocols.
- Standalone review of any pull request, including ones the harness did not build.
- PR watching after human handoff without a dedicated runner agent per PR.
- Removal of the lessons system, which produced low-value output in practice.

## The request

Replace the current skill set (implement, pr-review, review-triage, pr-shepherd, gh-inline-comment) and agent usage with the architecture in Decisions, delete the lessons machinery everywhere, and keep brainstorming, push-pr, visual-evidence, receiving-code-review, and build-design-system as they are.

## Acceptance criteria

1. `ls ~/.claude/skills/` shows `implement`, `review-panel`, and `github-comment`; `review-triage`, `pr-shepherd`, and `gh-inline-comment` are gone.
2. `ls ~/.claude/agents/` shows exactly `builder.md`, `reviewer.md`, `skeptic.md`; `skeptic.md` frontmatter carries `effort: xhigh`; all three descriptions state capability only, never pipeline role.
3. `/review-panel <pr>` runs the full panel standalone on an arbitrary PR: persona selection, blind parallel reviews through the generic reviewer agent, skeptic verification, one batched inline review plus sticky summary.
4. A run of `/implement` on a small spec reaches an OPEN PR with a monitor armed by the main session, and a pushed commit on that PR produces a builder wake-up.
5. `grep -ri "lesson" ~/.claude/CLAUDE.md ~/.claude/skills/ ~/.claude/agents/` returns no operative instructions; `~/.claude/state/lessons/` does not exist.

## Decisions

### Architecture

Skills:

| Skill | Role |
|---|---|
| `brainstorming` | Unchanged process: interview, design, adversarial review, approved spec. Loses only its lesson references. |
| `implement` | The whole delivery chain, orchestrated by the main session, which never touches code: setup (worktree, branch), spawn builder with the spec, draft PR, review loop of at most three rounds invoking `review-panel` by name, finding triage (actionable to builder, human threads never auto-resolved, escalations via the two message types), OPEN flip, watch phase. |
| `review-panel` | The review panel standalone: persona roster (one line each: name, expertise, selection rule, preserving always-on vs conditional selection, the two-persona floor, and backfill order), a unified `personas/` directory, spawning through the generic reviewer agent, reconciliation gate, convergence dedup, skeptic verification with provenance stripped, marker-SHA re-review skip, public-repo redaction, sticky summary. |
| `github-comment` | Reusable gh library: inline comments and thread replies (absorbed from gh-inline-comment) plus monitor recipes (wait for CI, comments, merge) and the wake-the-builder dispatch pattern. |

Agents:

- `builder` - one per PR, persistent, three lifecycle phases: implement from the spec; fix during review rounds; watch after OPEN. In watch phase it acts on wake-ups: rebase when the base moves, fix CI, respond to and implement human feedback, clean up worktree and branch on merge.
- `reviewer` - one generic definition holding the review discipline and the single unified findings format. Per spawn it receives file paths: always its persona file; additionally the spec path when the persona needs design intent, so the design-conformance persona never infers the problem being solved.
- `skeptic` - unchanged role: adversarial verification of findings and design red-teams. Pinned `effort: xhigh` in frontmatter.

### Rulings

1. **Effort configuration dropped.** The `effort:` agent frontmatter field is ignored at runtime (anthropics/claude-code#64706), making per-agent effort routing impossible. Session effort, set once by the operator, governs all agents; the token cost is accepted. Exception: `skeptic.md` carries `effort: xhigh` anyway - inert until the bug is fixed, active the day it is.
2. **The main agent is an orchestrator only.** It never touches code. Its only watch-phase action is waking the builder when a monitor fires.
3. **Monitors belong to the main session.** Verified: a spawned subagent cannot receive monitor events. The main session arms one persistent monitor per shepherded PR; on any event it sends the builder a "PR updated" message and does nothing else.
4. **After OPEN, humans own the PR.** The builder's counterpart is the human on the PR thread: it asks questions there, and whoever requested a change reviews that change. No machine re-review after OPEN.
5. **Session death needs no machinery.** A dead session is resumed; context is preserved. No recovery registries, no status summaries.
6. **Reviewers read their own persona file.** The orchestrator passes a file path instead of injecting content, keeping persona bodies out of its context. The residual ability of a reviewer to list sibling personas is accepted.
7. **Neutral agent descriptions.** Every spawned subagent sees the roster of named agents with descriptions. Descriptions therefore state capability only; a description that names its place in the pipeline (as skeptic's does today) leaks the pipeline to blind reviewers.
8. **Lessons system removed entirely**, including rejection-driven pruning. Empirical basis: the post-merge pass generated six low-value, polluting lessons for a documentation PR.
9. **The panel stays a separate skill** so foreign PRs remain reviewable; `implement` references it by name and explains nothing about it.

### Rejected alternatives

- **Per-agent effort registry** (frontmatter pins, worker/runner shells): blocked by the runtime bug and dropped as over-configuration.
- **Full role registry** (every reviewer a named agent with its mandate as body): breaks the mandate-file append paths, forces duplicating the shared persona contract, and enlarges the roster leak.
- **Workflow-tool orchestration of the panel**: per-call effort exists there, but judgment-heavy loop steps and the persistent builder do not fit deterministic scripts.
- **Builder escalation via a fresh high-effort consultant**: a fresh agent cold-reads the code, reintroducing the handicap builder persistence exists to eliminate.

## Non-goals

- No effort configuration anywhere (see ruling 1).
- No replacement for the lessons system; anything future builds on built-in memory.
- `build-design-system`, `push-pr`, `visual-evidence`, `receiving-code-review` unchanged.
- Main-session effort remains a manual operator setting.

## Delivery outline

1. **PR 1 - Agents.** Rewrite `agents/builder.md` (three-phase lifecycle, neutral description); create `agents/reviewer.md`; reword `agents/skeptic.md` description and add `effort: xhigh`. Verify: spawn a reviewer manually with one persona file against a toy diff; the output format parses.
2. **PR 2 - Review panel.** Build `skills/review-panel/` from `pr-review`: roster and selection rules in the skill, thirteen mandate files unified under `personas/` with one output contract and growth markers stripped, spawning via the reviewer agent, chain-mode glue deleted. Verify: `/review-panel` end to end on a real small PR.
3. **PR 3 - github-comment.** Create `skills/github-comment/` from `gh-inline-comment` plus monitor recipes and the builder wake pattern; delete `gh-inline-comment`; repoint references. Verify: arm a monitor on a test PR, push a commit, observe the event and a message reaching a live agent.
4. **PR 4 - The chain.** Rewrite `skills/implement/` as the full orchestration (setup, builder, draft PR, review loop via `review-panel`, triage, OPEN flip, watch handoff per `github-comment`); delete `review-triage` and `pr-shepherd`. Verify: run the chain on a small real spec from checkpoint to OPEN PR with an armed monitor.
5. **PR 5 - Lessons removal.** Strip lesson machinery from `brainstorming` and CLAUDE.md (including rewriting the Review Workflow section to describe the new chain), sweep README, delete `~/.claude/state/lessons/`. Verify: acceptance criterion 5.

## Open questions

- When anthropics/claude-code#64706 is fixed, revisit per-agent effort pins. The gradient approved during this design, recorded for that day: builder high; skeptic xhigh (already set); security-audit, security-breadth, concurrency, correct-design xhigh; breaker, fresh-eyes, tests, database, reliability, infra, api-contracts high; frontend medium; standards low.
- `build-design-system`'s multi-agent build mode has no agent contract; it needs its own design pass.
