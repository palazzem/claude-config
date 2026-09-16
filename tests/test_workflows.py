"""Test worktree artifact isolation and retained native workflow entry points."""

import tempfile
import unittest
from pathlib import Path

from scripts.render import COMMANDS, PERSONAS, ROOT, artifact_directory, build_auto_spec, outputs


class WorkflowTests(unittest.TestCase):
    """Check that lifecycle wrappers preserve upstream resources and local scope."""

    def test_other_worktree_spec_cannot_satisfy_build(self) -> None:
        """Verify other worktree spec cannot satisfy build."""
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory) / "current"
            other = worktree / ".harness/work/other"
            other.mkdir(parents=True)
            (other / "spec.md").write_text("Other task")
            with self.assertRaisesRegex(ValueError, "Run spec first"):
                build_auto_spec(worktree)
            selected = artifact_directory(worktree)
            selected.mkdir(parents=True)
            (selected / "spec.md").write_text("Current task")
            self.assertEqual(build_auto_spec(worktree), selected / "spec.md")

    def test_legacy_resume_and_conflict(self) -> None:
        """Verify legacy resume and conflict."""
        with tempfile.TemporaryDirectory() as directory:
            worktree = Path(directory) / "current"
            legacy = worktree / ".claude/specs/current"
            legacy.mkdir(parents=True)
            (legacy / "plan.md").write_text("In flight")
            self.assertEqual(artifact_directory(worktree), legacy)
            current = worktree / ".harness/work/current"
            current.mkdir(parents=True)
            (current / "plan.md").write_text("Different")
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                artifact_directory(worktree)

    def test_wrappers_load_original_commands_and_personas(self) -> None:
        """Verify wrappers load original commands and personas."""
        files, _ = outputs(ROOT)
        self.assertEqual(
            set(COMMANDS),
            {
                "spec",
                "plan",
                "build",
                "test",
                "constraints",
                "review",
                "webperf",
                "code-simplify",
                "ship",
            },
        )
        for name in COMMANDS:
            body = files[Path(f"generated/codex/skills/{name}/SKILL.md")]
            self.assertIn(f".claude/commands/{name}.md", body)
            self.assertIn("Honor prior authorization", body)
            self.assertIn("Never commit process artifacts", body)
        for name in PERSONAS:
            body = files[Path(f"generated/codex/agents/{name}.toml")]
            self.assertIn(f"agents/{name}.md", body)
            self.assertIn("read-only", body)


if __name__ == "__main__":
    unittest.main()
