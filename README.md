# claude-config

A versioned `~/.claude` that turns Claude Code into a disciplined engineer. Its skills and agents ship as the `harness` plugin, from the `palazzem` marketplace in this repository.

```text
  DEFINE     /spec                    ── agent-skills
    │
  DELIVER    /harness:deliver         ── harness
    │
  PLAN       /plan                    ┐
    │                                 │
  BUILD      /build                   │
    │                                 │
  SIMPLIFY   /code-simplify           ├─ agent-skills
    │                                 │
  REVIEW     /review                  │
    │                                 │
  GATE       /ship                    ┘
    │
  STACK      /gh-stack:gh-stack       ── gh-stack
    │
  WATCH      /harness:shepherd        ── harness
```

## Requirements

- Claude Code 2.1.324 or later
- System packages: `gh`, `jq`, `npm`

## Quick Start

To install globally, on a machine where Claude Code has no `~/.claude` yet:

```bash
git clone git@github.com:palazzem/claude-config.git ~/.claude
claude                                  # the first start registers the palazzem marketplace; /exit
claude plugin install harness@palazzem

gh auth login
gh extension install github/gh-stack --pin v0.3.0

npm install -g ccstatusline
mkdir -p ~/.config/ccstatusline
cp ~/.claude/statusline/ccstatusline-config.json ~/.config/ccstatusline/settings.json

claude
```

`claude plugin install harness@palazzem` also installs `agent-skills` and `gh-stack`, its dependencies. The `palazzem` marketplace is this repository's default branch on GitHub, the same source every project that installs the harness uses, so every session runs the published harness. After a change to `harness` is merged, `claude plugin update harness@palazzem` installs it, and the next session loads it.

## Plugins

| Plugin | Source | Pinned to |
| --- | --- | --- |
| `harness` | `harness/` in this repository | The default branch |
| `agent-skills` | [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | 0.6.16, `39b723c` |
| `gh-stack` | [github/gh-stack](https://github.com/github/gh-stack) | v0.3.0, `2a49e67` |

A third-party pin moves only by editing its `sha` in `.claude-plugin/marketplace.json`; once that change is pulled, `claude plugin update agent-skills@palazzem` or `claude plugin update gh-stack@palazzem` installs it.

## Install in a project

To enable the plugins and keep each user's global rules out for everyone who works in a repository, commit this to its `.claude/settings.json`:

```json
{
  "claudeMdExcludes": [
    "/home/*/.claude/rules/**",
    "/Users/*/.claude/rules/**"
  ],
  "extraKnownMarketplaces": {
    "palazzem": {
      "source": { "source": "github", "repo": "palazzem/claude-config" }
    }
  },
  "enabledPlugins": {
    "harness@palazzem": true,
    "agent-skills@palazzem": true,
    "gh-stack@palazzem": true
  }
}
```

In a clone of that repository, start `claude` once and trust the folder, then run:

```bash
claude plugin install harness@palazzem --scope project
```

The marketplace declaration is identical to the one in this repository's `settings.json`, so a project never re-points it. After a change to the harness is merged, run `claude plugin update harness@palazzem --scope project`, and the same for `agent-skills@palazzem` and `gh-stack@palazzem` when their pins moved.

`claudeMdExcludes` matches absolute paths, so the two globs drop `~/.claude/rules/` on Linux and macOS for every user, while the project's own `.claude/rules/` still loads. The project carries the rules it follows in its own `.claude/rules/`. Check what loads with `/memory`.

## Develop the harness

Sessions load the published harness. To try a change before it is merged, start a session with the checkout's copy:

```bash
claude --plugin-dir ~/.claude/harness
```

For that session it replaces the installed `harness`, in any project. Run `/reload-plugins` after each edit.

## Commands

| What you're doing | Command | Key principle |
| --- | --- | --- |
| Define what to build | `/spec` | Spec before code |
| Run everything after `/spec` in one pass | `/harness:deliver` | Build, simplify, and review once per PR, then gate the whole change |
| Plan how to build it | `/plan` | One PR per concern, atomic tasks |
| Build incrementally | `/build` | One slice at a time |
| Split a change into dependent PRs | `/gh-stack:gh-stack` | One concern per PR, reviewed in order |
| Carry the open PR and its stack to merge | `/harness:shepherd` | One watch covers every open layer; a PR is done when a human merges it |
| Prove it works | `/test` | Tests are proof |
| Set the quality bar | `/constraints` | Decide it once, enforce it everywhere |
| Review before merge | `/review` | Improve code health |
| Audit web performance | `/webperf` | Measure before you optimize |
| Simplify the code | `/code-simplify` | Clarity over cleverness |
| Ship to production | `/ship` | Faster is safer |
| Find where a session's time went | `/harness:inference-tracing` | Measure from the transcripts, never by asking the session |
| Consolidate memories into rules | `/harness:reflect` | A lesson lives once, where it applies |

Skills also activate on their own: a build task that touches a library is checked against current docs through `harness:docs-researcher`, a chain of dependent branches triggers `gh-stack:gh-stack`, a freshly opened PR triggers `harness:shepherd`.

## Project Structure

```text
~/.claude/
├── .claude-plugin/
│   └── marketplace.json               # The palazzem marketplace: harness, plus agent-skills and gh-stack pinned by commit
├── harness/
│   ├── .claude-plugin/
│   │   └── plugin.json                # The harness plugin; depends on agent-skills and gh-stack
│   ├── agents/
│   │   ├── docs-researcher.md         # One documentation question per call, Context7-backed, quoted and cited
│   │   ├── layer-builder.md           # One PR layer per call: built test-first, simplified, reported
│   │   └── planner.md                 # One spec per call: plan and task list, cut into PR layers
│   └── skills/
│       ├── deliver/                   # Spec to published PRs: per-layer build, simplify, review, then a gate
│       ├── shepherd/                  # Watch an open PR and every open layer of its stack until a human merges or closes them
│       ├── inference-tracing/         # Trace another session's transcripts into a timing report, published as an Artifact
│       └── reflect/                   # Triage memories, promote lessons into rules, prune after merge
├── settings.json                      # Model, effort, permissions, plugin registration, status line
├── statusline/
│   └── ccstatusline-config.json       # Three-line ccstatusline layout
└── docs/
    └── skill-anatomy.md               # Ruling for writing and auditing skills, adapted from agent-skills 0.6.16
```

## License

Apache License 2.0. See [LICENSE](LICENSE).
