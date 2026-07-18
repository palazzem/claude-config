---
name: brainstorming
description: "Use when the user invokes /brainstorming, or when a request is genuinely ambiguous or feature-sized (new feature, new system, behavior change with architectural impact) - in that case SUGGEST this skill in one line and let the user decide; never auto-run it. Never suggest it for trivial work (small fixes, config edits, mechanical changes). Two gated stages - Understanding, then Design Overview - each red-teamed and user-approved, ending in a stored checkpoint spec. Never proceeds to implementation."
---

# Brainstorming

Turn a raw request into an approved, red-teamed design checkpoint. Stage 1 captures the reasoning chain behind the request (why, for whom, enabling what). Stage 2 fixes the recommended architecture before any implementation effort is spent. An adversarial reviewer attacks both stages. Each stage ends in an explicit user approval; the terminal state is a saved checkpoint, never implementation.

Flow:

1. Stage 1 Understanding: interview, fill the template, user approves.
2. Stage 2 Design Overview: options ranked by outcome quality only, self-check.
3. Adversarial review: skeptic red-teams both stages, findings presented to the user.
4. User approves the direction.
5. Checkpoint: write the artifact, store where the user chooses, ask what is next.

## Triggering

| Situation | Behavior |
|---|---|
| User invokes `/brainstorming` | Run the skill |
| Ambiguous or feature-sized request without it | Suggest in one line ("This looks feature-sized - run /brainstorming first?"), then follow the user's choice |
| Trivial work (small fix, config edit, mechanical change) | Never suggest, never run - this skill must not block trivial work |
| Unattended run | Gates cannot pass without a user. Produce the Stage 1 draft, record everything unresolved as open questions, stop, and flag it in the report |

Scale ceremony to the work: for a small-but-ambiguous ask, Stage 1 may be two or three questions and Stage 2 a short overview. The gates and the adversarial review remain; only the length shrinks.

## Repo profile

This skill contains zero repository-specific facts. Repo facts live in the repo profile - the harness's per-repo project memory, one JSON file per repository at `~/.claude/profiles/<owner>-<repo>.json` (fields include `trust`, `frontend`, `base_branch`, `launch_command`, `infrastructure`, `spec_location`; this skill uses `infrastructure` and `spec_location`). When a needed field is missing:

- Interactive: ask once via the question selector tool and write the answer back to the profile file.
- Unattended: use the safe default (treat as unknown / skip) and flag it in the report.

## Stage 1 - Understanding

Goal: capture the reasoning chain - the larger task, who it serves, what the output enables - not just the literal request. A request understood without its reasoning chain produces the wrong system with perfect acceptance criteria.

1. **Recon.** Read the project state relevant to the request: structure, docs, recent commits. If `.claude/lessons/INDEX.md` exists, load only the lessons whose domains or globs match the request's area - prior decisions inform the questions and the later design.
2. **Interview.** Ask in rounds via the question selector tool: batch the related questions you already know you need into one call (up to 4 per call), read the answers, then ask the next batch informed by them. Keep iterating rounds until the reasoning chain is fully understood - never stop at one round if open unknowns remain, and never stretch a batch across separate single-question messages. A question whose wording depends on an unanswered question belongs in a later round, not the same batch. Make each question self-contained (context in the question text, trade-offs in the option descriptions); prefer multiple choice, open-ended when needed. Drill into the chain: what larger task is this part of, who consumes the outcome, what does the outcome enable them to do, what observable result means "done".
3. **Draft the template.** Fill every field:

   | Field | Content |
   |---|---|
   | The task | The larger task this request is part of |
   | Who it is for | The person, team, or system that consumes the outcome |
   | What the output enables | What the consumer can do once this exists |
   | The request | The concrete ask, restated precisely |
   | Acceptance criteria | Observable, testable statements of done - each checkable by a command, a test, or a demonstrable behavior |

4. **Present and iterate.** Show the filled template. Revise on feedback until it is right.
5. **Gate.** Ask for explicit approval via the question selector tool. Do not start Stage 2 without it.

## Stage 2 - Design Overview

Present the recommended high-level architecture BEFORE any implementation. Follow the Decision Making procedure exactly:

1. Derive the requirements from the approved Understanding.
2. Design the correct system as if build resources were unlimited - that design is the recommendation.
3. Produce every genuinely different option - minimum 2, maximum 4 (different architectures, not parameter tweaks of one idea). "Unlimited resources" is not one option among them: it is the design condition ALL options are designed under. The set always contains the green-field option (what this would look like designed from scratch today); when the context makes them genuinely distinct, also an option that reshapes the existing system, and at most one unconventional option (a different paradigm worth considering). Never pad to a count with fillers; never cap at 3 when a fourth genuinely distinct architecture exists. Rank ONLY by outcome quality: correctness, security, maintainability, performance, operability. Nothing else ranks.
4. Lead with the winner on outcome quality, even when it is a big change.
5. Name every rejected alternative and why it lost.
6. If a genuine constraint forces a trade-down from the unlimited-resources design, present it as an explicit, named deviation for the user to approve. Never pre-trade silently.
7. Never calibrate options to the current codebase's quality - a bad codebase is context to fix, not a baseline to match. YAGNI applies to scope, never to structure; optimal is not maximal, so speculative abstraction is itself suboptimal.

