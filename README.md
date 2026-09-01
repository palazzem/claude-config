# claude-config

Personal [Claude Code](https://docs.anthropic.com/en/docs/claude-code) configuration, versioned as the `~/.claude` directory itself. Process comes from the [agent-skills](https://github.com/addyosmani/agent-skills) plugin; this repo adds the quality bar, the GitHub pull-request lifecycle the plugin stops short of, a documentation-research agent, and settings.

## Layout

```
~/.claude/
├── CLAUDE.md                   # The bar — wins over plugin defaults where they conflict
├── settings.json               # Model, effort, permissions, plugin marketplace, status line
├── rules/context7.md           # Library and API questions go to docs-researcher, never memory
├── agents/docs-researcher.md   # Context7-backed documentation lookups, source-cited
├── skills/
│   ├── shepherd/               # Watches an open PR until a human merges or closes it
│   └── gh-stack/               # Stacked PRs (vendored from github/gh-stack)
├── docs/skill-anatomy.md       # Ruling for writing and auditing skills
└── statusline/                 # ccstatusline layout
```

An ignore-all `.gitignore` whitelists only these paths, so Claude Code's runtime files (history, caches, telemetry) never enter version control.

## How it fits together

**agent-skills supplies process.** Its lifecycle skills — `/spec`, `/plan`, `/build`, `/test`, `/review`, `/ship` and the rest — and its reviewer personas run the work from idea to pull request. `settings.json` registers the marketplace and enables the plugin.

**`CLAUDE.md` supplies the bar.** Where the two conflict, `CLAUDE.md` wins: options ranked by outcome quality only, a green-field proposal on every decision, no lint suppressions, warnings treated as findings, docstrings on every public symbol, conceptual architecture docs, and merges reserved for humans.

**This repo's skills pick up after the PR exists.** `shepherd` arms a single monitor on the open PR and wakes the session on reviewer comments, failed checks, and drift or conflicts; the session fixes, pushes, replies, and re-arms until a human merges or closes, then reports and cleans up the branch and worktree. `gh-stack` drives the `gh stack` extension for chains of dependent PRs.

**`docs-researcher` answers from current documentation.** Any question about a library, framework, SDK, CLI, or cloud service is delegated to it — a Sonnet subagent querying the Context7 CLI — and answered from the returned report, never from memory. `rules/context7.md` makes that routing mandatory.

## Setup

```bash
git clone git@github.com:palazzem/claude-config.git ~/.claude
```

`~/.claude` usually already exists; on a machine with configuration to keep, clone elsewhere and copy the pieces you want.

Prerequisites:

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- [GitHub CLI](https://cli.github.com/) (`gh`), authenticated, plus `jq` — used by `shepherd`
- `gh extension install github/gh-stack` — used by `gh-stack`
- [ccstatusline](https://github.com/sirmalloc/ccstatusline) — copy `statusline/ccstatusline-config.json` to `~/.config/ccstatusline/settings.json`
- Context7 runs through `npx ctx7@latest`; nothing to install

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
