"""Deploy clean revisions into a stable worktree with scoped links and recovery records."""

import difflib
import fcntl
import hashlib
import json
import os
import subprocess
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from scripts.installer.files import Conflict, atomic_json, replace_link, safe_path, same_link


def git(root: Path, *arguments: str) -> str:
    """Run Git against an explicit repository, raising on failed provenance checks."""
    return subprocess.check_output(["git", "-C", str(root), *arguments], text=True).strip()


def locations(environment: dict[str, str]) -> dict[str, Path]:
    """Resolve native home overrides without conflating runtime and source directories."""
    home = Path(environment["HOME"]).absolute()
    result = {
        "codex": Path(environment.get("CODEX_HOME", str(home / ".codex"))).absolute(),
        "claude": Path(environment.get("CLAUDE_CONFIG_DIR", str(home / ".claude"))).absolute(),
        "skills": home / ".agents/skills",
        "statusline": Path(environment.get("XDG_CONFIG_HOME", str(home / ".config")))
        / "ccstatusline",
        "data": Path(environment.get("XDG_DATA_HOME", str(home / ".local/share"))) / "harness",
    }
    for path in result.values():
        safe_path(path / "entry")
    return result


def mapping(root: Path, targets: set[str], paths: dict[str, Path]) -> dict[str, str]:
    """Select individual owned native entries; reflection remains repository-local."""
    links: dict[str, str] = {}
    for client in sorted(targets):
        home = paths[client]
        instruction = "AGENTS.md" if client == "codex" else "CLAUDE.md"
        config = "config.toml" if client == "codex" else "settings.json"
        links[str(home / instruction)] = f"generated/{client}/{instruction}"
        links[str(home / config)] = f"adapters/{client}/{config}"
        for agent in sorted((root / f"generated/{client}/agents").glob("*")):
            links[str(home / "agents" / agent.name)] = str(agent.relative_to(root))
        for skill in sorted((root / f"generated/{client}/skills").iterdir()):
            if skill.name != "reflect":
                destination = paths["skills"] if client == "codex" else home / "skills"
                links[str(destination / skill.name)] = str(skill.relative_to(root))
        if client == "claude":
            for rule in sorted((root / "rules").glob("*.md")):
                if rule.name != "engineering.md":
                    links[str(home / "rules" / rule.name)] = str(rule.relative_to(root))
            links[str(paths["statusline"] / "settings.json")] = (
                "statusline/ccstatusline-config.json"
            )
    return links


def clean(root: Path) -> None:
    """Refuse dirty tracked or untracked work, retaining its diff for human review."""
    status = git(root, "status", "--porcelain")
    if status:
        raise Conflict(f"Dirty worktree {root}:\n{status}\n{git(root, 'diff')}")


def validate_source(root: Path) -> str:
    """Require a clean source and exact committed regeneration before deployment."""
    clean(root)
    subprocess.run(["python3", str(root / "scripts/render.py"), "--check"], check=True)
    return git(root, "rev-parse", "HEAD")


