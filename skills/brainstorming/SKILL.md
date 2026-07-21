---
name: brainstorming
description: "Use when the user invokes /brainstorming, or when a request is genuinely ambiguous or feature-sized (new feature, new system, behavior change with architectural impact) - in that case suggest this skill in one line and let the user decide; never auto-run it. Never suggest it for trivial work (small fixes, config edits, mechanical changes). Two gated stages - Understanding, then Design Overview - each red-teamed and user-approved, ending in an approved spec."
---

# Brainstorming

Turn a raw request into an approved, red-teamed spec. Stage 1 captures the reasoning chain behind the request (why, for whom, enabling what). Stage 2 fixes the recommended architecture before any implementation effort is spent. An adversarial reviewer attacks both stages. Each stage ends in an explicit user approval.

Flow:

1. Stage 1 Understanding: interview, fill the template, user approves.
2. Stage 2 Design Overview: options ranked by outcome quality only, self-check.
3. Adversarial review: skeptic red-teams both stages, findings presented to the user.
4. User approves the direction.
5. Spec: write the full spec in the conversation and ask the user to approve it or give feedback; iterate until approved.
6. Destination: ask the user what to do with the approved spec (publish to GitHub, store as markdown via a PR, or implement it directly).

## Triggering

| Situation | Behavior |
|---|---|
| User invokes `/brainstorming` | Run the skill |
| Ambiguous or feature-sized request without it | Suggest in one line ("This looks feature-sized - run /brainstorming first?"), then follow the user's choice |
| Trivial work (small fix, config edit, mechanical change) | Never suggest, never run - this skill must not block trivial work |
| Unattended run | Gates cannot pass without a user. Produce the Stage 1 draft, record everything unresolved as open questions, stop, and flag it in the report |

Scale ceremony to the work: for a small-but-ambiguous ask, Stage 1 may be two or three questions and Stage 2 a short overview. The gates and the adversarial review remain; only the length shrinks.

## Stage 1 - Understanding

Goal: capture the reasoning chain - the larger task, who it serves, what the output enables - not just the literal request. A request understood without its reasoning chain produces the wrong system with perfect acceptance criteria.

1. Recon. Read the project state relevant to the request: structure, docs, recent commits.
2. Interview. Ask questions in batches via the question selector tool (it carries up to four questions per call - group related ones). Make each question self-contained (context in the question text, trade-offs in the option descriptions); prefer multiple choice, open-ended when needed. Drill into the chain: what larger task is this part of, who consumes the outcome, what does the outcome enable them to do, what observable result means "done".
3. Draft the template. Fill every field:

   | Field | Content |
   |---|---|
   | The task | The larger task this request is part of |
   | Who it is for | The person, team, or system that consumes the outcome |
   | What the output enables | What the consumer can do once this exists |
   | The request | The concrete ask, restated precisely |
   | Acceptance criteria | Observable, testable statements of done - each checkable by a command, a test, or a demonstrable behavior |

4. Present and iterate. Show the filled template. Revise on feedback until it is right.
5. Gate. Ask for explicit approval via the question selector tool. Do not start Stage 2 without it.

## Stage 2 - Design Overview

Present the recommended high-level architecture before any implementation. Follow the Decision Making procedure exactly:

1. Derive the requirements from the approved Understanding.
2. Design the correct system as if build resources were unlimited - that design is the recommendation.
3. Produce every genuinely different option - minimum 2, maximum 4 (different architectures, not parameter tweaks of one idea). "Unlimited resources" is not one option among them: it is the design condition all options are designed under. The set always contains the green-field option (what this would look like designed from scratch today); when the context makes them genuinely distinct, also an option that reshapes the existing system, and at most one unconventional option (a different paradigm worth considering). Never pad to a count with fillers; never cap at 3 when a fourth genuinely distinct architecture exists. Rank only by outcome quality: correctness, security, maintainability, performance, operability. Nothing else ranks.
4. Lead with the winner on outcome quality, even when it is a big change.
5. Name every rejected alternative and why it lost.
6. If a genuine constraint forces a trade-down from the unlimited-resources design, present it as an explicit, named deviation for the user to approve. Never pre-trade silently.
7. Never calibrate options to the current codebase's quality - a bad codebase is context to fix, not a baseline to match. YAGNI applies to scope, never to structure; optimal is not maximal, so speculative abstraction is itself suboptimal.

Banned ranking criteria (they may be stated as facts, never used to demote an option): implementation time or effort, team size or skill, migration or rollout cost, review burden, "too complex to build", "MVP first / iterate later", phased delivery for effort reasons, backwards compatibility unless the user states it as a requirement.

User-stated requirements override the ban. When the user explicitly asks for an MVP, a prototype, speed, or compatibility, that is a stated requirement: design for it as scope and say which options honor it. The ban is on you introducing these criteria uninvited.

Platform-context probe. When the design touches a system boundary - messaging, storage, deployment, auth, or any external service - establish what actually exists before designing against it: inspect the repository (architecture docs, relevant ADRs, IaC, databases, CI/CD) and, when still unclear, ask the user once via the question selector. Unattended: assume nothing exists, design against explicit abstractions, and record the unknown as an open question flagged in the report. A design chosen in ignorance of available infrastructure (a hand-rolled local queue where a managed pub/sub exists) is exactly the failure this stage prevents.

Banned-criteria self-check. Before presenting anything, scan the reasoning for banned criteria. If any influenced the ranking, redo the ranking without them. Only then proceed to the adversarial review.

