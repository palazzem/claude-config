# Compatibility and validation evidence

Implementation verification date: 2026-09-16. These are tested versions, not
invented minimum requirements: Codex CLI 0.154.0, Claude Code 2.1.273, GitHub CLI
2.100.0, Node 24.20.0, Python 3.12.14 and 3.14.7. CI targets Python 3.11 and 3.12 on Linux
and macOS. CI results must be checked on the PR; configured coverage is not proof
of successful execution.

A read-only inventory found no configured MCP servers in either client, including
Claude project entries. No speculative integrations were added.

## Observed native behavior

Disposable homes were used throughout; no real client settings, authentication,
memories or sessions were copied or changed.

- The complete public `scripts/install.sh --codex` path passed against an isolated
  clone with disposable runtime roots, including native dependency verification and
  settings guards. Repeat testing exposed a GitHub CLI force/pin bug; matching
  extension pins now skip installation and mismatches are preserved for explicit
  native reconciliation. Two corrected native repeat runs preserved the pin.
  The initial generation guard caught stale outputs during final
  edits; regeneration and a clean committed rerun passed.
- GitHub's pinned extension and both user skill installs succeeded. Native source
  tracking matched the locked commit/tree; `gh stack --version` worked.
- Claude's pinned plugin catalog installed Addy 0.6.8 at the exact locked commit.
  Codex's pinned marketplace and plugin install succeeded. Complete native payload
  hashes matched the lock. Native clients package one upstream symlink differently;
  separate payload hashes record that observed difference.
- Context7 0.5.11 and ccstatusline 2.2.27 installed and reported expected versions.
- Repeated native plugin installation preserved symlinked settings and their bytes.
  Changing Claude marketplace source writes configuration through the symlink;
  the installer detects this as dirty tracked state instead of hiding the edit.
- Codex app-server `config/read` with strict configuration loaded symlinked settings
  including `on-request`, `workspace-write`, and live web search. `skills/list`
  discovered all nine lifecycle wrappers and shepherd through linked packages in
  an unrelated project. Reflect was absent there and present in the harness worktree.
- Claude fresh stream-JSON initialization loaded symlinked settings with the
  intended model and `auto` mode, discovered docs-researcher and shepherd, and
  discovered reflect only from the harness worktree. Settings remained links.
- Claude startup with `--agent docs-researcher` exposed Bash/WebFetch, but effective
  mode remained `auto` despite agent metadata requesting `plan`. Parent permission
  inheritance is real; do not claim metadata creates a hard read-only boundary.

## Explicitly unverified acceptance claims

Disposable clients have no authentication. Model requests failed authentication;
model consumption of standing rules, real delegated researcher behavior and spawned
permissions, and actual end-to-end lifecycle command execution are **unverified**.
Discovery/configuration evidence does not establish those behaviors. Run fresh
authenticated sessions after acceptance, confirm the loaded instruction contract,
invoke each workflow, and test researcher effective permissions before claiming
full native parity. Do not put live credentials in this repository to run CI.

The production Claude catalog URL is introduced by this PR and unavailable at
`main` before merge. The equivalent local native catalog was tested; published-URL
installation remains **unverified until merge**. Preflight requires the published
catalog to equal the selected tracked catalog before installation. A changed URL
or pin must be reviewed, published, and retested.

Shepherd can monitor Codex only while its task is active. Persisted state supports
explicit resume; no automatic wake-up after a task ends and no daemon is provided.
Claude Monitor must actually be available and armed before reporting durable
monitoring. Oversized GitHub responses fail closed with explicit incomplete-read
errors; they are not silently truncated or treated as complete baselines.

Reflection is explicit-only, repository-local, and limited to selected Claude
memory files. Pruning requires a merged PR, deployed revision/links, unchanged
hashes and recorded fresh-client discovery evidence for every selected target.
The helper validates evidence integrity; a transcript hash alone is not semantic
proof that a model loaded a rule. An explicit session must confirm that evidence.
Do not apply this deletion workflow to Codex-generated memories.

## Reproducible checks

`uv run python -W error -m unittest discover -v` uses temporary repositories and
homes, fake native failures, synthetic memory files and PR responses. It exercises
adoption, stable worktrees, repeat installation, conflicts, rollback, native
replacement/write-through behavior, journal interruption, regeneration, workflow
scoping, event limits/markers and reflection gates. No test merges a real PR or
deletes real memories.

`ruff check`, `ruff format --check`, `mypy`, `scripts/render.py --check`, native
JSON/TOML parsing and Bash syntax validation accompany those tests. Native package
and client startup smoke tests are separate evidence, not inferred from mocks.

Official contracts consulted: [Codex skills](https://learn.chatgpt.com/docs/build-skills),
[Codex agents](https://learn.chatgpt.com/docs/agent-configuration/subagents),
[Claude rules](https://code.claude.com/docs/en/memory),
[Claude settings](https://code.claude.com/docs/en/settings),
[Claude plugin sources](https://code.claude.com/docs/en/plugin-marketplaces#plugin-sources),
and [GitHub skill installation](https://cli.github.com/manual/gh_skill_install).
