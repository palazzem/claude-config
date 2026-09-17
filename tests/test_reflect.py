"""Exercise reflection's newline manifest and memory reader using disposable files."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/reflect/scripts"


class ReflectTests(unittest.TestCase):
    """Keep the original stdin interface and reject escaping deletion paths."""

    def setUp(self) -> None:
        """Create private synthetic memories, never a real client's memory root."""
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "projects"
        self.memory = self.root / "project/memory"
        self.memory.mkdir(parents=True)
        self.lesson = self.memory / "lesson.md"
        self.lesson.write_text("A synthetic lesson.\n")
        self.index = self.memory / "MEMORY.md"
        self.index.write_text("[Lesson](lesson.md)\n[Retained](other.md)\n")

    def run_helper(
        self, name: str, manifest: str = "", *args: str
    ) -> subprocess.CompletedProcess[str]:
        """Run a real Bash helper with a synthetic memory root and captured output."""
        return subprocess.run(
            ["bash", str(SCRIPTS / name), *args],
            input=manifest,
            text=True,
            capture_output=True,
            env=dict(os.environ, REFLECT_MEMORY_ROOT=str(self.root)),
            check=False,
        )

    def test_dry_run_then_prune_and_idempotent_resume(self) -> None:
        """The same newline manifest previews, deletes, and safely skips absent memories."""
        manifest = "project/memory/lesson.md\n"
        preview = self.run_helper("prune.sh", manifest, "--dry-run")
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(json.loads(preview.stdout)["deleted"], [manifest.strip()])
        self.assertTrue(self.lesson.exists())
        result = self.run_helper("prune.sh", manifest)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.lesson.exists())
        self.assertEqual(self.index.read_text(), "[Retained](other.md)\n")
        resumed = self.run_helper("prune.sh", manifest)
        self.assertEqual(json.loads(resumed.stdout)["skipped"], [manifest.strip()])

    def test_absolute_path_blank_lines_and_missing_final_newline(self) -> None:
        """Existing absolute-path, blank-line, and final-line handling remains compatible."""
        result = self.run_helper("prune.sh", f"\n  \n{self.lesson}", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["deleted"], ["project/memory/lesson.md"])

    def test_entire_manifest_is_validated_before_deleting(self) -> None:
        """One invalid line prevents every deletion, including earlier valid entries."""
        for invalid in ["../memory/lesson.md", "project/memory/MEMORY.md", "/outside.md"]:
            with self.subTest(invalid=invalid):
                result = self.run_helper("prune.sh", f"project/memory/lesson.md\n{invalid}\n")
                self.assertEqual(result.returncode, 2)
                self.assertTrue(self.lesson.exists())
                self.assertIn("lesson.md", self.index.read_text())

    def test_reject_project_memory_file_and_index_symlinks(self) -> None:
        """Symlinks in every relevant path component fail before memory or index writes."""
        outside = self.base / "outside"
        outside.mkdir()
        victim = outside / "victim.md"
        victim.write_text("Never change this")
        for relative in [
            "linked",
            "project/memory",
            "project/memory/link.md",
            "project/memory/MEMORY.md",
        ]:
            with self.subTest(relative=relative):
                link = self.root / relative
                if link == self.memory:
                    self.memory.rename(self.base / "saved-memory")
                if link == self.index:
                    self.index.unlink()
                link.symlink_to(outside if relative in {"linked", "project/memory"} else victim)
                manifest = {
                    "linked": "linked/memory/victim.md",
                    "project/memory": "project/memory/victim.md",
                }.get(
                    relative,
                    "project/memory/link.md"
                    if relative.endswith("link.md")
                    else "project/memory/lesson.md",
                )
                result = self.run_helper("prune.sh", manifest + "\n")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(victim.read_text(), "Never change this")
                self.assertTrue(
                    (self.base / "saved-memory/lesson.md").exists()
                    if link == self.memory
                    else self.lesson.exists()
                )
                link.unlink()
                if link == self.memory:
                    (self.base / "saved-memory").rename(self.memory)
                if link == self.index:
                    self.index.write_text("[Lesson](lesson.md)\n")

    def test_reject_symlink_in_memory_root_ancestors(self) -> None:
        """A linked runtime ancestor cannot redirect the accepted memory root."""
        link = self.base / "runtime-link"
        link.symlink_to(self.root)
        self.root = link
        result = self.run_helper("prune.sh", "project/memory/lesson.md\n")
        self.assertEqual(result.returncode, 2)
        self.assertTrue(self.lesson.exists())

    def test_inventory_preserves_frontmatter_and_excludes_index(self) -> None:
        """The sole memory reader retains metadata and emits one record per memory."""
        self.lesson.write_text(
            '---\nname: "Lesson"\ndescription: "Useful"\nmetadata:\n  type: feedback\n---\nBody\n'
        )
        result = self.run_helper("inventory.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Lesson")
        self.assertEqual(rows[0]["type"], "feedback")
        self.assertEqual(rows[0]["body"], "Body")


if __name__ == "__main__":
    unittest.main()
