"""Synthetic reflection fixtures; never use real client memories."""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "reflect_prune", ROOT / "skills/reflect/scripts/prune.py"
)
assert spec and spec.loader
prune = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prune)


class ReflectTests(unittest.TestCase):
    """Verify synthetic safety and recovery contracts."""

    def test_hash_selection_dry_run_and_prune(self) -> None:
        """Hash selection dry run and prune."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            memory = root / "project/memory/lesson.md"
            memory.parent.mkdir(parents=True)
            memory.write_text("lesson")
            index = memory.parent / "MEMORY.md"
            index.write_text("[lesson](lesson.md)\nkeep\n")
            manifest: dict[str, Any] = {
                "explicit_selection": True,
                "entries": [{"path": "project/memory/lesson.md", "sha256": prune.digest(memory)}],
            }
            prune.prune(root, manifest, True)
            self.assertTrue(memory.exists())
            memory.write_text("changed")
            with self.assertRaises(ValueError):
                prune.prune(root, manifest, False)
            self.assertTrue(memory.exists())
            memory.write_text("lesson")
            self.assertEqual(
                prune.prune(root, manifest, False)["deleted"], ["project/memory/lesson.md"]
            )
            self.assertEqual(index.read_text(), "keep\n")
            self.assertEqual(
                prune.prune(root, manifest, False)["skipped"], ["project/memory/lesson.md"]
            )

    def test_symlink_ancestors_and_indexes(self) -> None:
        """Symlink ancestors and indexes."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            outside = root / "outside"
            outside.mkdir()
            (root / "project").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                prune.memory_path(root, "project/memory/file.md")
            (root / "project").unlink()
            (root / "project/memory").mkdir(parents=True)
            (root / "project/memory/MEMORY.md").symlink_to(outside / "index")
            with self.assertRaises(ValueError):
                prune.memory_path(root, "project/memory/file.md")

    def test_invalid_selection_and_paths(self) -> None:
        """Invalid selection and paths."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for relative in [
                "../memory/a.md",
                "/project/memory/a.md",
                "project/memory/MEMORY.md",
                "project/memory/../a.md",
            ]:
                with self.subTest(relative=relative), self.assertRaises(ValueError):
                    prune.memory_path(root, relative)
            with self.assertRaises(ValueError):
                prune.prune(root, {}, False)

    def test_deployment_revision_links_and_discovery(self) -> None:
        """Deployment revision links and discovery."""
        import subprocess

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            checkout = root / "checkout"
            checkout.mkdir()

            def git(*args: str) -> str:
                return subprocess.check_output(
                    ["git", "-C", str(checkout), *args], text=True
                ).strip()

            git("init", "-q")
            git("checkout", "-qb", "install/local")
            git("config", "user.email", "test@example.invalid")
            git("config", "user.name", "Test")
            git("remote", "add", "origin", "git@github.com:owner/repo.git")
            rule = checkout / "generated/codex/AGENTS.md"
            rule.parent.mkdir(parents=True)
            rule.write_text("reviewed promotion")
            git("add", ".")
            git("commit", "-qm", "fixture")
            revision = git("rev-parse", "HEAD")
            link = root / "AGENTS.md"
            link.symlink_to(rule)
            transcript = root / "discovery.txt"
            transcript.write_text("fresh Codex loaded reviewed promotion")
            receipt: dict[str, Any] = {
                "checkout": str(checkout),
                "revision": revision,
                "targets": ["codex"],
                "links": {
                    str(link): {
                        "source": "generated/codex/AGENTS.md",
                        "backup": None,
                        "target": "codex",
                    }
                },
            }
            manifest: dict[str, Any] = {
                "merge_commit": revision,
                "repository": "owner/repo",
                "targets": ["codex"],
                "deployment": {
                    "codex": {
                        "revision": revision,
                        "discovery_command": "codex",
                        "discovery_output": str(transcript),
                        "discovery_output_sha256": prune.digest(transcript),
                        "confirmed_loaded": "codex",
                        "links": {str(link): prune.digest(rule)},
                    }
                },
            }
            prune.deployment(manifest, receipt)
            manifest["repository"] = "other/repository"
            with self.assertRaises(ValueError):
                prune.deployment(manifest, receipt)
            manifest["repository"] = "owner/repo"
            receipt["links"][str(link)]["target"] = "claude"
            with self.assertRaises(ValueError):
                prune.deployment(manifest, receipt)
            receipt["links"][str(link)]["target"] = "codex"
            receipt["links"][str(link)]["source"] = "unrelated.md"
            with self.assertRaises(ValueError):
                prune.deployment(manifest, receipt)
            receipt["links"][str(link)]["source"] = "generated/codex/AGENTS.md"
            redirected = root / "redirected"
            redirected.symlink_to(checkout, target_is_directory=True)
            receipt["checkout"] = str(redirected)
            with self.assertRaises(ValueError):
                prune.deployment(manifest, receipt)
            receipt["checkout"] = str(checkout)
            manifest["targets"].append("claude")
            with self.assertRaises(ValueError):
                prune.deployment(manifest, receipt)
            manifest["targets"].pop()
            transcript.write_text("changed")
            with self.assertRaises(ValueError):
                prune.deployment(manifest, receipt)
            transcript.write_text("fresh Codex loaded reviewed promotion")
            link.unlink()
            link.write_text(rule.read_text())
            with self.assertRaises(ValueError):
                prune.deployment(manifest, receipt)

    def test_cli_unmerged_and_missing_manifest_block(self) -> None:
        """Cli unmerged and missing manifest block."""
        import json
        import sys
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "manifest.json"
            with patch.object(sys, "argv", ["prune.py", str(path)]):
                with self.assertRaises(FileNotFoundError):
                    prune.main()
            path.write_text(json.dumps({"pr": 1, "repository": "owner/repo"}))
            path.chmod(0o600)
            for state in ["OPEN", "CLOSED"]:
                with (
                    patch.object(sys, "argv", ["prune.py", str(path)]),
                    patch.object(
                        prune.subprocess,
                        "check_output",
                        return_value=json.dumps({"state": state, "mergeCommit": None}),
                    ),
                ):
                    with self.assertRaises(ValueError):
                        prune.main()
