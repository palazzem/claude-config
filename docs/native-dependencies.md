# Native dependencies

`dependencies.lock.toml` records the reviewed package versions and provenance. The installer invokes native package managers; no upstream skills or plugin payloads are copied into this repository. The generated Claude marketplace is only a catalog entry pointing to the complete upstream package.

| Package | Reviewed pin | Verification |
| --- | --- | --- |
| Addy agent-skills | 0.6.8, `d2c37ef6225dd8726cdd369a8030307f48592d26` | Claude registry commit, Codex marketplace commit, enablement, and complete installed payload hashes |
| gh-stack extension | v0.1.0 | Native pinned manifest and executable version; GitHub release ref must resolve to the skill revision |
| gh-stack skill | `a1b4a3d4d0bcde9ec3a78ab99b2d63af121857a9` | Native source/ref/tree metadata plus installed skill content hash |
| Context7 CLI | ctx7 0.5.11 | Native npm installation and executable version |
| Claude statusline | ccstatusline 2.2.27 | Native npm installation and executable version |

Addy's pre-existing 0.6.8 checkout was inspected and retained deliberately. Its Claude upstream catalog leaves the plugin source unpinned, so our minimal native catalog adds the exact plugin `sha`. Codex uses the upstream local-root catalog at the pinned marketplace revision. Native package names remain `agent-skills@addy-agent-skills` for Claude and `agent-skills@agent-skills` for Codex. Verification rejects multiple enabled registrations of the same plugin name.

The Claude catalog's published URL is versioned in both the dependency lock and Claude settings. Before deployment, the installer verifies the published catalog equals the selected checkout's catalog. This lets settings stay directly authored and portable across arbitrary installation worktree paths. **The URL first becomes available when this PR merges.** Until then, actual native smoke tests use the identical catalog via a disposable local-directory registration. The production URL path is consequently unverified before merge. Repository renaming must update and validate this URL in both tracked locations during the release step. A future dependency upgrade publishes its reviewed catalog before installing the upgraded revision; old revisions with a different catalog intentionally refuse deployment against changed catalog content.

The extension installs once and skills install only for selected clients:

```sh
gh extension install github/gh-stack --pin v0.1.0 --force
gh skill install github/gh-stack gh-stack --agent codex --scope user \
  --pin a1b4a3d4d0bcde9ec3a78ab99b2d63af121857a9 --force
gh skill install github/gh-stack gh-stack --agent claude-code --scope user \
  --pin a1b4a3d4d0bcde9ec3a78ab99b2d63af121857a9 --force
```

`--force` is preceded by provenance checks: an existing extension must belong to `github/gh-stack`; an existing skill must have GitHub's source metadata or match the exact legacy vendored skill digest. Unknown entries and symlink traversal are refused. Codex's GitHub CLI skill destination is `$HOME/.agents/skills`; `CODEX_HOME` does not change that upstream convention. Claude skill installation honors `CLAUDE_CONFIG_DIR`.

The installer invokes `npm install --global` for the selected pinned CLI packages. Use the native Node installation's configured user-writable prefix and ensure its `bin` directory is on `PATH`. It does not change npm prefix configuration, install unrelated packages, or add another harness executable. The researcher uses the pinned `ctx7` package version; credentials continue to use native environment/authentication facilities.

## Evidence from disposable environments

On 16 September 2026, GitHub CLI 2.100.0 installed and executed gh-stack v0.1.0, and installed the pinned skill for both agents. Both installed skill files had SHA-256 `fd6298acc66248817bd8aa612d0e6d82297250d024f3bfeed4ecf08ef26c65b6`.

Claude Code 2.1.273 installed the pinned local catalog and recorded the exact Addy commit. Codex 0.154.0 installed its pinned marketplace and complete plugin. Both package trees matched the hashes in the lock. The complete installer verification function also passed against the disposable Codex installation. Claude preserved the upstream `.opencode/skills` symlink; Codex omitted that irrelevant host symlink, so each client has a separate complete-payload hash. The tests verified the full payload, including helper files, instead of trusting only the installer exit status.

With settings symlinked to separate disposable tracked files, repeating both clients' plugin installations preserved the links and bytes. Changing Claude's marketplace source under the same marketplace name updated its native registry and wrote the changed declaration through the settings link; this demonstrates why the installer checks managed files after every native call. Unit fixtures cover conflict handling, including failed native calls, and preservation of unexpected configuration writes.

A disposable npm prefix installed ctx7 0.5.11 and ccstatusline 2.2.27; both executable version checks passed. No real client environments were installed into. The Codex CLI emitted a warning that it refuses helper PATH aliases beneath `/tmp`; that is an explicit sandbox-smoke limitation, not a passing helper-discovery claim. npm printed an informational upgrade notice; upgrading npm was outside scope. GitHub's skill installer printed its standard unverified-third-party-content warning; the selected package provenance and bytes were independently checked.

## Recovery and upgrades

Before native calls, private snapshots of settings, plugin registrations, existing gh-stack skills and the extension manifest are saved under `$XDG_DATA_HOME/harness/backups/native/registration-*` (default `~/.local/share/harness/backups/native/`). These are evidence and recovery inputs, not replacement live settings. Compare old/new registrations, retain unrelated entries, and use native clients to reinstall the recorded package revisions. Do not replace an entire live registry from a snapshot after unrelated packages have changed. Authentication files and sessions are never part of these snapshots.

Each native operation is followed by the installer’s settings/link guard, including when the native command fails. An unexpected write stops subsequent native operations. Native dependency state is not rolled back automatically: a successful extension installation remains present if a later plugin operation fails. Preserve that state and resolve the reported conflict through the source repository before rerunning.

Upgrade the lock, catalog, and native settings together in a PR, rerun disposable native installations, and review changed payload hashes. A changed GitHub release-to-commit pairing, an unsupported native registry format, or an unexpected installed payload fails verification. Client authentication and interactive model behavior require the separate fresh-session checks documented in the compatibility runbook.

References: [Claude plugin source pinning](https://code.claude.com/docs/en/plugin-marketplaces#plugin-sources), [Addy native setup](https://github.com/addyosmani/agent-skills#quick-start), [gh-stack native setup](https://github.com/github/gh-stack#installation), [GitHub skill installation](https://cli.github.com/manual/gh_skill_install).
