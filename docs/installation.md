# Installation and update

Install only a clean, reviewed source revision after acceptance. The installer is
Python 3.11+ behind `scripts/install.sh`; it is not a management CLI. Native clients,
Git, GitHub CLI with `gh skill`, npm, Bash, and jq must be available. See the tested
versions in [compatibility](compatibility.md). Authenticate native clients through
their own credential stores; never put credentials in tracked settings.

```bash
./scripts/install.sh --codex --dry-run
./scripts/install.sh --claude --dry-run
./scripts/install.sh --codex --claude --dry-run
./scripts/install.sh --codex --claude
```

No target is an error. Dry run reads and validates the source, prerequisites and
destinations, prints links/native commands, and creates no checkout, backups or
client state. It never invokes a third-party installation command.

Review existing configuration before first adoption. Byte-identical files and
explicitly reviewed baseline hashes in `adapters/adoption.json` may be backed up
and replaced. Unknown differences produce a diff and stop. Preserve desired
preferences by changing the authoritative source through a PR, regenerate, then
retry. Unknown directories and unexpected links are never silently adopted.

The stable checkout is `${XDG_DATA_HOME:-$HOME/.local/share}/harness/checkout`, on
`install/local`. It shares the source repository. Never develop in it or delete it
while links are active. A dirty checkout prints its status/diff and refuses updates;
no reset or automatic commit discards native writes. The installation state and
private backups live beside this checkout, outside client runtime homes.

| Destination | Tracked target |
| --- | --- |
| `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json` | `adapters/claude/settings.json` |
| `${CODEX_HOME:-$HOME/.codex}/config.toml` | `adapters/codex/config.toml` |
| Claude `CLAUDE.md` / Codex `AGENTS.md` | `generated/<client>/` instructions |
| Claude individual `rules/*.md` | `rules/` except engineering already in global instructions |
| Client `agents/` individual definitions | `generated/<client>/agents/` |
| Claude individual `skills/` | `generated/claude/skills/` except reflect |
| `$HOME/.agents/skills/` individual Codex skills | `generated/codex/skills/` except reflect |
| `${XDG_CONFIG_HOME:-$HOME/.config}/ccstatusline/settings.json` | `statusline/ccstatusline-config.json` |
| Repository `.agents/skills/reflect`, `.claude/skills/reflect` | Relative links to in-worktree generated packages |

Codex's user skill discovery is `$HOME/.agents/skills`, independently of
`CODEX_HOME`. The installer respects both client home overrides for configuration
and agents. It preserves unrelated siblings, auth, memories and sessions.
Destination ancestors must be real directories; stop and choose a supported
physical path if a runtime home is itself a symlink.

The installer creates links, runs pinned native installers, and verifies native
registrations and payloads. Package payloads remain upstream-owned. The Claude
catalog must be published at the reviewed URL before installation. This PR's
catalog is available there only after merge; repository rename requires updating
that URL in source. See [native dependencies](native-dependencies.md).

A native operation that replaces a link with identical bytes gets a backup and
is relinked. A write-through modification dirties the stable checkout; unexpected
replacement content is retained and reported as a conflict. Resolve changes in a
fresh development worktree and PR, then recover and retry. There is no automatic
bidirectional synchronization.

To update, fetch/pull the accepted revision in the source checkout and rerun the
same installer. When both clients have been installed, changing revision requires
both targets because they share one installation checkout. Existing correct links
are no-ops; obsolete owned links are removed only if unchanged. Restart clients
and verify fresh discovery. Preserve backups until acceptance.

Before post-acceptance rollout: rename the repository as a separate human-reviewed
administrative action; verify remote identity and protections, update catalog URL
and remotes, resolve active worktrees before moving the development checkout,
then deploy. Never move the stable worktree during ordinary feature cleanup.
