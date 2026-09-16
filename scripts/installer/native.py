"""Install reviewed third-party packages through native clients, retaining runtime ownership."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable
from pathlib import Path

from scripts.installer.files import safe_path


def _lock(root: Path) -> dict[str, dict[str, str]]:
    with (root / "dependencies.lock.toml").open("rb") as source:
        result = tomllib.load(source)
    for package in ("agent_skills", "gh_stack"):
        if not re.fullmatch(r"[0-9a-f]{40}", result[package]["revision"]):
            raise ValueError(f"Invalid locked revision: {package}")
    return result


def _home(name: str, fallback: Path) -> Path:
    return Path(os.environ.get(name, str(fallback))).expanduser()


def _run(args: list[str]) -> str:
    result = subprocess.run(args, check=False, text=True, capture_output=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    result.check_returncode()
    return result.stdout


def _skill(target: str) -> Path:
    if target == "codex":
        return Path.home() / ".agents/skills/gh-stack/SKILL.md"
    return _home("CLAUDE_CONFIG_DIR", Path.home() / ".claude") / "skills/gh-stack/SKILL.md"


def _extension_needed(stack: dict[str, str]) -> bool:
    extension = _home("XDG_DATA_HOME", Path.home() / ".local/share") / "gh/extensions/gh-stack"
    manifest = extension / "manifest.yml"
    safe_path(manifest)
    if not extension.exists():
        return True
    if not manifest.is_file() or not {"owner: github", "name: gh-stack", "host: github.com"} <= set(
        manifest.read_text().splitlines()
    ):
        raise RuntimeError(f"Unknown extension collision: {extension}")
    fields = set(manifest.read_text().splitlines())
    if not {f"tag: {stack['release']}", "ispinned: true"} <= fields:
        raise RuntimeError(
            "Existing gh-stack extension does not match the reviewed pin; it was preserved. "
            "Save its manifest for recovery, then explicitly run native commands in the intended "
            f"environment: gh extension remove gh-stack; gh extension install {stack['repository']} "
            f"--pin {stack['release']}. Rerun the installer after native reinstallation."
        )
    return False


def _claude_registration() -> dict[str, str] | None:
    home = _home("CLAUDE_CONFIG_DIR", Path.home() / ".claude")
    registry = home / "plugins/installed_plugins.json"
    if not registry.is_file():
        return None
    entries = (
        json.loads(registry.read_text())
        .get("plugins", {})
        .get("agent-skills@addy-agent-skills", [])
    )
    installed = [entry for entry in entries if entry.get("scope") == "user"]
    if len(installed) > 1:
        raise RuntimeError("Duplicate user-scoped Claude plugin registrations")
    return installed[0] if installed else None


def _claude_current(addy: dict[str, str]) -> bool:
    installed = _claude_registration()
    if installed is None or installed.get("gitCommitSha") != addy["revision"]:
        return False
    manifest = Path(installed["installPath"]) / ".claude-plugin/plugin.json"
    return manifest.is_file() and json.loads(manifest.read_text()).get("version") == addy["version"]


def commands(root: Path, targets: set[str]) -> list[list[str]]:
    """Describe pinned native calls without executing them or modifying any destination."""
    lock = _lock(root)
    addy, stack = lock["agent_skills"], lock["gh_stack"]
    result = []
    if _extension_needed(stack):
        result.append(
            ["gh", "extension", "install", stack["repository"], "--pin", stack["release"]]
        )
    for target, agent in (("codex", "codex"), ("claude", "claude-code")):
        if target in targets:
            result.append(
                [
                    "gh",
                    "skill",
                    "install",
                    stack["repository"],
                    "gh-stack",
                    "--agent",
                    agent,
                    "--scope",
                    "user",
                    "--pin",
                    stack["revision"],
                    "--force",
                ]
            )
    if "codex" in targets:
        result.extend(
            [
                [
                    "codex",
                    "plugin",
                    "marketplace",
                    "add",
                    addy["repository"],
                    "--ref",
                    addy["revision"],
                ],
                ["codex", "plugin", "add", "agent-skills@agent-skills"],
            ]
        )
    if "claude" in targets:
        result.append(["claude", "plugin", "marketplace", "add", addy["repository"]])
        if not _claude_current(addy):
            if _claude_registration():
                result.append(
                    [
                        "claude",
                        "plugin",
                        "uninstall",
                        "agent-skills@addy-agent-skills",
                        "--scope",
                        "user",
                        "--keep-data",
                    ]
                )
            result.append(
                [
                    "claude",
                    "plugin",
                    "install",
                    "agent-skills@addy-agent-skills",
                    "--scope",
                    "user",
                ]
            )
    packages = [lock["context7"]]
    if "claude" in targets:
        packages.append(lock["ccstatusline"])
    result.append(
        ["npm", "install", "--global", *[f"{p['package']}@{p['version']}" for p in packages]]
    )
    return result


def preflight(root: Path, targets: set[str]) -> None:
    """Reject absent prerequisites, invalid pins and unrelated skill collisions before linking."""
    if not targets or not targets <= {"codex", "claude"}:
        raise ValueError("Select codex, claude, or both")
    lock = _lock(root)
    for name in {"git", "gh", "npm", *targets}:
        if shutil.which(name) is None:
            raise RuntimeError(f"Required native installer not found: {name}")
    _run(["gh", "skill", "install", "--help"])
    stack = lock["gh_stack"]
    reference = _run(
        [
            "gh",
            "api",
            f"repos/{stack['repository']}/git/ref/tags/{stack['release']}",
            "--jq",
            ".object.sha",
        ]
    ).strip()
    if reference != stack["revision"]:
        raise RuntimeError("gh-stack release and skill revision pairing changed")
    _extension_needed(stack)
    if "claude" in targets and not _claude_current(lock["agent_skills"]):
        addy = lock["agent_skills"]
        current = _run(["git", "ls-remote", f"https://github.com/{addy['repository']}.git", "HEAD"])
        if not current.split() or current.split()[0] != addy["revision"]:
            raise RuntimeError(
                "Claude's upstream plugin source moved from the reviewed revision. "
                "Review the new version and update dependencies.lock.toml before installing."
            )
    for target in targets:
        skill = _skill(target)
        safe_path(skill)
        if (
            skill.exists()
            and "github-repo: https://github.com/github/gh-stack" not in skill.read_text()
            and hashlib.sha256(skill.read_bytes()).hexdigest()
            != lock["gh_stack"]["legacy_skill_sha256"]
        ):
            raise RuntimeError(f"Unknown skill collision: {skill}")
        if skill.parent.is_symlink() or skill.is_symlink():
            raise RuntimeError(f"Native installer cannot replace a linked skill: {skill}")


def verify(root: Path, targets: set[str]) -> None:
    """Verify native package versions, registration revisions and skill provenance."""
    lock = _lock(root)
    addy, stack = lock["agent_skills"], lock["gh_stack"]
    extension_root = _home("XDG_DATA_HOME", Path.home() / ".local/share") / "gh/extensions/gh-stack"
    manifest = (extension_root / "manifest.yml").read_text()
    for field in ("owner: github", "name: gh-stack", f"tag: {stack['release']}", "ispinned: true"):
        if field not in manifest.splitlines():
            raise RuntimeError(f"gh-stack extension registration mismatch: {field}")
    if (
        _run(["gh", "stack", "--version"]).strip()
        != f"gh stack version {stack['release'].removeprefix('v')}"
    ):
        raise RuntimeError("gh-stack executable version mismatch")
    for target in targets:
        text = _skill(target).read_text()
        for field in (
            f"github-pinned: {stack['revision']}",
            "github-repo: https://github.com/github/gh-stack",
        ):
            if field not in text:
                raise RuntimeError(f"gh-stack {target} provenance mismatch: {field}")
        if target == "claude":
            home = _home("CLAUDE_CONFIG_DIR", Path.home() / ".claude")
            registry = json.loads((home / "plugins/installed_plugins.json").read_text())["plugins"]
            entries = registry["agent-skills@addy-agent-skills"]
            installed = [entry for entry in entries if entry["scope"] == "user"]
            if len(installed) != 1 or installed[0].get("gitCommitSha") != addy["revision"]:
                raise RuntimeError(
                    "Claude plugin registration revision mismatch; native update can retain a stale "
                    "gitCommitSha. The installed package was preserved. Reinstall agent-skills "
                    "through Claude's native plugin installer before rerunning."
                )
            package = Path(installed[0]["installPath"])
            settings = json.loads((home / "settings.json").read_text())
            expected_source = {"source": "github", "repo": addy["repository"]}
            marketplaces = json.loads((home / "plugins/known_marketplaces.json").read_text())
            if marketplaces.get("addy-agent-skills", {}).get("source") != expected_source:
                raise RuntimeError("Claude marketplace registry source differs from upstream")
            declared = settings.get("extraKnownMarketplaces", {}).get("addy-agent-skills", {})
            if declared.get("source") != expected_source:
                raise RuntimeError("Claude marketplace settings and registry disagree")
            enabled = settings.get("enabledPlugins", {})
            if enabled.get("agent-skills@addy-agent-skills") is not True:
                raise RuntimeError("Claude plugin is not enabled")
        else:
            home = _home("CODEX_HOME", Path.home() / ".codex")
            with (home / "config.toml").open("rb") as source:
                config = tomllib.load(source)
            marketplace = config.get("marketplaces", {}).get("agent-skills", {})
            if (
                marketplace.get("ref") != addy["revision"]
                or marketplace.get("source") != f"https://github.com/{addy['repository']}.git"
            ):
                raise RuntimeError("Codex marketplace revision mismatch")
            enabled = config.get("plugins", {})
            if enabled.get("agent-skills@agent-skills", {}).get("enabled") is not True:
                raise RuntimeError("Codex plugin is not enabled")
            package = home / "plugins/cache/agent-skills/agent-skills" / addy["version"]
        active = [
            key
            for key, value in enabled.items()
            if key.startswith("agent-skills@")
            and (value.get("enabled", False) if isinstance(value, dict) else value)
        ]
        if len(active) != 1:
            raise RuntimeError(f"Duplicate active agent-skills packages: {active}")
        plugin_manifest = package / (
            ".claude-plugin/plugin.json" if target == "claude" else "plugin.json"
        )
        if json.loads(plugin_manifest.read_text()).get("version") != addy["version"]:
            raise RuntimeError(f"{target} installed Addy version differs from dependency lock")
        if not (package / "skills/using-agent-skills/SKILL.md").is_file():
            raise RuntimeError(f"{target} installed Addy package is incomplete")
    for name in ("context7", "ccstatusline") if "claude" in targets else ("context7",):
        dependency = lock[name]
        if _run([dependency["package"], "--version"]).strip() != dependency["version"]:
            raise RuntimeError(f"Native package version mismatch: {name}")


def _snapshot() -> None:
    base = _home("XDG_DATA_HOME", Path.home() / ".local/share") / "harness/backups/native"
    safe_path(base / "entry")
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = Path(tempfile.mkdtemp(prefix="registration-", dir=base))
    homes = {
        "claude": _home("CLAUDE_CONFIG_DIR", Path.home() / ".claude"),
        "codex": _home("CODEX_HOME", Path.home() / ".codex"),
    }
    for name, home in homes.items():
        for relative in (
            "plugins/installed_plugins.json",
            "plugins/known_marketplaces.json",
            "config.toml",
            "settings.json",
        ):
            source = home / relative
            if source.is_file():
                target = backup / name / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
    for client in ("codex", "claude"):
        skill = _skill(client)
        if skill.is_file():
            target = backup / client / "skills/gh-stack/SKILL.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(skill.read_bytes())
    extension = (
        _home("XDG_DATA_HOME", Path.home() / ".local/share") / "gh/extensions/gh-stack/manifest.yml"
    )
    if extension.is_file():
        target = backup / "gh-stack/manifest.yml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(extension.read_bytes())
    print(f"Native registration recovery snapshot: {backup}")


def install(
    root: Path, targets: set[str], after_operation: Callable[[], None] | None = None
) -> None:
    """Run guarded native operations; treat scoped Claude reinstallation as one recoverable pair."""
    preflight(root, targets)
    _snapshot()
    pending = iter(commands(root, targets))
    for args in pending:
        try:
            _run(args)
            if args[:3] == ["claude", "plugin", "uninstall"]:
                _run(next(pending))
        finally:
            if after_operation is not None:
                after_operation()
    verify(root, targets)
