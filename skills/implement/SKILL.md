---
name: implement
description: Use when the user asks to implement something — "implement X", "implement the brainstorm result", "build this spec". Manual entry point of the build chain (W2). Authors an implementation brief with an architecture lock, spawns one persistent builder agent, produces stacked draft PRs, then owns the review loop (W3) — pr-review rounds, review-triage fixes, the OPEN flip — and attaches pr-shepherd to merge. The user is contacted only via the two human-facing message types.
argument-hint: <what to implement> (optional) — a task description or a reference to an approved checkpoint/spec (issue URL, issue number, or file path)
---

# Implement

Manual entry, automatic chain. The user invokes this skill once; everything after — draft PR, review loop, ready flip, shepherding, merge — proceeds without further user prompts. The only user contact is the two message types fired later by the review loop (section 7) and the shepherd (see "The automatic chain" below).

Roles: the **main agent** (session model) authors the brief, spawns the builder, answers escalations, and owns the review loop of section 7. The **builder agent** (agent definition `builder`, which sets its own model) does all implementation work and is the only agent that writes code for this PR — now and in every later fix round.

## 1. Gather inputs

1. **Locate the approved checkpoint/spec.** The user may point at it ("implement the brainstorm result"); otherwise look for the tracking issue or checkpoint file produced by brainstorming for this task. Read it in full — especially its Decisions section and approved Design Overview.
2. **No checkpoint and the task is non-trivial** (new feature, ambiguous scope, touches system boundaries): offer brainstorming first via the question selector tool — offer, never require. If the user declines, or the task is trivial (small fix, mechanical change), derive the brief directly from the request.
3. **Read the repo profile** — the harness's per-repo project memory, one JSON file per repository at `~/.claude/profiles/<owner>-<repo>.json`. Fields needed here: `trust`, `base_branch`. For any missing field: ask the user once via the question selector tool and write the answer back to the profile file. In unattended runs, use the safe default (`trust: read-only`) and flag the assumption in the report.
4. **Trust gate.** `trust: read-only` means no pushes. Attended: surface this via the question selector tool — the user may update the profile or stop. Unattended: implement locally in the worktree only, report the branch location, do not push, do not continue the chain, and flag it.

## 2. Author the implementation brief (main agent)

Write an in-depth brief. It is the builder's entire world — assume the builder reads nothing else up front. Save it to `~/.claude/state/implement/<branch-slug>/brief.md`.

| Section | Content |
|---|---|
| Task summary | What is being built, for whom, what the output enables |
| Architecture lock | The approved Design Overview from the checkpoint, **verbatim**. Deviation by the builder requires escalation to the main agent — never silent. If a deviation would alter the approved overview, the user must approve and the checkpoint's Decisions section is updated |
| Acceptance criteria | Observable criteria from the checkpoint; each one checkable by a command or a described observation |
| Constraints | Repo profile facts (base branch, trust), house rules that bind the work, and any lessons relevant to the touched areas |
| Delivery outline | The checkpoint's ordered PR-sized outcomes, each a delivery unit: scope, files likely touched, tests to write, verification command + expected output |
| Escalation contract | The table from section 6, copied into the brief |

`<branch-slug>` = the feature branch name lowercased with every non-alphanumeric run replaced by a single hyphen (e.g. `feat/user-auth` → `feat-user-auth`).

## 3. Spawn one persistent builder

Spawn a single builder via the Agent tool:

- `subagent_type: builder` — the model comes from the agent definition; do not override it.
- **Stable name**: `builder-<branch-slug>`, using the slug of the feature branch. Naming is deterministic — any later skill derives it from the PR's head branch (`gh pr view --json headRefName`) and resumes the agent. No lookup files: the main agent coordinates the chain with full context, and the name itself is the cross-session key.
- Prompt = the full brief.

**Persistence rule (hard):** this same agent is resumed by name (SendMessage) for every later fix on this PR — review-triage fixes, CI fixes dispatched by the shepherd, escalation follow-ups. Never spawn a second builder for the same PR. A resumed agent keeps its transcript, so the implementation rationale survives the PR's whole life; a fresh fixer per round is forbidden.

**Workflow-based build:** if the user asked for a Workflow (multiple parallel workers), this skill works identically — each worker receives the same brief scoped to its delivery unit, uses the `builder` agent definition, gets its own stable name (`builder-<its-branch-slug>`), owns its own PR, and is bound by the same escalation contract. One persistent worker per PR; the persistence rule applies to each.

## 4. Build (builder)

1. **Worktree.** Create an isolated git worktree for the feature branch off `base_branch` (`git worktree add` from the repo root; use the using-git-worktrees skill if available). Never build on the user's checked-out branch.
2. **Adopt staged lessons.** Check `~/.claude/state/lessons/<owner>-<repo>/` for lessons staged by a previous merge's learning pass. If any exist, move them into the working tree's `.claude/lessons/<domain>/`, regenerate `.claude/lessons/INDEX.md`, commit them with this PR, and delete the consumed staging files — staged lessons ride the next PR, and this is that PR.
3. **Load lessons.** If the repo has `.claude/lessons/INDEX.md`, read it and load only the lessons whose `domains`/`globs` frontmatter match the delivery outline's paths and domains. Apply them as constraints.
4. **Implement the delivery outline as small PRs.** Stacked-PR tooling is deliberately not part of the workflow yet (`skills-disabled/prompt-graphite.md` reintroduces it when the tooling lands). Until then: independent delivery units become separate branches off `base_branch`, each its own PR; interdependent units land as ONE PR with the units as ordered commits — split only what is independently mergeable. Per-PR rules:

