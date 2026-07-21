# claude-config

Personal [Claude Code](https://docs.anthropic.com/en/docs/claude-code) harness — skills, agents, rules, and settings versioned as a git repository. It runs the software delivery pipeline from a raw idea to a merged pull request as a simple chain — brainstorm, implement, review loop, human review, merge and clean — so human attention is spent only where judgment is irreplaceable. You explain intent, approve the design, decide escalations, and merge; agents do everything in between, with no stored state: GitHub and the agents' own context are the only memory.

Full pipeline diagram and deep dive: [ARCHITECTURE.md](ARCHITECTURE.md).

## How it works

1. **Understand** (`brainstorming`) — Two gated stages, Understanding then Design Overview, turn a raw request into an approved spec. Each stage is red-teamed by the skeptic and needs your explicit approval. The spec lives in the conversation, published at most to a GitHub issue.
2. **Build** (`implement`) — The main agent orchestrates and never touches code: one persistent builder agent per PR writes all code and tests against the approved design and opens a draft PR. It escalates to you rather than silently deviating. Each builder is spawned with Claude Code's built-in worktree isolation, so it works in a locked worktree of its own and never in your checkout.
3. **Review** (`review-panel`) — A blind panel of persona reviewers, selected by the impact of the change, is spawned once per PR; the skeptic verifies findings; survivors post as one batched inline review, each finding marked fix-now or deferred to a follow-up PR. The builder fixes or rebuts, and the same reviewers are woken to re-check — three rounds without convergence stops the loop and escalates with a diagnosis. Then the PR flips open and you get one of two messages: "ready for your final review - push back or merge" or "escalated items - findings pushed back with uncertainty, your call". The panel also runs standalone on any PR.
4. **Watch to merge** — A monitor owned by the main session fires on comments, human reviews, CI, and pushes; its only action is waking the builder, which responds to feedback, fixes CI, rebases, and cleans up branch and worktree on merge. Final review and merge are always yours.

## Skills

| Skill | Purpose |
|---|---|
| `brainstorming` | Two gated stages — Understanding then Design Overview — each red-teamed and approved by you, ending in an approved spec. Manual; auto-suggested on feature-sized asks, never auto-run. |
| `implement` | Manual entry point of the delivery chain: persistent builder in an isolated worktree, draft PR, review loop via `review-panel`, open flip, one message, monitor watch. |
| `review-panel` | The multi-persona review panel with skeptic verification, posting one batched inline review per round; spawned once per PR, woken for re-checks; runnable standalone on any PR. |
| `github-comment` | Agent-facing gh library: batched inline reviews, thread replies and resolution, and the PR monitor plus wake-the-builder pattern. |
| `push-pr` | Creates or updates a pull request (draft inside the chain, usable manually anywhere) with the repo PR template filled when present, labels, and a Verification section. |
| `receiving-code-review` | Behavioral discipline for handling review feedback: verify before implementing, calibrated push-back, no performative agreement. |
| `build-design-system` | Builds a complete frontend design system from an approved design exploration. |

Deactivated skills live in `skills-disabled/`: `visual-evidence` (frontend visual proof) and the Graphite stacking prompt.

## Agents

| Agent | Role |
|---|---|
| `builder` | Persistent per PR: implements from the spec, opens the draft PR, fixes or rebuts review findings, keeps every push green through CI, then services the open PR (feedback, rebases) and cleans up on merge. |
| `reviewer` | Generic reviewer that adopts the persona file it is given and reports findings in one unified format. Read-only. |
| `skeptic` | Read-only adversarial verifier: refutes review findings with codebase evidence (refute-by-default) and red-teams brainstorm specs. Pinned to Fable 5 with `effort: xhigh`. |

Builder and reviewer inherit the session model and effort; the skeptic is pinned to Fable 5 with xhigh effort, and the push-pr body author runs on sonnet.

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
- [Playwright](https://playwright.dev/) — only if the visual-evidence skill is enabled; capture runs via `npx playwright`, browsers download on first use

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
