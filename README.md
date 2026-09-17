# harness

Versioned configuration that turns Claude Code and Codex into disciplined engineers.
`CLAUDE.md` supplies the bar; skills and plugins supply the process. `AGENTS.md` is
an alias of the same authored conventions.

## Requirements

- Linux with Python 3.14 available as `python3`
- Claude Code, Codex, or both, according to the installation targets
- Git, Bash, `gh` with `gh skill`, `jq`, and `npm`
- GitHub authentication (`gh auth login`) and a writable npm global installation prefix

## Quick Start

Keep the source checkout separate from `~/.claude` and `~/.codex`. After the PR is
accepted, install from a clean checkout:

```bash
git clone git@github.com:palazzem/claude-config.git ~/workspaces/harness
cd ~/workspaces/harness
./scripts/install.sh --codex --claude --dry-run
./scripts/install.sh --codex --claude
```

Use `--codex` or `--claude` alone to select one client. `--dry-run` prints the
proposed links, backups, and native installer commands without changing client
state. `scripts/install.sh` is a thin launcher for `scripts/install.py`; there is
no separate management CLI.

The installer creates a persistent Git worktree at
`${XDG_DATA_HOME:-$HOME/.local/share}/harness/checkout`, on `install/local`.
Settings, instructions, agents, and skills link into that checkout. Claude uses
`${CLAUDE_CONFIG_DIR:-$HOME/.claude}`; Codex configuration uses
`${CODEX_HOME:-$HOME/.codex}` and its user skills use `$HOME/.agents/skills`.
Claude's statusline configuration uses `${XDG_CONFIG_HOME:-$HOME/.config}/ccstatusline`.
Credentials, sessions, memories, and unrelated packages stay in their native locations.

Existing identical files are backed up before replacement with links. Different
configuration, unknown directories, and unexpected links stop installation:
reconcile wanted changes in source before adopting them. Native settings changes
are retained and reported, including edits to ignored generated files.

[dependencies.lock.toml](dependencies.lock.toml) is the single source of native
dependency versions and revisions. Addy's complete `agent-skills` 0.6.9 plugin is
installed directly from its upstream marketplace. GitHub's extension and skill
installers provide `gh-stack`; its skill is not vendored here. Context7 and
ccstatusline are installed through npm. Claude's upstream installer chooses the
plugin payload; verification refuses a version or revision different from the lock.

## Commands

Development lifecycle commands come from agent-skills. Codex uses `$` skill names;
its native `/plan` and `/review` commands remain separate.

| What you're doing | Claude | Codex | Key principle |
| --- | --- | --- | --- |
| Define what to build | `/spec` | `$spec` | Spec before code |
| Plan how to build it | `/plan` | `$plan` | Small, atomic tasks |
| Build incrementally | `/build` | `$build` | One slice at a time |
| Split a change into dependent PRs | `/gh-stack` | `$gh-stack` | One concern per PR, reviewed in order |
| Carry the open PR to merge | `/shepherd` | `$shepherd` | The PR is done when a human merges it |
| Prove it works | `/test` | `$test` | Tests are proof |
| Set the quality bar | `/constraints` | `$constraints` | Decide it once, enforce it everywhere |
| Review before merge | `/review` | `$review` | Improve code health |
| Audit web performance | `/webperf` | `$webperf` | Measure before you optimize |
| Simplify the code | `/code-simplify` | `$code-simplify` | Clarity over cleverness |
| Ship to production | `/ship` | `$ship` | Faster is safer |
| Consolidate memories into rules | `/reflect` | `$reflect` | A lesson lives once, globally |

A library question routes to `docs-researcher`, a chain of dependent branches
triggers `gh-stack`, and a freshly opened PR triggers `shepherd`. Reflect is
explicit-only and available only in this repository. Codex shepherd monitoring
runs while its task is active; it does not automatically wake after the task ends.

## How It Fits Together

| Layer | Lives in | Decides |
| --- | --- | --- |
| Process | agent-skills plugin, overridden by `rules/agent-skills.md` | How work moves and which reviewer persona looks at it |
| Bar | `CLAUDE.md`, aliased by `AGENTS.md` | What "good" means |
| PR lifecycle | `skills/shepherd/`, upstream gh-stack, `rules/gh-stack.md` | What happens after the PR exists |
| Knowledge | `agents/docs-researcher.md`, `rules/context7.md` | Where facts about libraries, frameworks, and tools come from |
| Memory | `skills/reflect/` | Which project lessons become global rules |
| Native configuration | `adapters/`, `statusline/` | Client metadata, settings, and status line |

[Skill Anatomy](docs/skill-anatomy.md) describes how to write and audit skills.
Native conversions preserve their authored workflows. Run `python3 scripts/render.py`
after editing rules, skills, agents, or native metadata to refresh this checkout's
local packages. Outputs live in ignored `generated/`; they are never committed.
The installer renders them in the stable checkout during installation. Repository
reflection links resolve to each worktree's own generated packages.

## Update and Recovery

Pull the accepted revision into the source checkout and rerun the installer.
Updating a checkout used by both clients requires both target flags. Restart the
clients after installation. Do not edit or delete the stable worktree while its
links are active; preserve any local changes and bring them into the source first.

Installation records and backups live beside the stable checkout:
`installation.json` records the deployed revision and owned links; `pending.json`
records interrupted work; `backups/` preserves adopted files and native registrations.
On failure, safe local changes are rolled back; native package installations are
retained. Unknown writes and dirty files are never discarded automatically.

If a pending journal remains, stop the owning installer and inspect it with the
receipt and checkout. A receipt matching the journal's new revision can mean only
journal cleanup failed: verify that revision and its links, then archive the
journal without rolling back. Otherwise restore only unchanged journal-owned
links and recorded backups, and return to the prior revision only after preserving
local edits; regenerate its native outputs. Archive the journal only after the
receipt, checkout, and links agree. Never reset dirty state or restore an entire
client home from a snapshot. To uninstall, unlink only recorded unchanged harness
links and restore their backups; retain unrelated state and shared dependencies.

## License

Apache License 2.0. See [LICENSE](LICENSE). Upstream packages retain their own licenses.
