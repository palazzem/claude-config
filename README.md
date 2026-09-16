# harness

Shared engineering conventions and native Codex/Claude configuration. Keep the
source checkout separate from client runtime homes. Existing workflow names and
upstream packages remain intact.

After the implementation PR is accepted, install a clean reviewed revision:

```bash
./scripts/install.sh --codex --claude --dry-run
./scripts/install.sh --codex --claude
```

Choose either target independently with `--codex` or `--claude`. The installer
links tracked configuration, instructions, agents and skills through a persistent
Git worktree at `~/.local/share/harness/checkout` (`install/local`). Native clients
own credentials, sessions, memories, caches and third-party package payloads.
Changes to managed configuration go through a source PR; rerun the installer to
advance the clean installation worktree after acceptance.

| Workflow | Claude | Codex |
| --- | --- | --- |
| Specification, planning, implementation | `/spec`, `/plan`, `/build` | `$spec`, `$plan`, `$build` |
| Verification and constraints | `/test`, `/constraints` | `$test`, `$constraints` |
| Review, performance, simplification | `/review`, `/webperf`, `/code-simplify` | `$review`, `$webperf`, `$code-simplify` |
| Publication and maintenance | `/ship`, `/shepherd`, `/gh-stack` | `$ship`, `$shepherd`, `$gh-stack` |
| Explicit memory promotion, only in this repo | `/reflect` | `$reflect` |

Addy's complete upstream plugin supplies lifecycle processes and review personas.
Codex wrappers reference its installed command resources. GitHub's native extension
and skill installers supply `gh-stack`; no upstream skill is vendored here.
`docs-researcher` uses a pinned Context7 CLI and reports cited findings or explicit
gaps. Human review and merge remain mandatory.

Read [installation](docs/installation.md), [recovery](docs/recovery.md),
[native dependencies](docs/native-dependencies.md),
[compatibility and evidence](docs/compatibility.md), and
[stateful skills](docs/stateful-skills.md) before deployment.

## Development

Work in a fresh feature worktree. Shared instructions live in `rules/` and
`repository/`; native metadata and settings live in `adapters/`. Commit shared
changes and regenerated native outputs together. Process artifacts stay ignored.

```bash
uv sync --locked
uv run python scripts/render.py
uv run ruff check .
uv run ruff format --check .
uv run mypy scripts tests skills
uv run python -W error -m unittest discover -v
uv run python scripts/render.py --check
```

The repository remains at `palazzem/claude-config` until the human-reviewed release
renames it to `harness`. Do not rename it, merge the PR, or install into real client
homes during implementation. After rename update remotes and the catalog URL in a
reviewed change before deployment.

Apache-2.0; see [LICENSE](LICENSE). Addy's agent-skills remains upstream under MIT;
GitHub's gh-stack remains upstream under its license. We install those packages
through their native tools and retain their original names and attribution.
