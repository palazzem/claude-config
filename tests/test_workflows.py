"""Verify preserved workflows survive native conversion without process rewrites."""

import unittest
from pathlib import Path

from scripts.render import COMMANDS, PERSONAS, ROOT, outputs


class WorkflowTests(unittest.TestCase):
    """Check original entry points, detailed process and native runtime references."""

    def test_wrappers_load_original_commands_and_personas(self) -> None:
        """Existing names load upstream resources instead of a substituted workflow."""
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
            self.assertIn(f"name: {name}\n", body)
            self.assertIn(f".claude/commands/{name}.md", body)
            self.assertIn("$ARGUMENTS", body)
            self.assertIn("agent-skills rule overrides", body)
        self.assertEqual(
            set(PERSONAS),
            {"code-reviewer", "security-auditor", "test-engineer", "web-performance-auditor"},
        )
        for name in PERSONAS:
            self.assertIn(f"agents/{name}.md", files[Path(f"generated/codex/agents/{name}.toml")])

    def test_original_worktree_artifacts_and_build_overrides_survive(self) -> None:
        """Native instructions retain original artifact scope and build prerequisites."""
        files, _ = outputs(ROOT)
        body = files[Path("generated/codex/AGENTS.md")]
        for text in (
            ".claude/specs/<slug>/spec.md",
            ".claude/specs/<slug>/plan.md",
            ".claude/specs/<slug>/todo.md",
            "anything else uncommitted stops the run",
            "artifacts never enter a PR",
            "Never read, overwrite, or delete it",
            "never count it when checking for an existing plan",
        ):
            self.assertIn(text, body)
        self.assertNotIn(".harness/work/", body)

    def test_claude_skill_bodies_are_preserved(self) -> None:
        """Claude receives the authored skill bodies without paraphrase or appended process."""
        files, _ = outputs(ROOT)
        for name in ("reflect", "shepherd"):
            self.assertEqual(
                files[Path(f"generated/claude/skills/{name}/SKILL.md")],
                (ROOT / f"skills/{name}/SKILL.md").read_text(),
            )

    def test_shepherd_keeps_continuous_monitoring_and_stack_process(self) -> None:
        """Codex conversion preserves babysitting through terminal and stack sequencing."""
        files, _ = outputs(ROOT)
        body = files[Path("generated/codex/skills/shepherd/SKILL.md")]
        self.assertNotIn("${CLAUDE_SKILL_DIR}", body)
        self.assertNotIn("the Monitor tool", body)
        self.assertIn("until the PR is terminal", body)
        self.assertIn("<!-- codex -->", body)
        self.assertIn("— Codex", body)
        for original in (
            "Handle them, then arm again",
            "never a fresh `baseline`",
            "`gh stack sync --prune`",
            "the bottom open one",
            "**Changed after review:**",
            "**Open:**",
            "Report first, cleanup second",
            "A state that contradicts the watcher",
        ):
            self.assertIn(original, body)
        self.assertNotIn("explicit handoff", body)
        self.assertNotIn("paused/resumable", body)

    def test_reflect_retains_author_selection_and_close_behavior(self) -> None:
        """Native translation preserves the user's redundant-memory and closed-PR process."""
        files, _ = outputs(ROOT)
        for client in ("codex", "claude"):
            body = files[Path(f"generated/{client}/skills/reflect/SKILL.md")]
            self.assertIn("pruned after merge unless you say `keep <n>`", body)
            self.assertIn("`none` with redundant memories", body)
            self.assertIn("`CLOSED`", body)
            self.assertIn("the manifest is gone", body)


if __name__ == "__main__":
    unittest.main()
