"""Check that native rendering preserves authored source and portable packages."""

import os
import shutil
import tempfile
import tomllib
import unittest
from pathlib import Path

from scripts.render import ROOT, codex, outputs, render


def _copy_source(destination: Path) -> None:
    """Copy rendering inputs without generated files, private state or environments."""
    for name in ("CLAUDE.md", "AGENTS.md", "dependencies.lock.toml"):
        shutil.copy2(ROOT / name, destination / name)
    for name in ("rules", "skills", "agents", "adapters"):
        shutil.copytree(
            ROOT / name,
            destination / name,
            symlinks=True,
            ignore=shutil.ignore_patterns("__pycache__"),
        )


class RenderingTests(unittest.TestCase):
    """Exercise native conversion without client credentials or runtime installation."""

    def test_agent_schema_preserves_research_contract(self) -> None:
        """Native agents retain required metadata and the full authored research prompt."""
        files, _ = outputs(ROOT)
        for path, content in files.items():
            if path.suffix == ".toml" and "agents" in path.parts:
                agent = tomllib.loads(content)
                self.assertTrue(agent["name"])
                self.assertTrue(agent["description"])
                self.assertTrue(agent["developer_instructions"])
        lock = tomllib.loads((ROOT / "dependencies.lock.toml").read_text())
        source = (
            (ROOT / "agents/docs-researcher.md")
            .read_text()
            .replace("{context7_version}", lock["context7"]["version"])
        )
        research = tomllib.loads(files[Path("generated/codex/agents/docs-researcher.toml")])
        self.assertEqual(research["developer_instructions"], codex(source))
        self.assertIn(source, files[Path("generated/claude/agents/docs-researcher.md")])

    def test_render_leaves_authored_files_untouched(self) -> None:
        """Generating and repairing ignored outputs never rewrites source instructions."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            _copy_source(root)
            originals = {name: (root / name).read_bytes() for name in ("CLAUDE.md", "AGENTS.md")}
            files, _ = outputs(root)
            self.assertTrue(all(path.parts[0] == "generated" for path in files))
            self.assertTrue(render(root))
            self.assertEqual(render(root, check=True), [])
            target = root / "generated/codex/AGENTS.md"
            target.write_text("native edit\n")
            self.assertIn("generated/codex/AGENTS.md", render(root, check=True))
            self.assertEqual(target.read_text(), "native edit\n")
            render(root)
            self.assertEqual(render(root, check=True), [])
            for name, content in originals.items():
                self.assertEqual((root / name).read_bytes(), content)

    def test_linked_packages_resolve_inside_each_worktree(self) -> None:
        """A fresh worktree renders complete packages with worktree-relative helpers."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            _copy_source(root)
            render(root)
            _, links = outputs(root)
            for path, source in links.items():
                self.assertFalse(os.path.isabs(source))
                resolved = (root / path).resolve(strict=True)
                self.assertTrue(resolved.is_relative_to(root))
                if "scripts" in path.parts:
                    self.assertTrue(
                        (
                            resolved / ("watch-pr.sh" if "shepherd" in path.parts else "prune.sh")
                        ).is_file()
                    )
            for client in (".claude", ".agents"):
                package = root / client / "skills/reflect"
                self.assertTrue((package / "SKILL.md").is_file())
                self.assertTrue((package / "scripts/prune.sh").is_file())

    def test_reflect_remains_explicit_only(self) -> None:
        """Both clients retain native metadata that prevents implicit reflection."""
        files, _ = outputs(ROOT)
        self.assertIn(
            "disable-model-invocation: true",
            files[Path("generated/claude/skills/reflect/SKILL.md")],
        )
        self.assertNotIn(
            "disable-model-invocation:", files[Path("generated/codex/skills/reflect/SKILL.md")]
        )
        self.assertIn(
            "allow_implicit_invocation: false",
            files[Path("generated/codex/skills/reflect/agents/openai.yaml")],
        )

    def test_every_authored_rule_is_rendered_without_fixed_allowlist(self) -> None:
        """Adding a rule automatically includes its full content in Codex instructions."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            _copy_source(root)
            new_rule = "# Additional rule\n\nPreserve this complete authored convention.\n"
            (root / "rules/new-rule.md").write_text(new_rule)
            files, _ = outputs(root)
            document = files[Path("generated/codex/AGENTS.md")]
            self.assertIn(new_rule, document)
            self.assertIn(codex((root / "CLAUDE.md").read_text()), document)
            for rule in (root / "rules").glob("*.md"):
                self.assertEqual(document.count(codex(rule.read_text()).strip()), 1)
            self.assertEqual(
                files[Path("generated/claude/CLAUDE.md")], (root / "CLAUDE.md").read_text()
            )

    def test_unsafe_output_ancestors_fail_before_any_writes(self) -> None:
        """Check and render both reject symlinked package parents without touching outside files."""
        for relative in (".agents", ".claude", "generated", "generated/codex"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve() / "source"
                root.mkdir()
                _copy_source(root)
                outside = root.parent / "outside"
                outside.mkdir()
                sentinel = outside / "preserve.txt"
                sentinel.write_text("unrelated content")
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(outside, target_is_directory=True)
                for check in (True, False):
                    with self.assertRaisesRegex(ValueError, "symlink|ancestor"):
                        render(root, check=check)
                    self.assertEqual(sentinel.read_text(), "unrelated content")
                    self.assertEqual(list(outside.iterdir()), [sentinel])
                    self.assertFalse((root / "generated/claude/CLAUDE.md").exists())

    def test_replaced_output_symlink_never_overwrites_external_file(self) -> None:
        """Repair replaces an output entry itself rather than writing through its symlink."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "source"
            root.mkdir()
            _copy_source(root)
            render(root)
            outside = root.parent / "outside.txt"
            outside.write_text("retain external file")
            target = root / "generated/codex/AGENTS.md"
            target.unlink()
            target.symlink_to(outside)
            self.assertIn("generated/codex/AGENTS.md", render(root, check=True))
            self.assertTrue(target.is_symlink())
            self.assertEqual(outside.read_text(), "retain external file")
            render(root)
            self.assertFalse(target.is_symlink())
            self.assertEqual(outside.read_text(), "retain external file")


if __name__ == "__main__":
    unittest.main()