**Banned ranking criteria** (they may be stated as facts, never used to demote an option): implementation time or effort, team size or skill, migration or rollout cost, review burden, "too complex to build", "MVP first / iterate later", phased delivery for effort reasons, backwards compatibility unless the user states it as a requirement.

**User-stated requirements override the ban.** When the user explicitly asks for an MVP, a prototype, speed, or compatibility, that is a stated requirement: design for it as scope and say which options honor it. The ban is on YOU introducing these criteria uninvited.

**Platform-context probe.** When the design touches a system boundary - messaging, storage, deployment, auth, or any external service - check the repo profile's `infrastructure` field for what actually exists (cloud provider, IaC, queues, databases, CI/CD). If unknown: interactive, ask once via the question selector tool and persist the answer to the profile; unattended, assume nothing exists, design against explicit abstractions, and record the unknown as an open question flagged in the report. A design chosen in ignorance of available infrastructure (a hand-rolled local queue where a managed pub/sub exists) is exactly the failure this stage prevents.

**Banned-criteria self-check.** Before presenting anything, scan the reasoning for banned criteria. If any influenced the ranking, redo the ranking without them. Only then proceed to the adversarial review.

## Adversarial review

Always runs - no exception for small designs, and it attacks BOTH stages. Spawn the skeptic agent via the Agent tool with `model: opus`, in design red-team mode. The skeptic is read-only.

Input to the skeptic: the approved Understanding template, the full Design Overview (all options, ranking, rejected alternatives, named deviations), and the relevant profile facts. Mandate - generative attack, not mere refutation:

- Holes and blind spots in the Understanding: wrong problem, missing consumer, acceptance criteria that are not observable or not testable.
- Unconsidered failure scenarios in the design: scale, partial failure, concurrency, security, operational and deployment realities.
- Unstated assumptions and missing integration constraints.
- The effort-free test, verbatim: "Would this design differ if effort were free? If yes, banned criteria leaked into the ranking - redo it."

Skeptic output: findings with severity (CRITICAL / HIGH / MEDIUM / LOW / NIT), each stating what is wrong, why it matters, and the question it raises.

Handling findings:

1. Present ALL findings to the user verbatim, alongside the design, each with your assessment: agree (will revise), disagree (with reasoning), or needs the user's ruling. Never silently absorb a finding into a revised design and never silently drop one.
2. If the effort-free test failed, redo the ranking before presenting anything.
3. Findings against the Understanding reopen Stage 1 - revise the template and re-approve it.
4. After a substantive revision, re-run the skeptic on the revised design. After 3 rounds, stop and escalate the surviving disagreements to the user as open questions.
5. **Gate.** Ask for explicit approval of the direction - chosen architecture plus any named deviations - via the question selector tool.

## Checkpoint

On approval, write the artifact:

| Section | Content |
|---|---|
| The task / Who it is for / What the output enables / The request / Acceptance criteria | The approved Stage 1 template, verbatim |
| Decisions | Chosen architecture, rejected alternatives with why, approved deviations, red-team findings and their rulings |
| Non-goals | What is deliberately out of scope |
| Delivery outline | Ordered PR-sized outcomes; each with an observable verification command (exact command plus expected result) |
| Open questions | Anything unresolved, including any unattended safe defaults that were flagged |

**Storage** - ask the user via the question selector tool:

- **GitHub tracking issue** - for repo or issue-tracked work. Use `gh`: update the existing tracking issue (`gh issue edit`) if one exists, otherwise create one (`gh issue create`). The spec is a user-owned artifact stored at the user's direction: no bot header, no mention of AI or tooling.
- **Markdown file** - for explorations. Location comes from the repo profile's `spec_location`; if missing, ask once and persist it.

**Lesson capture.** When Stage 2 settled a reusable platform decision (which messaging backbone, storage layer, or deployment path this repo uses), persist it so later brainstorms start informed: infrastructure facts go to the repo profile; the decision itself becomes a lesson in the target repo at `.claude/lessons/<domain>/<slug>.md` with YAML frontmatter (`name`, one-line `summary`, `domains: [list]`, `globs: [path patterns]`), and `.claude/lessons/INDEX.md` is regenerated (one line per lesson: summary plus domains) whenever a lesson is written. Leave the lesson in the working tree so it rides the first implementation PR; for a pure exploration with no repo, record the decision only in the checkpoint.

**Terminal state.** Report where the checkpoint was saved, then ask the user what is next via the question selector tool (for example: start implementation from the delivery outline, refine the spec, stop here). NEVER auto-invoke implementation or any other skill - the next step is always the user's explicit choice. The approved Design Overview recorded in Decisions is the architecture lock for whatever follows: downstream implementation carries it, and deviating from it requires escalation back to the user.
