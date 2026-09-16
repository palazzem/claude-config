"""Exercise native command scope, collision protection and partial-operation recovery."""

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.installer import native

ROOT = Path(__file__).resolve().parents[1]


class NativeTests(unittest.TestCase):
    """Keep external operations pinned, scoped, verifiable and recoverable."""

    def test_selected_targets_and_pins(self) -> None:
        """Target selection never installs the other client and has no floating dependency."""
        for selected in ({"codex"}, {"claude"}, {"codex", "claude"}):
            commands = native.commands(ROOT, selected)
            self.assertEqual(
                sum(command[:3] == ["gh", "extension", "install"] for command in commands), 1
            )
            for target, agent in (("codex", "codex"), ("claude", "claude-code")):
                skills = [
                    command for command in commands if "--agent" in command and agent in command
                ]
                self.assertEqual(len(skills), int(target in selected))
            self.assertNotIn("latest", str(commands))
            self.assertIn("ctx7@0.5.11", commands[-1])
            self.assertEqual("ccstatusline@2.2.27" in commands[-1], "claude" in selected)

    def test_missing_prerequisite(self) -> None:
        """Missing native tooling fails before any upstream operation."""
        with (
            patch.object(native.shutil, "which", return_value=None),
            self.assertRaisesRegex(RuntimeError, "Required native"),
        ):
            native.preflight(ROOT, {"codex"})

    def test_unknown_skill_and_extension_preserved(self) -> None:
        """Force flags are gated by identity checks for both extension and skill collisions."""
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with (
                patch.dict(os.environ, {"HOME": str(home), "XDG_DATA_HOME": str(home / "data")}),
                patch.object(native.shutil, "which", return_value="tool"),
                patch.object(
                    native, "_run", return_value="a1b4a3d4d0bcde9ec3a78ab99b2d63af121857a9"
                ),
            ):
                skill = home / ".agents/skills/gh-stack/SKILL.md"
                skill.parent.mkdir(parents=True)
                skill.write_text("unrelated package")
                with self.assertRaisesRegex(RuntimeError, "Unknown skill collision"):
                    native.preflight(ROOT, {"codex"})
                self.assertEqual(skill.read_text(), "unrelated package")
                skill.unlink()
                extension = home / "data/gh/extensions/gh-stack"
                extension.mkdir(parents=True)
                (extension / "manifest.yml").write_text("owner: another-owner\nname: gh-stack\n")
                with self.assertRaisesRegex(RuntimeError, "Unknown extension collision"):
                    native.preflight(ROOT, {"codex"})

    def test_failed_native_call_still_checks_links(self) -> None:
        """An unsuccessful native operation can write settings, so its guard always runs."""
        guard = Mock()
        with (
            patch.object(native, "preflight"),
            patch.object(native, "_snapshot") as snapshot,
            patch.object(native, "_run", side_effect=subprocess.CalledProcessError(1, ["gh"])),
            patch.object(native, "verify") as verify,
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                native.install(ROOT, {"codex"}, guard)
            guard.assert_called_once_with()
            snapshot.assert_called_once_with()
            verify.assert_not_called()

    def test_guard_conflict_stops_later_native_operations(self) -> None:
        """A changed setting is retained for recovery before another installer can rewrite it."""
        with (
            patch.object(native, "preflight"),
            patch.object(native, "_snapshot"),
            patch.object(native, "_run") as run,
        ):
            with self.assertRaisesRegex(RuntimeError, "settings conflict"):
                native.install(ROOT, {"codex"}, Mock(side_effect=RuntimeError("settings conflict")))
            self.assertEqual(run.call_count, 1)

    def test_payload_hash_detects_helpers_and_symlink_changes(self) -> None:
        """Whole-package verification includes helpers and link text, without following links."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "SKILL.md").write_text("skill")
            helper = root / "helper.sh"
            helper.write_text("first")
            link = root / "resources"
            link.symlink_to("outside")
            before = native.payload_hash(root)
            helper.write_text("tampered")
            self.assertNotEqual(before, native.payload_hash(root))
            helper.write_text("first")
            link.unlink()
            link.symlink_to("elsewhere")
            self.assertNotEqual(before, native.payload_hash(root))

    def test_native_catalog_matches_lock(self) -> None:
        """Claude pins the plugin payload itself instead of only its marketplace revision."""
        lock = native._lock(ROOT)
        catalog = json.loads(
            (ROOT / "adapters/claude/marketplace/.claude-plugin/marketplace.json").read_text()
        )
        self.assertEqual(catalog["plugins"][0]["source"]["sha"], lock["agent_skills"]["revision"])

    def test_registration_snapshot_keeps_original_bytes(self) -> None:
        """Recovery snapshots preserve native registries and settings before mutation."""
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            claude = home / "claude"
            (claude / "plugins").mkdir(parents=True)
            content = b'{"plugins": {"unrelated": []}}\n'
            (claude / "plugins/installed_plugins.json").write_bytes(content)
            with patch.dict(
                os.environ,
                {
                    "HOME": str(home),
                    "CLAUDE_CONFIG_DIR": str(claude),
                    "CODEX_HOME": str(home / "codex"),
                    "XDG_DATA_HOME": str(home / "data"),
                },
            ):
                native._snapshot()
            copies = list(
                (home / "data/harness/backups/native").glob(
                    "*/claude/plugins/installed_plugins.json"
                )
            )
            self.assertEqual(len(copies), 1)
            self.assertEqual(
                hashlib.sha256(copies[0].read_bytes()).digest(), hashlib.sha256(content).digest()
            )

    def test_bad_dependency_revision_is_rejected(self) -> None:
        """An invalid immutable pin never reaches a native command."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "dependencies.lock.toml").write_text(
                (ROOT / "dependencies.lock.toml")
                .read_text()
                .replace("d2c37ef6225dd8726cdd369a8030307f48592d26", "main")
            )
            with (
                patch.object(native, "_run") as run,
                self.assertRaisesRegex(ValueError, "Invalid locked revision"),
            ):
                native.preflight(root, {"codex"})
            run.assert_not_called()

    def test_release_revision_pairing_is_rejected(self) -> None:
        """A moved upstream release cannot silently replace the locked extension/skill pair."""
        with (
            patch.object(native.shutil, "which", return_value="tool"),
            patch.object(native, "_run", return_value="0" * 40),
            self.assertRaisesRegex(RuntimeError, "pairing changed"),
        ):
            native.preflight(ROOT, {"codex"})

    def test_payload_hash_uses_portable_path_order(self) -> None:
        """Native payload hashes order full relative names, independent of Path part ordering."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a").mkdir()
            (root / "a/file").write_bytes(b"nested")
            (root / "a.md").write_bytes(b"flat")
            expected = hashlib.sha256(
                b"a.md\0"
                + hashlib.sha256(b"flat").digest()
                + b"a/file\0"
                + hashlib.sha256(b"nested").digest()
            ).hexdigest()
            self.assertEqual(native.payload_hash(root), expected)
