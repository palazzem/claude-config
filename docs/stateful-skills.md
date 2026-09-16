# Stateful skills

Shepherd keeps the portable Bash/GraphQL/jq reader. Its `state.py` companion journals a complete read before exposing events: PR identity, watermark including head commit, pending/handling events, and handled evidence. A persisted ingestion sequence distinguishes later CI/drift transitions with identical event bodies. A failed new head wakes the watcher even when the prior head failed too. Keep the journal private under the client runtime home. Supply the long-lived client PID to every operation; a kernel lock serializes operations and the saved live-owner PID prevents concurrent sessions handling the same PR. A dead owner allows resume. PID reuse requires checking ownership manually before transfer. Do not remove a live owner's state.

On resume, inspect `show`, reconcile every `handling` event against the remote effect, and record `complete` with the effect URL/commit or no-action reason. Never replay a remote action blindly or take a fresh baseline. There is no atomic transaction spanning GitHub and local disk. A crash after remote posting and before completion is resolved by examining attribution and event references. Both `<!-- claude -->` and `<!-- codex -->` are filtered.

Claude monitoring uses the native Monitor capability only when available and tested. Codex monitoring runs during an active task and resumes explicitly from its saved journal. No daemon or automatic wake-up after completion is supplied. Report actual active, paused/resumable, or terminal state in every handoff. A truncated GraphQL connection fails closed rather than creating an incomplete baseline. Large PRs beyond any current connection limit require extending the shared reader with pagination before monitoring; this is a deliberate documented limitation.

Reflection is explicit-only and repository-local. It can run on either client but only operates selected Claude memories. The Claude runtime memory root is separate from the Git source and installation worktree. The helper rejects path and ancestor symlinks, including sibling indexes; run without concurrent memory writers. Do not point it at Codex generated memories.

Private manifests live outside the repository, in `${CLAUDE_CONFIG_DIR:-~/.claude}/reflect/`, with mode 0600 and a private parent directory. Explicitly select every deletion, including already redundant memories; promotion selection alone never authorizes deletion, and `none` ends without changes. Store explicit selected paths and hashes before promotion, then PR identity and deployment evidence after the separate authorized installation. Example schema (use real hashes and paths):

```json
{
  "explicit_selection": true,
  "repository": "owner/harness",
  "pr": 42,
  "entries": [{"path": "project/memory/lesson.md", "sha256": "SHA256"}],
  "targets": ["codex", "claude"],
  "deployment": {
    "codex": {
      "revision": "INSTALL_COMMIT",
      "discovery_command": "fresh client command used",
      "discovery_output": "/private/path/codex-discovery.txt",
      "discovery_output_sha256": "SHA256",
      "confirmed_loaded": "codex",
      "links": {"/native/AGENTS.md": "SHA256_OF_DEPLOYED_FILE"}
    }
  }
}
```

Include an analogous deployment object for every selected target. Capture a fresh-client transcript demonstrating the promoted guidance is loaded, not merely a successful process exit. This is explicit session evidence; the helper checks transcript integrity and deployment identity, and does not pretend a transcript hash proves semantic discovery. `prune.sh --dry-run <manifest>` checks selection, containment, indexes and content hashes. `prune.sh <manifest>` additionally queries GitHub to confirm the PR is merged, checks merge ancestry in the clean installation checkout, checks the installation receipt revision and all selected targets, and verifies tracked symlink destinations and rule hashes. Each target must prove its own global instruction file; Claude must additionally prove every deployed shared rule. Links owned by another target or unrelated source files cannot satisfy this gate. The active checkout must have no symlink ancestors, use branch `install/local`, and have the same GitHub origin as the promotion PR. The default receipt is `${XDG_DATA_HOME:-~/.local/share}/harness/installation.json`; tests may supply `--receipt`.

An absent manifest, changed memory, unmerged/closed PR, stale discovery evidence, replaced link, dirty checkout or uninstalled target blocks deletion. Syncing the development checkout alone does not count. Preserve manifests after failure and closed PRs. After a successful prune, remove the manifest; interrupted pruning can resume with the same manifest and skips already absent files. No real memory deletion or production deployment belongs in validation.

Before an explicit handoff, stop the active reader, then run the journal `release`
action with the verified current owner PID. Pending work and watermark remain; a
new session can claim ownership without waiting for the old client to exit. Use
the same process namespace for the PID and helper (sandbox PIDs may differ).
