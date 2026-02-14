# claude-config

Personal [Claude Code](https://docs.anthropic.com/en/docs/claude-code) configuration to centralize custom skills, global rules, and settings.

## What's Inside

```
~/.claude/
├── CLAUDE.md          # Global rules (review workflow, conventions)
├── settings.json      # Permissions, plugins, environment
└── skills/
    ├── ask-claude-review/       # Self-review with 6 parallel reviewer agents
    ├── pull-review-comments/    # Fetch and address GitHub PR review threads
    ├── push-pr/                 # Create or update GitHub PRs via subagent
    ├── writing-bug-report/      # Structured bug report authoring
    └── writing-prd/             # Product requirements document authoring
```

## Setup

Clone this repository into your Claude Code configuration directory:

```bash
git clone git@github.com:palazzem/claude-config.git ~/.claude
```

If you already have a `~/.claude` directory, clone elsewhere and copy the files you need:

```bash
git clone git@github.com:palazzem/claude-config.git /tmp/claude-config
cp -r /tmp/claude-config/skills/ ~/.claude/skills/
cp /tmp/claude-config/CLAUDE.md ~/.claude/CLAUDE.md
```

## How It Works

This repo uses an ignore-all `.gitignore` strategy: everything in `~/.claude` is ignored by default, and only configuration files are explicitly whitelisted. This keeps Claude Code's runtime files (caches, history, telemetry) out of version control.

### Skills

Skills are slash commands you can invoke in Claude Code sessions. Type `/<skill-name>` to run one:

| Skill | Description |
|-------|-------------|
| `/ask-claude-review` | Dispatches 6 parallel review agents to analyze code changes |
| `/pull-review-comments` | Fetches unresolved PR review threads and addresses each one |
| `/push-pr` | Creates or updates a GitHub PR with template filling and labels |
| `/writing-bug-report` | Guides structured bug report creation |
| `/writing-prd` | Guides product requirements document creation |

### Review Workflow

The global `CLAUDE.md` defines a review workflow that ties three skills together:

1. `/ask-claude-review` — self-review before pushing
2. `/push-pr` — create or update the PR
3. `/pull-review-comments` — fetch and address reviewer feedback

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI installed
- [GitHub CLI](https://cli.github.com/) (`gh`) installed and authenticated (for PR-related skills)

## License

This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
