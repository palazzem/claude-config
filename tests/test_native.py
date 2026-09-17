"""Exercise native command scope, collision protection and partial-operation recovery."""

import hashlib
import io
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
            with (
                tempfile.TemporaryDirectory() as directory,
                patch.dict(os.environ, {"XDG_DATA_HOME": str(Path(directory).resolve())}),
            ):
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
            home = Path(directory).resolve()
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
            patch.object(native, "_extension_needed", return_value=True),
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
            patch.object(native, "_extension_needed", return_value=True),
            patch.object(native, "_snapshot"),
            patch.object(native, "_run") as run,
        ):
            with self.assertRaisesRegex(RuntimeError, "settings conflict"):
                native.install(ROOT, {"codex"}, Mock(side_effect=RuntimeError("settings conflict")))
            self.assertEqual(run.call_count, 1)

    def test_registration_snapshot_keeps_original_bytes(self) -> None:
        """Recovery snapshots preserve native registries and settings before mutation."""
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory).resolve()
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
            root = Path(directory).resolve()
            (root / "dependencies.lock.toml").write_text(
                (ROOT / "dependencies.lock.toml")
                .read_text()
                .replace("be4e44a9fbc5e8df0beaefadbb28bd22ee61cc39", "main")
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

    def test_correct_extension_pin_is_skipped(self) -> None:
        """Repeat installation never invokes GitHub's force-upgrade path for an existing pin."""
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"XDG_DATA_HOME": str(Path(directory).resolve())}),
        ):
            manifest = Path(directory).resolve() / "gh/extensions/gh-stack/manifest.yml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                "owner: github\nname: gh-stack\nhost: github.com\ntag: v0.1.0\nispinned: true\n"
            )
            before = manifest.read_bytes()
            for _ in range(2):
                calls = native.commands(ROOT, {"codex"})
                self.assertFalse(any(call[:2] == ["gh", "extension"] for call in calls))
                self.assertEqual(manifest.read_bytes(), before)

    def test_mismatched_extension_is_preserved(self) -> None:
        """A shared unpinned or changed extension requires explicit native reinstallation."""
        for tag, pinned in (("v0.1.0", "false"), ("v0.1.1", "true")):
            with (
                tempfile.TemporaryDirectory() as directory,
                patch.dict(os.environ, {"XDG_DATA_HOME": str(Path(directory).resolve())}),
            ):
                manifest = Path(directory).resolve() / "gh/extensions/gh-stack/manifest.yml"
                manifest.parent.mkdir(parents=True)
                manifest.write_text(
                    f"owner: github\nname: gh-stack\nhost: github.com\ntag: {tag}\nispinned: {pinned}\n"
                )
                before = manifest.read_bytes()
                with self.assertRaisesRegex(RuntimeError, "preserved"):
                    native.commands(ROOT, {"codex"})
                self.assertEqual(manifest.read_bytes(), before)

    def test_native_stderr_is_reported_before_failure(self) -> None:
        """Native warnings and errors remain visible when subprocess output is captured."""
        message = "native installer warned before failing\n"
        result = subprocess.CompletedProcess(["native"], 1, stdout="", stderr=message)
        output = io.StringIO()
        with (
            patch.object(native.subprocess, "run", return_value=result),
            patch.object(native.sys, "stderr", output),
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                native._run(["native"])
        self.assertEqual(output.getvalue(), message)

    def test_claude_upstream_drift_blocks_new_install(self) -> None:
        """An unpinned upstream Claude source cannot silently install an unreviewed revision."""
        revision = native._lock(ROOT)["gh_stack"]["revision"]
        with (
            patch.object(native.shutil, "which", return_value="tool"),
            patch.object(native, "_extension_needed", return_value=False),
            patch.object(native, "_claude_current", return_value=False),
            patch.object(native, "_run", side_effect=["help", revision, "0" * 40 + "\tHEAD"]),
            self.assertRaisesRegex(RuntimeError, "source moved"),
        ):
            native.preflight(ROOT, {"claude"})

    def test_existing_claude_package_is_skipped_or_reinstalled(self) -> None:
        """Exact packages stay installed; stale registrations use one scoped native reinstall pair."""
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"XDG_DATA_HOME": str(Path(directory).resolve())}),
            patch.object(native, "_claude_registration", return_value={"version": "older"}),
        ):
            with patch.object(native, "_claude_current", return_value=True):
                calls = native.commands(ROOT, {"claude"})
                self.assertFalse(
                    any(
                        call[:3]
                        in (["claude", "plugin", "install"], ["claude", "plugin", "uninstall"])
                        for call in calls
                    )
                )
            with patch.object(native, "_claude_current", return_value=False):
                calls = native.commands(ROOT, {"claude"})
                self.assertIn(
                    [
                        "claude",
                        "plugin",
                        "uninstall",
                        "agent-skills@addy-agent-skills",
                        "--scope",
                        "user",
                        "--keep-data",
                    ],
                    calls,
                )
                removal = next(
                    index
                    for index, command in enumerate(calls)
                    if command[:3] == ["claude", "plugin", "uninstall"]
                )
                self.assertEqual(
                    calls[removal + 1],
                    [
                        "claude",
                        "plugin",
                        "install",
                        "agent-skills@addy-agent-skills",
                        "--scope",
                        "user",
                    ],
                )
            self.assertIn(
                ["claude", "plugin", "marketplace", "add", "addyosmani/agent-skills"], calls
            )

    def test_reinstall_failure_runs_guard_and_stops(self) -> None:
        """A failed second native command exposes intermediate settings changes to recovery."""
        removal = [
            "claude",
            "plugin",
            "uninstall",
            "agent-skills@addy-agent-skills",
            "--scope",
            "user",
            "--keep-data",
        ]
        addition = [
            "claude",
            "plugin",
            "install",
            "agent-skills@addy-agent-skills",
            "--scope",
            "user",
        ]
        guard = Mock()
        with (
            patch.object(native, "preflight"),
            patch.object(native, "_snapshot"),
            patch.object(native, "commands", return_value=[removal, addition, ["npm", "install"]]),
            patch.object(
                native, "_run", side_effect=["removed", subprocess.CalledProcessError(1, addition)]
            ) as run,
            patch.object(native, "verify") as verify,
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                native.install(ROOT, {"claude"}, guard)
            self.assertEqual(run.call_count, 2)
            guard.assert_called_once_with()
            verify.assert_not_called()

    def test_reinstall_success_checks_settings_after_pair(self) -> None:
        """Native uninstall temporarily removes enablement; only the complete pair is guarded."""
        removal = [
            "claude",
            "plugin",
            "uninstall",
            "agent-skills@addy-agent-skills",
            "--scope",
            "user",
            "--keep-data",
        ]
        addition = [
            "claude",
            "plugin",
            "install",
            "agent-skills@addy-agent-skills",
            "--scope",
            "user",
        ]
        sequence = Mock()
        with (
            patch.object(native, "preflight"),
            patch.object(native, "_snapshot"),
            patch.object(native, "commands", return_value=[removal, addition]),
            patch.object(native, "_run", side_effect=lambda args: sequence.command(args)),
            patch.object(native, "verify"),
        ):
            native.install(ROOT, {"claude"}, lambda: sequence.guard())
        self.assertEqual(
            [entry[0] for entry in sequence.mock_calls], ["command", "command", "guard"]
        )
