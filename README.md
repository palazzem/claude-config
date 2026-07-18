# claude-config

Personal [Claude Code](https://docs.anthropic.com/en/docs/claude-code) harness — skills, agents, rules, and settings versioned as a git repository. It runs the software delivery pipeline from a raw idea to a merged pull request, so human attention is spent only where judgment is irreplaceable. You explain intent, approve the design, decide escalations, and merge; agents do everything in between.

Full pipeline diagram and deep dive: [ARCHITECTURE.md](ARCHITECTURE.md).

## How it works

1. **Understand** (`brainstorming`) — Two gated stages, Understanding then Design Overview, turn a raw request into an approved design. Each stage is red-teamed and needs your explicit approval before anything proceeds.
2. **Build** (`implement`, `push-pr`) — One persistent builder agent per PR writes all code and tests against a locked architecture and opens a draft PR. It escalates to you rather than silently deviating from the approved design.
3. **Review** (`pr-review`, `review-triage`) — A blind reviewer panel and skeptic verifiers run on the draft PR, and triage dispatches fixes back to the builder for at most three rounds. When it converges the PR flips to open and you get one of two messages: "ready for your final review - push back or merge" or "escalated items - findings pushed back with uncertainty, your call".
4. **Keep green** (`pr-shepherd`) — A maintenance loop rebases the open PR, triages CI, and autofixes lint until merge, pinging you with those same two message types. It never merges, closes, or reviews — final review and merge are always yours.
5. **Learn** (lessons layer) — Every human intervention becomes a lesson committed alongside the PR that taught it, so future rounds need less of you. A merge-time pass distills anything missed.

## Skills

| Skill | Purpose |
|---|---|
| `brainstorming` | Two gated stages — Understanding then Design Overview — each red-teamed and approved by you, ending in a stored design checkpoint. Manual; auto-suggested on ambiguous or feature-sized asks, never auto-run. |
| `implement` | Manual entry point of the build chain: authors the brief with the architecture lock, spawns the persistent builder, produces draft PRs, and owns the review loop. |
| `push-pr` | Creates or updates a pull request (draft inside the chain, usable manually anywhere) with the repo PR template filled when present (generated body otherwise), labels, and a Verification section. |
| `pr-review` | Runs the blind, parallel reviewer panel with skeptic verification and posts one batched inline review plus a sticky summary; manually runnable on any PR. |
| `review-triage` | Classifies every review thread into one bucket, dispatches fixes to the builder, resolves handled threads, and escalates the rest; manually runnable on any PR. |
| `pr-shepherd` | Keep-green maintenance loop until merge: rebase, CI triage, lint autofix, description sync, and cleanup; manually attachable to any PR. |
| `visual-evidence` | Captures per-state screenshots and interaction GIFs for frontend PRs, commits them to the branch, and upserts an evidence comment. |
| `receiving-code-review` | Behavioral discipline for handling review feedback: verify before implementing, calibrated push-back, no performative agreement. |
| `build-design-system` | Builds a complete frontend design system from an approved design exploration. |
| `gh-inline-comment` | Internal, agent-facing technique for posting line-anchored PR comments through the gh API. |

## Agents

| Agent | Role |
|---|---|
| `builder` | Persistent per PR: writes all code and tests in the initial build and every fix round; escalates to the main agent when blocked or when the locked architecture would need to change. |
| `skeptic` | Read-only adversarial verifier: refutes review findings with codebase evidence (refute-by-default when uncertain) and red-teams brainstorm specs. |

## Model assignments

This table is the single source of truth for which model runs what.

| Component | Model |
|---|---|
| `builder` agent | opus |
| `skeptic` agent | opus |
| `pr-shepherd` loop runner | haiku |
| CI log classification (flaky vs legit) | sonnet |
| Mechanical fixes (lint autofix, description sync) | sonnet |
| `push-pr` body author | sonnet |
| `visual-evidence` capture runner | haiku |
| Everything else (main agent, panel reviewers, triage judgment, brainstorming, learning pass) | session model |

Here, session model means whichever model the Claude Code session was started with. The split is deliberate cross-model verification: every artifact is checked by a model different from the one that produced it, so a hallucination shared inside one model family cannot verify itself. Skills state the model when spawning agents (Agent tool `model` parameter).

## Lessons

Every human intervention becomes a lesson, committed alongside the PR that taught it, so future rounds need less of you. Lessons live in the target repository at `.claude/lessons/<domain>/<slug>.md`, scoped by domain and path globs. A regenerated `INDEX.md` is auto-imported into every session, so consumers load only the full lessons whose scope matches the work at hand.

## Setup

`~/.claude` already exists for every Claude Code user, so cloning directly over it collides with your current configuration. Clone elsewhere and copy the pieces you want:

```bash
git clone git@github.com:palazzem/claude-config.git ~/claude-config
```

On a fresh machine with no existing configuration, you can clone straight into the config directory instead:

```bash
git clone git@github.com:palazzem/claude-config.git ~/.claude
```

Prerequisites:

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI installed
- [GitHub CLI](https://cli.github.com/) (`gh`) installed and authenticated — all GitHub interactions go through `gh`
- PR stacking is deliberately not enabled yet; `skills-disabled/prompt-graphite.md` contains the ready-to-apply prompt that reintroduces it once Graphite (`gt`) is adopted
- [Playwright](https://playwright.dev/) — visual evidence capture runs via `npx playwright`; browsers download on first use

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
