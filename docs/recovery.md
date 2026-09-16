# Recovery

Installation is a sequence of local and upstream operations, not an atomic
transaction across package managers. Local state lives under
`${XDG_DATA_HOME:-$HOME/.local/share}/harness/`:

- `installation.json`: accepted revision, checkout, selected targets, owned links
  and adoption backup locations.
- `pending.json`: interrupted/failed transaction, prior revision, intended changes
  and conflicts that prevented safe restoration.
- `backups/`: adopted original files and matching native replacements.
- Native registration backups: see [native dependencies](native-dependencies.md).

The kernel installation lock prevents concurrent runs and releases on process
exit. Do not delete a lock to bypass a running process. An interrupted journal
stops further installation until recovery is reviewed. Protect these private
files: they may contain local paths and previous preferences.

On ordinary failure the installer restores only unchanged links it created,
restores their adoption backups, and returns a clean checkout to the prior
revision. New native writes, unexpected links, dirty checkout content and shared
package payloads remain intact. Conflicts retain the journal. Never use
`git reset --hard`, force-remove a client directory, or restore a stale whole-home
snapshot.

To recover an interrupted transaction:

1. Ensure the owning installer process has exited. Read `pending.json` and the
   previous `installation.json`; save copies before changing anything.
2. First determine whether the receipt was already committed. If
   `installation.json` records the journal's new revision, and the checkout and
   every recorded link verify at that revision, the deployment succeeded and only
   journal cleanup remains. Preserve that revision and its links; archive the
   journal without replaying rollback. This also covers interruption immediately
   after receipt replacement, before the journal phase could be updated. If the
   receipt or links disagree, retain all evidence and reconcile before proceeding.
3. For a transaction whose new receipt was not committed, inspect every journal destination. If it is still exactly the intended owned
   link, remove just that link and restore its recorded backup if one exists.
   Leave any replaced file or changed link intact and reconcile it with source.
   For an obsolete-link removal, restore the prior link only when its destination
   is still absent. Do not alter unrelated directory entries.
4. Inspect `git -C <checkout> status --short` and `git -C <checkout> diff`.
   Preserve intended edits in a fresh feature worktree and PR. Do not reset dirty
   state. If clean, use `git -C <checkout> reset --keep <prior_revision>` from the
   journal and confirm the resulting revision matches the previous receipt.
5. Verify prior owned links resolve to their expected tracked files. Keep native
   package state and registration backups; consult the native installers to
   reconcile their versions. A local rollback does not downgrade dependencies.
6. Only after recovery is verified, archive `pending.json` outside the active state
   path. Rerun the same installer against a clean reviewed source revision.

A failed first installation may leave a clean `install/local` checkout without an
accepted receipt. It can be reused by the next run after recovery; do not create
another repository at the same path or delete worktrees blindly.

To remove the harness, stop active clients, inventory the receipt, and unlink only
entries whose link text still names the recorded stable checkout target. Restore
recorded original backups to absent destinations. Retain all shared dependencies
unless separately and explicitly uninstalled with their native tools. Preserve
credentials, sessions, memories and unrelated packages. Remove the stable Git
worktree only after no managed links refer to it and all edits are preserved.

Native UI writes require a source PR: copy only the intended, non-secret changes
into a fresh worktree, regenerate affected outputs, review/merge, then install.
For atomic replacement conflicts, preserve the runtime file and compare it to the
tracked target before restoring the link. Merely pulling the development checkout
does not deploy rules and never authorizes reflection pruning.
