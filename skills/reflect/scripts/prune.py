"""Prune explicitly selected Claude memories only after verified deployment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    """Return a file's SHA-256 for comparison with the private selection manifest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def physical(path: Path) -> Path:
    """Reject symlinks in every ancestor, including a supplied memory root."""
    absolute = path.absolute()
    for part in (absolute, *absolute.parents):
        if part.is_symlink():
            raise ValueError(f"unsafe symlink traversal: {part}")
    return absolute.resolve()


def memory_path(root: Path, relative: str) -> Path:
    """Resolve exactly a project/memory/file.md below the physical memory root."""
    pieces = relative.split("/")
    if (
        len(pieces) != 3
        or pieces[1] != "memory"
        or any(piece in ("", ".", "..") for piece in pieces)
        or not pieces[2].endswith(".md")
        or pieces[2] == "MEMORY.md"
    ):
        raise ValueError("invalid memory path")
    path = physical(root / relative)
    if not path.is_relative_to(root):
        raise ValueError("memory escapes root")
    physical(path.parent / "MEMORY.md")
    return path


def git(checkout: Path, *args: str) -> str:
    """Run a read-only Git query against the verified installation checkout."""
    return subprocess.check_output(["git", "-C", str(checkout), *args], text=True).strip()


def deployment(manifest: dict[str, Any], receipt: dict[str, Any]) -> None:
    """Verify merged ancestry, tracked links and fresh native-discovery evidence."""
    checkout = physical(Path(receipt["checkout"]))
    remote = git(checkout, "remote", "get-url", "origin")
    for prefix in ("git@github.com:", "https://github.com/", "ssh://git@github.com/"):
        if remote.startswith(prefix):
            remote = remote.removeprefix(prefix).removesuffix(".git").rstrip("/")
            break
    if remote.casefold() != manifest["repository"].casefold():
        raise ValueError("installation repository differs from promotion repository")
    revision = receipt["revision"]
    if git(checkout, "branch", "--show-current") != "install/local":
        raise ValueError("receipt does not identify the stable installation branch")
    if git(checkout, "rev-parse", "HEAD") != revision:
        raise ValueError("active installation revision differs from receipt")
    if git(checkout, "status", "--porcelain"):
        raise ValueError("active installation is dirty")
    git(checkout, "merge-base", "--is-ancestor", manifest["merge_commit"], revision)
    if not manifest["targets"] or set(manifest["targets"]) - set(receipt["targets"]):
        raise ValueError("selected target not installed")
    if not set(manifest["targets"]) <= {"codex", "claude"}:
        raise ValueError("unknown native deployment target")
    for target in manifest["targets"]:
        proof = manifest["deployment"][target]
        if (
            proof["revision"] != revision
            or not proof["discovery_command"]
            or not proof["discovery_output_sha256"]
        ):
            raise ValueError("native discovery proof missing or stale")
        output = Path(proof["discovery_output"])
        if digest(output) != proof["discovery_output_sha256"]:
            raise ValueError("native discovery evidence changed")
        # Evidence is recorded by the explicit reflect session only after a fresh client
        # confirms loading. A command exit code alone is insufficient.
        if proof["confirmed_loaded"] != target:
            raise ValueError("native target was not confirmed loaded")
        required_sources = {
            f"generated/{target}/{'AGENTS.md' if target == 'codex' else 'CLAUDE.md'}"
        }
        if target == "claude":
            required_sources.update(
                str(path.relative_to(checkout))
                for path in (checkout / "rules").glob("*.md")
                if path.name != "engineering.md"
            )
        proved_sources = {receipt["links"][destination]["source"] for destination in proof["links"]}
        if proved_sources != required_sources:
            raise ValueError("proof must cover the selected client's complete discovered rule set")
        for destination, expected_hash in proof["links"].items():
            link = Path(destination)
            owned = receipt["links"][destination]
            if owned["target"] != target:
                raise ValueError("rule link belongs to a different native target")
            physical(link.parent)
            expected = checkout / owned["source"]
            if not link.is_symlink() or link.resolve(strict=True) != expected.resolve(strict=True):
                raise ValueError("managed link missing or replaced")
            if not expected.resolve().is_relative_to(checkout):
                raise ValueError("installed target escapes checkout")
            git(checkout, "ls-files", "--error-unmatch", owned["source"])
            if digest(expected) != expected_hash:
                raise ValueError("deployed rules differ from reviewed proof")


def prune(root: Path, manifest: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    """Validate all selected hashes and indexes before performing any deletion."""
    root = physical(root)
    if (
        not root.is_dir()
        or not manifest.get("entries")
        or manifest.get("explicit_selection") is not True
    ):
        raise ValueError("missing root, manifest entries, or explicit selection")
    entries: list[tuple[str, Path]] = []
    indexes: dict[Path, str] = {}
    for entry in manifest["entries"]:
        path = memory_path(root, entry["path"])
        if path.exists() and digest(path) != entry["sha256"]:
            raise ValueError("source memory changed since selection")
        if len(entry["sha256"]) != 64:
            raise ValueError("missing selection hash")
        entries.append((entry["path"], path))
        index = path.parent / "MEMORY.md"
        if index.exists():
            indexes.setdefault(index, index.read_text())
    deleted: list[str] = []
    skipped: list[str] = []
    removed = 0
    for relative, path in entries:
        (deleted if path.exists() else skipped).append(relative)
        index = path.parent / "MEMORY.md"
        if index in indexes:
            lines = indexes[index].splitlines(keepends=True)
            retained = [line for line in lines if f"]({path.name})" not in line]
            removed += len(lines) - len(retained)
            indexes[index] = "".join(retained)
    if not dry_run:
        for _, path in entries:
            path.unlink(missing_ok=True)
        for index, body in indexes.items():
            index.write_text(body)
    return {
        "deleted": deleted,
        "skipped": skipped,
        "index_lines_removed": removed,
        "dry_run": dry_run,
    }


def main() -> None:
    """Read a private manifest and independently check PR merge and installation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--receipt",
        type=Path,
        default=Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
        / "harness/installation.json",
    )
    args = parser.parse_args()
    manifest_path = physical(args.manifest)
    if manifest_path.stat().st_mode & 0o077:
        raise ValueError("manifest must be private (chmod 600)")
    manifest = json.loads(manifest_path.read_text())
    if not args.dry_run:
        pr = json.loads(
            subprocess.check_output(
                [
                    "gh",
                    "pr",
                    "view",
                    str(manifest["pr"]),
                    "--repo",
                    manifest["repository"],
                    "--json",
                    "state,mergeCommit",
                ],
                text=True,
            )
        )
        if pr["state"] != "MERGED" or not pr.get("mergeCommit"):
            raise ValueError("promotion PR is not merged")
        manifest["merge_commit"] = pr["mergeCommit"]["oid"]
        deployment(manifest, json.loads(args.receipt.read_text()))
    root = Path(
        os.environ.get(
            "REFLECT_MEMORY_ROOT",
            str(
                Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))) / "projects"
            ),
        )
    )
    print(json.dumps(prune(root, manifest, args.dry_run)))


if __name__ == "__main__":
    main()