## Adversarial review

Always runs - no exception for small designs, and it attacks both stages. Spawn the skeptic agent via the Agent tool in design red-team mode. The skeptic is read-only.

Input to the skeptic: the approved Understanding template and the full Design Overview (all options, ranking, rejected alternatives, named deviations). Mandate - generative attack, not mere refutation:

- Holes and blind spots in the Understanding: wrong problem, missing consumer, acceptance criteria that are not observable or not testable.
- Unconsidered failure scenarios in the design: scale, partial failure, concurrency, security, operational and deployment realities.
- Unstated assumptions and missing integration constraints.
- The effort-free test, verbatim: "Would this design differ if effort were free? If yes, banned criteria leaked into the ranking - redo it."

Skeptic output: findings with severity (CRITICAL / HIGH / MEDIUM / LOW / NIT), each stating what is wrong, why it matters, and the question it raises.

Handling findings:

1. Present all findings to the user verbatim, alongside the design, each with your assessment: agree (will revise), disagree (with reasoning), or needs the user's ruling. Never silently absorb a finding into a revised design and never silently drop one.
2. If the effort-free test failed, redo the ranking before presenting anything.
3. Findings against the Understanding reopen Stage 1 - revise the template and re-approve it.
4. After a substantive revision, re-run the skeptic on the revised design. After 3 rounds, stop and escalate the surviving disagreements to the user as open questions.
5. Gate. Ask for explicit approval of the direction - chosen architecture plus any named deviations - via the question selector tool.

## The spec

On approval of the direction, write the full spec in the conversation.

The spec is a build-ready artifact, not a summary of the conversation that produced it. Someone who never saw the interview must be able to implement it from the spec alone. That means real paths, real identifiers, real commands, real values, real defaults - prose that could describe any project is a defect.

Not every session earns every section. The Required column below decides: a required section always appears; an optional one appears when the work has substance for it and is omitted entirely otherwise - never kept as a heading with a placeholder or an "N/A" under it. A small session can be five sections long.

| Section | Required | Content |
|---|---|---|
| Problem statement | Yes | What is broken or missing today and why it matters. This opens the spec - no preamble about the request or the interview |
| Scope | Yes | What this spec builds, and where it lands: the directories, packages, or services it touches. When it is one slice of a larger effort, say which slice and what the other slices are |
| Design | Yes | The approved architecture made concrete: file and directory layout, module boundaries, and the data flow between them. Show the tree or the wiring when the structure is not obvious from prose |
| Components | No | One subsection per component. Its responsibility, its inputs and outputs as tables (name, type, description, default), the concrete resources, types, endpoints, or files it defines, and the reasoning behind any non-obvious choice. This is the section that makes the spec implementable - it is normally the longest |
| Environment and state | No | Configuration, secrets, and persistent state: exact variable names and defaults, what is committed versus ignored, how state is stored and bootstrapped, how components are wired together at deploy time. Omit when the work has none |
| Acceptance criteria | Yes | The observable criteria from the approved Understanding, carried forward with each one paired with its exact proof: a command with its expected result, a named test, or a demonstrable behavior. The pairing is the substance of this section - a criterion with no proof is not a criterion, so resolve it or drop it before presenting the spec, and never reduce this to a bare restatement of the list |
| Documentation | No | Which documents are created or updated, what each must cover, and to what standard. Omit when nothing changes |
| ADRs | No | Each decision that outlives this work, as a proposed ADR: file path, context, decision, consequences. Omit when the work sets no lasting precedent |
| Decisions record | No | A table - decision, choice, rationale - covering every decision the spec locks in: the chosen architecture, rejected alternatives and why they lost, approved deviations, red-team findings and their rulings, and the smaller calls settled along the way. One line each; point at the ADR where there is one |
| Delivery outline | No | Ordered PR-sized outcomes. Each names what it delivers and which acceptance criteria it satisfies. Every criterion must be claimed by exactly one outcome - an unclaimed criterion means the outline is incomplete |
| Delivery recommendation | No | Sequential or parallel, with reasoning: contained or hard-to-parallelize work runs as the implement chain's single builder; a large change whose delivery outline splits into independent units (for example an abstraction, its implementations, infrastructure, documentation) recommends parallel delivery - one builder and PR per independent unit |
| Out of scope | Yes | What is deliberately excluded, each with the reason or the condition that would bring it back in scope |
| Open questions | Yes | Only unresolved questions that require code-level verification to answer. Every question answerable by the user or by your own investigation must be answered before the spec is presented - ask or investigate, do not park it here |

Then ask the user to approve the spec or give feedback (question selector); iterate until approved.

## Destination

Once the spec is approved, ask the user what to do with it (question selector):

1. Publish to GitHub - a tracking issue via `gh issue edit` (existing) or `gh issue create` (new), written as a user-owned artifact: no bot header, no mention of AI or tooling.
2. Store as markdown - write the spec to a markdown file in a worktree and open a PR for it via the push-pr skill. The spec itself stays concrete; any architecture document, ADR, or README the same PR touches follows the documentation altitude rule - concepts, boundaries, and decisions, never file paths or symbol names.
3. Implement directly - invoke the implement skill with the approved spec; the full delivery chain runs from here.

The next step is always the user's explicit choice through this question - never assume one. Whatever the destination, the approved Design Overview recorded in the Decisions record is the architecture lock for whatever follows: downstream implementation carries it, and deviating from it requires escalation back to the user.