| Rule | Detail |
|---|---|
| Size | Under 400 substantive changed lines (docs, lockfiles, snapshots excluded). Soft cap: exceeding requires a stated justification in the PR body |
| Concern | Exactly one concern per PR |
| Tests | Each PR ships its own tests, written first where TDD applies (always for bugfixes: failing test, then fix) |
| Verification section | Every PR body carries a Verification section: the exact command to run and its expected output |

5. **Follow the architecture lock.** If the implementation cannot follow the approved overview, stop and escalate (section 6) — never deviate silently, never pick a "close enough" substitute.
6. **Commit hygiene.** Clear imperative messages. Never mention AI, Claude, or generation in commit messages or PR bodies. No emoji anywhere. Initial implementation commits carry no special trailer; only later autonomous commits that address review findings carry the git trailer `Harness-Fix: true`.
7. **Capture lessons in the working tree.** When work on this PR teaches something durable (a resolved escalation, a discovered constraint), write `.claude/lessons/<domain>/<slug>.md` with YAML frontmatter (`name`, one-line `summary`, `domains: [list]`, `globs: [path patterns]`), regenerate `.claude/lessons/INDEX.md` (one line per lesson: summary + domains), and commit both with the PR — lessons ride the PR that taught them.
8. **Push each completed delivery branch**: `git push -u origin <branch>` when the unit's implementation and tests are done. This initial branch push is the builder's job; it is the only push the builder makes — later review-round fixes are committed locally and batch-pushed by the dispatcher.

## 5. Push draft and hand off to review (main agent)

For each completed delivery unit:

1. **Push a DRAFT PR** via the push-pr skill in draft mode, targeting the profile's `base_branch`. When the checkpoint lives in a tracking issue or spec file, pass its reference to push-pr so the PR body links it — reviewers fetch the approved Design Overview from that link. PRs stay draft while machines iterate; this skill never runs `gh pr ready` — the review loop's terminal step flips it.
2. **Enter the review loop** (section 7) for this PR. Do not stop, do not ask the user, do not wait for permission between these steps.

## 6. Escalation contract (builder to main agent)

The builder escalates via SendMessage to the main agent, then stops and waits — never guesses, never works around:

| Trigger | Definition |
|---|---|
| Blocked | Missing access, tool, dependency, or environment the brief did not anticipate |
| Ambiguous requirement | The brief or checkpoint supports two or more materially different readings |
| Architecture deviation | The approved Design Overview cannot be followed as written |
| Repeated test failure | The same test still fails after two distinct fix attempts |

Main agent handling: answer from the checkpoint and brief when possible, then resume the builder by name with the ruling. If the answer would alter the approved Design Overview or genuinely needs a user decision, surface it to the user as a type 2 message, get the ruling, update the checkpoint's Decisions section, then resume the builder. Escalations and their resolutions are candidate lessons (section 4, step 7).

## 7. The review loop (W3 — main agent)

The main agent is the loop owner: it executes this section for each draft PR, in stack order, immediately after section 5, with no user prompts between steps. pr-review's chain contract and review-triage's chain sub-step mode both refer to "the caller" — that caller is this section.

Per PR, with `round` starting at 1:

1. **Panel round.** Invoke pr-review in chain mode, passing the round number and the architecture lock: the brief path (`~/.claude/state/implement/<branch-slug>/brief.md`) and the checkpoint reference — both from your own context; you authored the brief (the brief carries the approved Design Overview verbatim; pr-review routes it to its design-conformance check). Round 1 always runs.
2. **Triage.** Invoke review-triage in chain sub-step mode with the brief it documents: PR number, owner/repo, head SHA, builder agent name (`builder-<branch-slug>`, derived from the PR's head branch), round number, previously escalated thread ids, and `terminal: false`. It dispatches fixes to the resumed builder and returns the structured report.
3. **Visual evidence.** If the repo profile says `frontend: yes` and the PR HEAD differs from the evidence manifest's `head_sha` (or no manifest exists yet), invoke the visual-evidence skill on the PR. Unattended with `frontend` missing from the profile: skip and flag it in the report.
4. **Re-round decision.** Re-round ONLY if the triage report shows `substantive_fixes: true` AND the applied fixes were major — logic or design changes. Mechanical changes (lint, formatting, renames, comment edits, description sync) never re-trigger a round. Hard cap: 3 rounds total per PR. To re-round: increment `round` and go to step 1 — the explicitly passed round number tells pr-review this is a deliberate re-round.
5. **Terminal.** When no re-round is warranted or the cap is hit, invoke review-triage once more with the same brief plus `terminal: true` and the final escalated thread ids. It handles any residue, posts the escalation comment if needed, flips the PR OPEN with `gh pr ready`, and returns the human-facing message.
6. **Deliver the message** to the user exactly as returned — type 1 or type 2, nothing else, no rewording.
7. **Attach the shepherd.** Invoke pr-shepherd on the now-OPEN PR. It owns the PR from here to merge.

Terminal state of this skill: every delivery PR flipped OPEN with its message delivered and a shepherd attached. On read-only repos the chain stops at section 1's trust gate instead.

## The automatic chain (context — what happens after this skill)

Within this skill the chain runs sections 5 and 7 back to back: draft PR, panel, triage fixes by the resumed builder (fix commits carry `Harness-Fix: true`), bounded re-rounds, OPEN flip, message, shepherd. After the flip pr-shepherd owns the PR to merge; after merge its learning pass stages lessons that the next build's section 4 step 2 commits.

Exactly two human-facing message types exist:

| Type | Message | Fires when |
|---|---|---|
| 1 | "ready for your final review - push back or merge" | Review loop converged, PR flipped OPEN |
| 2 | "escalated items - findings pushed back with uncertainty, your call" | Unresolved escalations need the user; also posted as a top-level PR comment whose first line is `**Harness automated comment**` |

Never send any other user-facing prompt from inside the chain.
