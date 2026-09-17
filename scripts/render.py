"""Convert existing harness content into ignored native client files."""

from __future__ import annotations

import argparse
import json
import os
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (
    "spec",
    "plan",
    "build",
    "test",
    "constraints",
    "review",
    "webperf",
    "code-simplify",
    "ship",
)
PERSONAS = ("code-reviewer", "security-auditor", "test-engineer", "web-performance-auditor")


def _text(root: Path, name: str) -> str:
    return (root / name).read_text()


def codex(text: str) -> str:
    """Translate native tool references without rewriting the author's workflow."""
    text = re.sub(
        r"(?<![\w./])/(" + "|".join(COMMANDS) + r")(?=[\s`]|$)",
        r"$\1",
        text,
    )
    return (
        text.replace("${CLAUDE_SKILL_DIR}", "<installed-skill-directory>")
        .replace("<!-- claude -->", "<!-- codex -->")
        .replace("— Claude", "— Codex")
        .replace("disable-model-invocation: true\n", "")
        .replace(
            "(Agent tool, `subagent_type: docs-researcher`)",
            "(native subagent named `docs-researcher`)",
        )
        .replace(
            "the Monitor tool, `persistent: true`,",
            "active-task execution, keeping this task running until the PR is terminal",
        )
        .replace(
            '`ExitWorktree(action: "remove", discard_changes: true)`',
            "switch the working directory to the main checkout",
        )
        .replace("`EnterWorktree`", "create a fresh Git worktree")
    )


def outputs(root: Path) -> tuple[dict[Path, str], dict[Path, str]]:
    """Describe generated files and links using only tracked source and dependency metadata."""
    files: dict[Path, str] = {}
    links: dict[Path, str] = {}
    lock = tomllib.loads(_text(root, "dependencies.lock.toml"))
    conventions = _text(root, "CLAUDE.md")
    rules = "\n".join(path.read_text() for path in sorted((root / "rules").glob("*.md")))
    files[Path("generated/claude/CLAUDE.md")] = conventions
    files[Path("generated/codex/AGENTS.md")] = codex(conventions + "\n" + rules)
    files[Path("generated/codex/config.toml")] = _text(root, "adapters/codex/config.toml").replace(
        "{agent_skills_revision}", lock["agent_skills"]["revision"]
    )
    for client in ("claude", "codex"):
        for name in ("shepherd", "reflect"):
            package = Path(f"generated/{client}/skills/{name}")
            body = _text(root, f"skills/{name}/SKILL.md")
            files[package / "SKILL.md"] = codex(body) if client == "codex" else body
            for helper in sorted((root / f"skills/{name}").iterdir()):
                if helper.name != "SKILL.md" and not helper.name.startswith("."):
                    links[package / helper.name] = os.path.relpath(helper, root / package)
            if name == "reflect":
                if client == "codex":
                    files[package / "agents/openai.yaml"] = (
                        "policy:\n  allow_implicit_invocation: false\n"
                    )
                local = Path(f"{'.agents' if client == 'codex' else '.claude'}/skills/reflect")
                links[local] = os.path.relpath(root / package, root / local.parent)
    for name in COMMANDS:
        files[Path(f"generated/codex/skills/{name}/SKILL.md")] = (
            f"---\nname: {name}\ndescription: Run the existing agent-skills {name} command.\n---\n\n"
            f"Read `.claude/commands/{name}.md` from the installed `agent-skills` plugin "
            "and follow it, passing the user's arguments as `$ARGUMENTS`. Apply the "
            "user's agent-skills rule overrides.\n"
        )
    for name in PERSONAS:
        files[Path(f"generated/codex/agents/{name}.toml")] = (
            f'name = "{name}"\ndescription = "The existing agent-skills {name} agent."\n'
            "developer_instructions = "
            + json.dumps(
                f"Read `agents/{name}.md` from the installed `agent-skills` plugin and follow it."
            )
            + "\n"
        )
    shared = _text(root, "agents/docs-researcher.md").replace(
        "{context7_version}", lock["context7"]["version"]
    )
    metadata = json.loads(_text(root, "adapters/claude/docs-researcher.json"))
    files[Path("generated/claude/agents/docs-researcher.md")] = (
        "---\n"
        + "".join(f"{key}: {json.dumps(value)}\n" for key, value in metadata.items())
        + "---\n\n"
        + shared
    )
    files[Path("generated/codex/agents/docs-researcher.toml")] = (
        _text(root, "adapters/codex/docs-researcher.toml")
        + "developer_instructions = "
        + json.dumps(codex(shared))
        + "\n"
    )
    return files, links


def render(root: Path = ROOT, *, check: bool = False) -> list[str]:
    """Write ignored native files, or report differences without changing the filesystem."""
    files, links = outputs(root)
    drift: list[str] = []
    generated = root / "generated"
    if generated.is_symlink():
        raise ValueError("Generated directory must not be a symlink")
    expected = set(files) | set(links)
    for relative in expected:
        for ancestor in (root / relative).parents:
            if ancestor == root:
                break
            if ancestor.is_symlink():
                raise ValueError(f"Unsafe generated ancestor: {ancestor}")
    if generated.exists():
        for directory, dirs, names in os.walk(generated, followlinks=False):
            base = Path(directory)
            names += [name for name in dirs if (base / name).is_symlink()]
            for name in names:
                relative = (base / name).relative_to(root)
                if relative not in expected:
                    drift.append(str(relative))
                    if not check:
                        (root / relative).unlink()
    for relative, content in files.items():
        target = root / relative
        if target.is_file() and not target.is_symlink() and target.read_text() == content:
            continue
        drift.append(str(relative))
        if not check:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                target.unlink()
            target.write_text(content)
    for relative, source in links.items():
        target = root / relative
        if target.is_symlink() and os.readlink(target) == source:
            continue
        drift.append(str(relative))
        if not check:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() or target.is_symlink():
                raise ValueError(f"Refusing to replace link collision: {target}")
            target.symlink_to(source)
    return drift


def main() -> int:
    """Generate ignored outputs, or fail when existing outputs differ from their source."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    drift = render(check=args.check)
    if args.check and drift:
        print("Generated output differs:\n" + "\n".join(drift))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
