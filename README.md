# claude-config

A versioned `~/.claude` that turns Claude Code into a disciplined engineer.

```text
  DEFINE     /spec            ── agent-skills
    │
  DELIVER    /deliver         ── this repo
    │
  PLAN       /plan            ┐
    │                         │
  BUILD      /build           │
    │                         │
  SIMPLIFY   /code-simplify   ├─ agent-skills
    │                         │
  REVIEW     /review          │
    │                         │
  GATE       /ship            ┘
    │
  STACK      /gh-stack        ┐
    │                         ├─ this repo
  WATCH      /shepherd        ┘
```

## Requirements

- Claude Code
- System packages: `gh`, `jq`, `npm`

## Quick Start

The following instructions are meant for a fresh installation where Claude Code doesn't
have a global `~/.claude` config folder yet:

```bash
# Custom Harness
git clone git@github.com:palazzem/claude-config.git ~/.claude

# Agent-skills plugin
claude plugin marketplace add addyosmani/agent-skills
claude plugin install agent-skills@addy-agent-skills

# GitHub configuration
gh auth login
gh extension install github/gh-stack

# Claude Code Statusline
npm install -g ccstatusline
mkdir -p ~/.config/ccstatusline
cp ~/.claude/statusline/ccstatusline-config.json ~/.config/ccstatusline/settings.json

claude
```

## Commands

Development lifecycle commands come from agent-skills

| What you're doing | Command | Key principle |
| --- | --- | --- |
| Define what to build | `/spec` | Spec before code |
| Run everything after `/spec` in one pass | `/deliver` | Build, simplify, and review once per PR, then gate the whole change |
| Plan how to build it | `/plan` | One PR per concern, atomic tasks |
| Build incrementally | `/build` | One slice at a time |
| Split a change into dependent PRs | `/gh-stack` | One concern per PR, reviewed in order |
| Carry the open PR and its stack to merge | `/shepherd` | One watch covers every open layer; a PR is done when a human merges it |
| Prove it works | `/test` | Tests are proof |
| Set the quality bar | `/constraints` | Decide it once, enforce it everywhere |
| Review before merge | `/review` | Improve code health |
| Audit web performance | `/webperf` | Measure before you optimize |
| Simplify the code | `/code-simplify` | Clarity over cleverness |
| Ship to production | `/ship` | Faster is safer |
| Find where a session's time went | `/inference-tracing` | Measure from the transcripts, never by asking the session |
| Consolidate memories into rules | `/reflect` | A lesson lives once, globally |

Skills also activate on their own: a build task that touches a library is checked against current docs through `docs-researcher`, a chain of dependent branches triggers `gh-stack`, a freshly opened PR triggers `shepherd`.

## How It Fits Together

| Layer | Lives in | Decides |
| --- | --- | --- |
| Process | agent-skills plugin, overridden by `rules/agent-skills.md` | How work moves — spec, plan, build, test, review, ship — and which reviewer persona looks at it |
| Bar | `CLAUDE.md` | What "good" means |
| Delivery | `skills/deliver`, `agents/planner.md`, `agents/layer-builder.md` | The order of a run from spec to published PRs — one layer at a time, then a gate over the whole change |
| PR lifecycle | `skills/shepherd`, `skills/gh-stack`, `rules/gh-stack.md` | What happens after the PR exists |
| Knowledge | `source-driven-development` from the plugin, `agents/docs-researcher.md` | Where facts about libraries, frameworks, and tools come from |
| Telemetry | `skills/inference-tracing` | Where a session's wall clock went — inference, tools, waiting on the human — and what would shorten it |
| Memory | `.claude/skills/reflect` | Which project lessons become global rules |
| Config | `settings.json`, `statusline/`, agent frontmatter | The session's model and effort, each agent's own, permissions, plugin registration, what the status line shows |

## Project Structure

```text
~/.claude/
├── CLAUDE.md                          # The bar — user-level instructions, loaded into every session
├── settings.json                      # Model, effort, permissions, plugin registration, status line
├── rules/
│   ├── agent-skills.md                # agent-skills overrides — artifacts under .claude/specs/<name>/, moved into the worktree when the first layer opens, plans cut into PR layers, model and effort per role, docs lookups via docs-researcher
│   └── gh-stack.md                    # Stack PR titles and bodies are decided before shipping
├── agents/
│   ├── docs-researcher.md             # One documentation question per call, Context7-backed, quoted and cited
│   ├── layer-builder.md               # One PR layer per call: built test-first, simplified, reported
│   └── planner.md                     # One spec per call: plan and task list, cut into PR layers
├── skills/
│   ├── deliver/
│   │   └── SKILL.md                   # Spec to published PRs: per-layer build, simplify, review, then a gate
│   ├── shepherd/
│   │   ├── SKILL.md                   # Watch an open PR and every open layer of its stack until a human merges or closes them
│   │   └── scripts/
│   │       ├── watch-pr.sh            # The one PR reader, over every open layer: baseline, then watch
│   │       ├── query.graphql          # The fragment read on each layer: every PR surface and its stack's entries
│   │       └── jq/                    # pass, layers, and shared lib filters
│   ├── gh-stack/
│   │   └── SKILL.md                   # Stacked PRs, vendored from github/gh-stack
│   └── inference-tracing/
│       ├── SKILL.md                   # Trace another session's transcripts into a timing report, published as an Artifact
│       └── report-template.md         # The report's sections and what each must find, show, and write
├── statusline/
│   └── ccstatusline-config.json       # Three-line ccstatusline layout
├── docs/
│   └── skill-anatomy.md               # Ruling for writing and auditing skills
└── .claude/
    └── skills/
        └── reflect/                   # Repo-local: visible only in this checkout
            ├── SKILL.md               # Triage memories, promote rules via PR, prune after merge
            └── scripts/
                ├── inventory.sh       # Every project memory as one JSON stream
                └── prune.sh           # Delete manifest files and their MEMORY.md lines
```

## License

Apache License 2.0. See [LICENSE](LICENSE).