def validate_checkout(root: Path, checkout: Path) -> None:
    """Verify stable worktree repository identity, branch, cleanliness and physical location."""
    safe_path(checkout / "entry")
    if checkout.is_symlink():
        raise Conflict(f"Installation checkout is a symlink: {checkout}")
    if Path(git(checkout, "rev-parse", "--show-toplevel")).resolve() != checkout.resolve():
        raise Conflict("Installation checkout is not its own worktree")
    source_common = Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    target_common = Path(git(checkout, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    if source_common.resolve() != target_common.resolve():
        raise Conflict("Installation checkout belongs to a different repository")
    if git(checkout, "branch", "--show-current") != "install/local":
        raise Conflict("Installation checkout must use branch install/local")
    clean(checkout)


def directory_hash(root: Path) -> str:
    """Identify an exact reviewed legacy package without following embedded links."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise Conflict(f"Unexpected link inside adopted package: {path}")
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode() + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def inspect_links(
    root: Path, checkout: Path, links: dict[str, str], previous: dict[str, Any]
) -> None:
    """Validate every destination before any writes; only reviewed adoption hashes may replace files."""
    tracked = set(git(root, "ls-files").splitlines())
    adoption_path = root / "adapters/adoption.json"
    adoption = json.loads(adoption_path.read_text()) if adoption_path.exists() else {}
    for destination, relative in links.items():
        path, source = Path(destination), root / relative
        safe_path(path)
        if relative not in tracked and not any(item.startswith(relative + "/") for item in tracked):
            raise Conflict(f"Untracked link target: {relative}")
        if not source.exists() or not source.resolve().is_relative_to(root.resolve()):
            raise Conflict(f"Missing or escaping source: {source}")
        target = checkout / relative
        if same_link(path, target):
            if not target.exists():
                raise Conflict(f"Broken managed link: {path}")
            continue
        if path.is_symlink():
            raise Conflict(f"Unexpected link target: {path} -> {os.readlink(path)}")
        if not path.exists():
            continue
        if destination in previous.get("links", {}):
            raise Conflict(f"Managed link was replaced: {path}; retain it and reconcile source")
        if path.is_file() and source.is_file():
            current = path.read_bytes()
            digest = hashlib.sha256(current).hexdigest()
            if current == source.read_bytes() or digest in adoption.get(relative, []):
                continue
            difference = "".join(
                difflib.unified_diff(
                    current.decode(errors="replace").splitlines(True),
                    source.read_text().splitlines(True),
                    fromfile=str(path),
                    tofile=str(source),
                )
            )
            raise Conflict(
                f"Unreviewed configuration at {path}; reconcile in source first:\n{difference}"
            )
        if path.is_dir() and source.is_dir():
            if directory_hash(path) in adoption.get(relative, []):
                continue
        raise Conflict(f"Unknown collision: {path}")


@contextmanager
def ownership(data: Path) -> Iterator[None]:
    """Serialize installs with a kernel lock that releases after interruption."""
    safe_path(data / "install.lock")
    data.mkdir(parents=True, exist_ok=True)
    lock_path = data / "install.lock"
    if lock_path.is_symlink():
        raise Conflict(f"Unsafe lock: {lock_path}")
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Conflict("Another installation owns the lock") from error
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def verify_native_links(checkout: Path, links: dict[str, str], backups: Path) -> None:
    """Retain native writes; relink only byte-identical atomic replacements."""
    changed: list[str] = []
    for index, (destination, relative) in enumerate(links.items()):
        path, source = Path(destination), checkout / relative
        safe_path(path)
        if same_link(path, source):
            continue
        if path.is_file() and not path.is_symlink() and source.is_file():
            if path.read_bytes() == source.read_bytes():
                safe_path(backups / "entry")
                backups.mkdir(parents=True, exist_ok=True)
                path.rename(backups / f"native-{index}")
                replace_link(path, source)
                continue
        changed.append(destination)
    if changed:
        raise Conflict(
            "Native operation replaced managed links; changes retained: " + ", ".join(changed)
        )
    clean(checkout)


def rollback(checkout: Path, journal: dict[str, Any]) -> list[str]:
    """Restore only unchanged owned links and a clean prior revision; retain ambiguous writes."""
    conflicts: list[str] = []
    for entry in reversed(journal["changes"]):
        path = Path(entry["destination"])
        source = checkout / entry["source"]
        backup = Path(entry["backup"]) if entry["backup"] else None
        try:
            safe_path(path)
            if entry["action"] == "remove":
                if path.exists() or path.is_symlink():
                    raise Conflict(f"Changed obsolete destination: {path}")
                replace_link(path, source)
            elif same_link(path, source):
                path.unlink()
                if backup and backup.exists():
                    backup.rename(path)
            elif not path.exists() and not path.is_symlink() and backup and backup.exists():
                backup.rename(path)
            elif path.exists() or path.is_symlink():
                raise Conflict(f"New destination write preserved: {path}")
        except (OSError, Conflict) as error:
            conflicts.append(str(error))
    if journal["prior_revision"]:
        try:
            clean(checkout)
            git(checkout, "reset", "--keep", journal["prior_revision"])
        except (Conflict, subprocess.CalledProcessError) as error:
            conflicts.append(str(error))
    return conflicts


def deploy(
    root: Path,
    targets: set[str],
    environment: dict[str, str],
    dry_run: bool = False,
    native: Callable[[Path, set[str]], None] | None = None,
    validate: Callable[[Path], str] = validate_source,
) -> dict[str, Any]:
    """Inspect, link a stable clean revision, then run guarded native installers.

    Dry runs make no filesystem changes. Failures restore safely owned prior links;
    ambiguous native writes and interrupted journals remain explicit recovery conflicts.
    """
    if not targets or not targets <= {"codex", "claude"}:
        raise Conflict("Select --codex, --claude, or both")
    revision = validate(root)
    paths = locations(environment)
    source = root.resolve()
    for name, path in paths.items():
        runtime = path.resolve()
        if source.is_relative_to(runtime) or runtime.is_relative_to(source):
            raise Conflict(f"Source and runtime locations overlap: {name} {path}")
    if paths["codex"].is_relative_to(paths["claude"]) or paths["claude"].is_relative_to(
        paths["codex"]
    ):
        raise Conflict("Codex and Claude runtime homes must not overlap")
    data, checkout = paths["data"], paths["data"] / "checkout"
    receipt, journal_path = data / "installation.json", data / "pending.json"
    for state_path in (receipt, journal_path):
        safe_path(state_path)
        if state_path.is_symlink():
            raise Conflict(f"Unsafe state file: {state_path}")
    if journal_path.exists():
        raise Conflict(f"Interrupted installation: inspect {journal_path} and docs/recovery.md")
    previous = json.loads(receipt.read_text()) if receipt.exists() else {}
    if checkout.exists():
        validate_checkout(root, checkout)
        if previous and git(checkout, "rev-parse", "HEAD") != previous["revision"]:
            raise Conflict("Installation revision differs from recorded provenance")
        if previous and revision != previous["revision"] and set(previous["targets"]) - targets:
            raise Conflict("Updating the shared checkout requires all previously installed targets")
    elif previous:
        raise Conflict("Recorded installation checkout is missing")
    selected = mapping(root, targets, paths)
    inspect_links(root, checkout, selected, previous)
    desired = dict(previous.get("links", {}))
    obsolete = {}
    for destination, entry in list(desired.items()):
        if entry["target"] in targets and destination not in selected:
            if not same_link(Path(destination), checkout / entry["source"]):
                raise Conflict(f"Obsolete link changed: {destination}")
            safe_path(Path(destination))
            obsolete[destination] = entry
            del desired[destination]
    proposal = {
        "revision": revision,
        "checkout": str(checkout),
        "links": selected,
        "remove": list(obsolete),
        "targets": sorted(targets),
    }
    print(json.dumps(proposal, indent=2))
    if dry_run:
        return proposal
    with ownership(data):
        if journal_path.exists() or (
            receipt.exists() and json.loads(receipt.read_text()) != previous
        ):
            raise Conflict("Installation changed during inspection; rerun")
        inspect_links(root, checkout, selected, previous)
        prior_revision = git(checkout, "rev-parse", "HEAD") if checkout.exists() else None
        if checkout.exists():
            validate_checkout(root, checkout)
        journal: dict[str, Any] = {
            "revision": revision,
            "prior_revision": prior_revision,
            "changes": [],
            "checkout": str(checkout),
        }
        atomic_json(journal_path, journal)
        backups = data / "backups" / str(time.time_ns())
        safe_path(backups / "entry")
        committed = False
        try:
            if checkout.exists():
                git(checkout, "reset", "--keep", revision)
            else:
                git(root, "worktree", "add", "-b", "install/local", str(checkout), revision)
            for destination, entry in obsolete.items():
                journal["changes"].append(
                    {
                        "destination": destination,
                        "source": entry["source"],
                        "backup": None,
                        "action": "remove",
                    }
                )
                atomic_json(journal_path, journal)
                Path(destination).unlink()
            for index, (destination, relative) in enumerate(selected.items()):
                path, source = Path(destination), checkout / relative
                old = desired.get(destination, {})
                target = (
                    "codex"
                    if destination.startswith(str(paths["codex"]) + "/")
                    or destination.startswith(str(paths["skills"]) + "/")
                    else "claude"
                )
                backup = old.get("backup")
                if not same_link(path, source):
                    backup = str(backups / str(index)) if path.exists() else None
                    journal["changes"].append(
                        {
                            "destination": destination,
                            "source": relative,
                            "backup": backup,
                            "action": "link",
                        }
                    )
                    atomic_json(journal_path, journal)
                    if backup:
                        backups.mkdir(parents=True, exist_ok=True)
                        path.rename(backup)
                    replace_link(path, source)
                desired[destination] = {"source": relative, "backup": backup, "target": target}
            try:
                if native:
                    native(checkout, targets)
            finally:
                verify_native_links(checkout, selected, backups)
            result = {
                "revision": revision,
                "checkout": str(checkout),
                "links": desired,
                "targets": sorted(set(previous.get("targets", [])) | targets),
            }
            atomic_json(receipt, result)
            committed = True
            journal_path.unlink()
            return result
        except BaseException:
            if committed:
                journal["phase"] = "committed; journal cleanup failed"
                atomic_json(journal_path, journal)
                raise
            conflicts = rollback(checkout, journal)
            journal["recovery_conflicts"] = conflicts
            atomic_json(journal_path, journal)
            if not conflicts:
                journal_path.unlink()
            raise
