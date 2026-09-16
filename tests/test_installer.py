"""Exercise real Git worktrees and isolated native destinations, including failure recovery."""

import contextlib
import io
import json
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scripts.installer.core import deploy, git, ownership
from scripts.installer.files import Conflict


class InstallerTests(unittest.TestCase):
    """Each fixture owns a disposable repository and client home with spaces."""

    def setUp(self) -> None:
        """Create a minimal committed source with each selected native target."""
        self.temporary = tempfile.TemporaryDirectory(prefix="harness fixture ")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "source"
        self.root.mkdir()
        self.env = {"HOME": str(self.base / "home")}
        sources = {
            "CLAUDE.md": "shared rules",
            "agents/docs-researcher.md": "research",
            "adapters/claude/docs-researcher.json": '{"name":"docs-researcher"}',
            "adapters/codex/docs-researcher.toml": 'name = "docs-researcher"\n',
            "adapters/claude/settings.json": "{}",
            "adapters/codex/config.toml": 'model = "fixture"\n',
            "dependencies.lock.toml": '[agent_skills]\nrevision = "fixture"\n[context7]\nversion = "0.5.11"\n',
            "skills/shepherd/SKILL.md": "shepherd",
            "skills/reflect/SKILL.md": "local",
            "statusline/ccstatusline-config.json": "{}",
            "rules/context7.md": "research",
            ".gitignore": "generated/\n.agents/skills/reflect\n.claude/skills/reflect\n",
            "scripts/render.py": (
                Path(__file__).resolve().parents[1] / "scripts/render.py"
            ).read_text(),
        }
        for relative, content in sources.items():
            self.write(relative, content)
        git(self.root, "init", "-b", "main")
        git(self.root, "config", "user.email", "fixture@example.invalid")
        git(self.root, "config", "user.name", "Fixture")
        self.commit()
        self.checkout = self.base / "home/.local/share/harness/checkout"
        self.data = self.checkout.parent
        self.settings = self.base / "home/.claude/settings.json"

    def write(self, relative: str, text: str) -> None:
        """Write source fixture files without touching any actual runtime environment."""
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit(self) -> None:
        """Commit fixture revisions so rollout exercises real provenance."""
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "fixture")

    def install(
        self,
        targets: set[str] | None = None,
        *,
        dry_run: bool = False,
        native: Callable[[Path, set[str]], None] | None = None,
    ) -> dict[str, Any]:
        """Capture the installer proposal while exercising its complete filesystem path."""
        with contextlib.redirect_stdout(io.StringIO()):
            return deploy(
                self.root,
                targets if targets is not None else {"claude", "codex"},
                self.env,
                dry_run=dry_run,
                native=native,
            )

    def test_target_selection_and_repeat(self) -> None:
        """Both clients receive tracked settings and only their intended skills."""
        self.install({"codex"})
        self.assertFalse(self.settings.exists())
        self.install({"claude"})
        before = self.settings.lstat().st_mtime_ns
        self.install()
        self.assertEqual(self.settings.lstat().st_mtime_ns, before)
        self.assertEqual(self.settings.resolve(), self.checkout / "adapters/claude/settings.json")
        self.assertFalse((self.base / "home/.agents/skills/reflect").exists())
        self.assertTrue((self.base / "home/.agents/skills/shepherd/SKILL.md").exists())

    def test_dry_run_and_no_target(self) -> None:
        """Dry run leaves even state directories absent; no-target invocation refuses."""
        self.install(dry_run=True)
        self.assertFalse((self.base / "home").exists())
        self.assertFalse((self.root / "generated").exists())
        with self.assertRaises(Conflict):
            self.install(set())

    def test_adoption_backup_and_unrelated_state(self) -> None:
        """Known matching files are backed up and credentials remain untouched."""
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text("{}")
        auth = self.settings.parent / "credentials.json"
        auth.write_text("private fixture")
        proposal = self.install(dry_run=True)
        self.assertIn(str(self.settings), proposal["backup_required"])
        receipt = self.install()
        backup = Path(receipt["links"][str(self.settings)]["backup"])
        self.assertEqual(backup.read_text(), "{}")
        self.assertEqual(auth.read_text(), "private fixture")

    def test_unknown_collision_and_parent_symlink(self) -> None:
        """Unknown configuration and unsafe ancestors stop before creating stable state."""
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text('{"wanted":true}')
        with self.assertRaisesRegex(Conflict, "Unreviewed"):
            self.install()
        self.settings.unlink()
        self.settings.parent.rmdir()
        self.settings.parent.symlink_to(self.root)
        with self.assertRaisesRegex(Conflict, "Unsafe"):
            self.install()
        self.assertFalse(self.data.exists())

    def test_replaced_and_broken_links(self) -> None:
        """Unexpected link replacement is retained for explicit source reconciliation."""
        self.install()
        self.settings.unlink()
        self.settings.write_text("{}")
        with self.assertRaisesRegex(Conflict, "replaced"):
            self.install()
        self.settings.unlink()
        self.settings.symlink_to(self.base / "missing")
        with self.assertRaisesRegex(Conflict, "Unexpected"):
            self.install()

    def test_dirty_worktree_and_feature_isolation(self) -> None:
        """Source edits do not affect deployment; native writes make the worktree dirty."""
        self.install()
        self.write("adapters/claude/settings.json", '{"feature":true}')
        self.assertEqual(self.settings.read_text(), "{}")
        self.commit()
        self.settings.write_text('{"native":true}')
        with self.assertRaisesRegex(Conflict, "Dirty worktree"):
            self.install()
        self.assertIn("native", self.settings.read_text())

    def test_update_and_obsolete_link(self) -> None:
        """Updating advances stable provenance and removes only an unchanged obsolete link."""
        self.install()
        self.write("adapters/claude/settings.json", '{"new":true}')
        (self.root / "rules/context7.md").unlink()
        self.commit()
        self.install()
        self.assertIn("new", self.settings.read_text())
        self.assertFalse((self.settings.parent / "rules/context7.md").is_symlink())
        self.assertEqual(
            git(self.checkout, "rev-parse", "HEAD"), git(self.root, "rev-parse", "HEAD")
        )

    def test_native_failure_restores_previous_revision(self) -> None:
        """Native failure restores safe prior revision without deleting unrelated state."""
        self.install()
        prior = git(self.checkout, "rev-parse", "HEAD")
        self.write("adapters/claude/settings.json", '{"new":true}')
        self.commit()

        def fail(root: Path, targets: set[str]) -> None:
            raise RuntimeError("fixture native failure")

        with self.assertRaisesRegex(RuntimeError, "native failure"):
            self.install(native=fail)
        self.assertEqual(git(self.checkout, "rev-parse", "HEAD"), prior)
        self.assertEqual(self.settings.read_text(), "{}")

    def test_atomic_matching_replacement_relinked(self) -> None:
        """Native identical atomic replacement is backed up and restored to a link."""

        def replace(root: Path, targets: set[str]) -> None:
            content = self.settings.read_bytes()
            self.settings.unlink()
            self.settings.write_bytes(content)

        self.install(native=replace)
        self.assertTrue(self.settings.is_symlink())
        self.assertTrue(list((self.data / "backups").glob("*/native-*")))

    def test_atomic_unexpected_replacement_retained(self) -> None:
        """Unexpected native writes survive rollback and retain a recovery journal."""

        def replace(root: Path, targets: set[str]) -> None:
            self.settings.unlink()
            self.settings.write_text('{"new native":true}')

        with self.assertRaisesRegex(Conflict, "replaced managed"):
            self.install(native=replace)
        self.assertIn("new native", self.settings.read_text())
        self.assertTrue((self.data / "pending.json").exists())
        with self.assertRaisesRegex(Conflict, "Interrupted"):
            self.install()

    def test_write_through_preserved(self) -> None:
        """Dirty native target content is never reset on failure."""

        def write(root: Path, targets: set[str]) -> None:
            self.settings.write_text('{"native edit":true}')

        self.install()
        with self.assertRaisesRegex(Conflict, "Dirty"):
            self.install(native=write)
        self.assertIn("native edit", self.settings.read_text())
        self.assertTrue((self.data / "pending.json").exists())

    def test_concurrent_install(self) -> None:
        """A second process cannot enter while the installation lock is held."""
        self.data.mkdir(parents=True)
        with ownership(self.data):
            with self.assertRaisesRegex(Conflict, "Another installation"):
                self.install()

    def test_interrupted_journal_refusal(self) -> None:
        """A persisted incomplete transaction requires explicit recovery first."""
        self.data.mkdir(parents=True)
        (self.data / "pending.json").write_text(json.dumps({"phase": "link"}))
        with self.assertRaisesRegex(Conflict, "Interrupted"):
            self.install()

    def test_custom_homes(self) -> None:
        """Client and XDG overrides retain native skill discovery at HOME/.agents."""
        self.env.update(
            {
                "CODEX_HOME": str(self.base / "codex custom"),
                "CLAUDE_CONFIG_DIR": str(self.base / "claude custom"),
                "XDG_DATA_HOME": str(self.base / "data custom"),
                "XDG_CONFIG_HOME": str(self.base / "config custom"),
            }
        )
        self.install()
        self.assertTrue((self.base / "codex custom/config.toml").is_symlink())
        self.assertTrue((self.base / "claude custom/settings.json").is_symlink())
        self.assertTrue((self.base / "config custom/ccstatusline/settings.json").is_symlink())

    def test_partial_target_update_refused(self) -> None:
        """A shared revision cannot silently change the unselected client's links."""
        self.install()
        previous = git(self.checkout, "rev-parse", "HEAD")
        self.write("adapters/claude/settings.json", '{"changed":true}')
        self.commit()
        with self.assertRaisesRegex(Conflict, "all previously installed"):
            self.install({"codex"})
        self.assertEqual(git(self.checkout, "rev-parse", "HEAD"), previous)

    def test_feature_worktree_removal_keeps_links(self) -> None:
        """Removing the temporary implementation worktree cannot invalidate live targets."""
        feature = self.base / "temporary feature"
        git(self.root, "worktree", "add", "-b", "feature", str(feature))
        with contextlib.redirect_stdout(io.StringIO()):
            deploy(feature, {"claude"}, self.env)
        git(self.root, "worktree", "remove", str(feature))
        self.assertEqual(self.settings.read_text(), "{}")
        self.assertTrue(self.settings.is_symlink())

    def test_unknown_skill_directory_preserved(self) -> None:
        """An existing package is not silently adopted or replaced."""
        legacy = self.base / "home/.claude/skills/shepherd"
        legacy.mkdir(parents=True)
        (legacy / "SKILL.md").write_text("old maintained package")
        with self.assertRaisesRegex(Conflict, "Unknown collision"):
            self.install()
        self.assertEqual((legacy / "SKILL.md").read_text(), "old maintained package")
        self.assertFalse(self.checkout.exists())

    def test_generated_write_through_preserved(self) -> None:
        """Ignored native edits are detected even when Git reports a clean worktree."""
        self.install()
        instruction = self.base / "home/.codex/AGENTS.md"
        instruction.write_text("native instruction edit")
        self.assertEqual(git(self.checkout, "status", "--porcelain"), "")
        with self.assertRaisesRegex(Conflict, "Generated installation files changed"):
            self.install()
        self.assertEqual(instruction.read_text(), "native instruction edit")

    def test_generated_failure_preserves_native_edit_and_journal(self) -> None:
        """Rollback never regenerates over an ignored output changed by a native client."""
        self.install()
        instruction = self.base / "home/.codex/AGENTS.md"

        def write(root: Path, targets: set[str]) -> None:
            instruction.write_text("native instruction edit")

        with self.assertRaisesRegex(Conflict, "Generated installation files changed"):
            self.install(native=write)
        self.assertEqual(instruction.read_text(), "native instruction edit")
        self.assertTrue((self.data / "pending.json").exists())

    def test_new_rule_and_failed_update_regenerate_prior_outputs(self) -> None:
        """New source rules reach both clients; a failed update restores prior generated content."""
        self.install()
        instruction = self.base / "home/.codex/AGENTS.md"
        before = instruction.read_text()
        self.write("rules/new-rule.md", "A new authored rule")
        self.commit()
        self.assertEqual(instruction.read_text(), before)

        def fail(root: Path, targets: set[str]) -> None:
            self.assertIn("A new authored rule", instruction.read_text())
            raise RuntimeError("fixture native failure")

        with self.assertRaisesRegex(RuntimeError, "native failure"):
            self.install(native=fail)
        self.assertEqual(instruction.read_text(), before)
        self.assertFalse((self.settings.parent / "rules/new-rule.md").exists())
        self.install()
        self.assertIn("A new authored rule", instruction.read_text())
        self.assertEqual(
            (self.settings.parent / "rules/new-rule.md").read_text(), "A new authored rule"
        )
        self.assertEqual(git(self.checkout, "ls-files", "generated"), "")

    def test_failed_journal_cleanup_keeps_committed_revision(self) -> None:
        """A cleanup error after the receipt commit cannot roll back committed provenance."""
        from unittest.mock import patch

        self.install()
        self.write("adapters/claude/settings.json", '{"new":true}')
        self.commit()
        original = Path.unlink

        def fail_cleanup(path: Path, missing_ok: bool = False) -> None:
            if path == self.data / "pending.json":
                raise OSError("fixture cleanup failure")
            original(path, missing_ok=missing_ok)

        with patch.object(Path, "unlink", fail_cleanup):
            with self.assertRaisesRegex(OSError, "cleanup failure"):
                self.install()
        receipt = json.loads((self.data / "installation.json").read_text())
        self.assertEqual(receipt["revision"], git(self.checkout, "rev-parse", "HEAD"))
        self.assertIn("new", self.settings.read_text())

    def test_source_runtime_overlap_refused(self) -> None:
        """Runtime destinations must not turn the source checkout into a client home."""
        self.env["CLAUDE_CONFIG_DIR"] = str(self.root)
        with self.assertRaisesRegex(Conflict, "overlap"):
            self.install()
        self.assertFalse(self.data.exists())

    def test_first_install_write_through_keeps_recovery_journal(self) -> None:
        """Dirty native content remains recoverable even without a previous revision."""

        def write(root: Path, targets: set[str]) -> None:
            self.settings.write_text('{"first native edit":true}')

        with self.assertRaisesRegex(Conflict, "Dirty"):
            self.install(native=write)
        self.assertIn(
            "first native edit", (self.checkout / "adapters/claude/settings.json").read_text()
        )
        self.assertTrue((self.data / "pending.json").exists())
