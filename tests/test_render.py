"""Behavioral checks for deterministic native generation and package portability."""

import os
import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path

from scripts.render import ROOT, outputs, render


class RenderingTests(unittest.TestCase):
    """Verify generated native contracts without installed client credentials."""

    def test_agent_schema_and_research_contract(self) -> None:
        """Verify agent schema and research contract."""
        files, _ = outputs(ROOT)
        for path, content in files.items():
            if path.suffix == ".toml":
                agent = tomllib.loads(content)
                self.assertTrue(agent["name"])
                self.assertTrue(agent["description"])
                self.assertIn("developer_instructions", agent)
                self.assertEqual(agent["sandbox_mode"], "read-only")
        research = files[Path("generated/codex/agents/docs-researcher.toml")]
        self.assertIn("Never create, edit, or run project code", research)
        self.assertIn("UNVERIFIED", research)

    def test_check_detects_drift_without_writing(self) -> None:
        """Verify check detects drift without writing."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source with spaces"
            shutil.copytree(
                ROOT,
                root,
                ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__"),
                symlinks=True,
            )
            render(root)
            target = root / "generated/codex/AGENTS.md"
            target.write_text("stale\n")
            self.assertIn("generated/codex/AGENTS.md", render(root, check=True))
            self.assertEqual(target.read_text(), "stale\n")
            render(root)
            self.assertEqual(render(root, check=True), [])

    def test_linked_helpers_resolve_inside_each_worktree(self) -> None:
        """Verify linked helpers resolve inside each worktree."""
        _, links = outputs(ROOT)
        for path, source in links.items():
            self.assertFalse(os.path.isabs(source))
            resolved = (ROOT / path.parent / source).resolve()
            self.assertTrue(resolved.is_relative_to(ROOT))
            if "scripts" in path.parts:
                self.assertTrue(resolved.is_dir())

    def test_reflect_is_explicit_only_in_both_clients(self) -> None:
        """Verify reflect is explicit only in both clients."""
        files, links = outputs(ROOT)
        self.assertIn(
            "disable-model-invocation: true",
            files[Path("generated/claude/skills/reflect/SKILL.md")],
        )
        self.assertIn(
            "allow_implicit_invocation: false",
            files[Path("generated/codex/skills/reflect/agents/openai.yaml")],
        )
        self.assertIn(Path(".claude/skills/reflect"), links)
        self.assertIn(Path(".agents/skills/reflect"), links)

    def test_codex_rules_are_assembled_once(self) -> None:
        """Verify codex rules are assembled once."""
        files, _ = outputs(ROOT)
        document = files[Path("generated/codex/AGENTS.md")]
        for rule in (ROOT / "rules").glob("*.md"):
            self.assertEqual(document.count(rule.read_text().strip()), 1)


if __name__ == "__main__":
    unittest.main()
