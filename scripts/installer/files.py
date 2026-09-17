"""Filesystem contracts for scoped, recoverable symlink deployment."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class Conflict(RuntimeError):
    """Report an unsafe or ambiguous installation without discarding user state."""


def safe_path(path: Path) -> None:
    """Reject symlink ancestors, including broken links, before following a destination."""
    if not path.is_absolute():
        raise Conflict(f"Destination must be absolute: {path}")
    for parent in path.parents:
        if parent.is_symlink():
            raise Conflict(f"Unsafe destination ancestor: {parent}")
        if parent.exists() and not parent.is_dir():
            raise Conflict(f"Destination ancestor is not a directory: {parent}")


def atomic_json(path: Path, value: Any) -> None:
    """Persist private recovery metadata by atomic replacement in its existing directory."""
    safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def same_link(destination: Path, source: Path) -> bool:
    """Compare link text without hiding a broken or redirected installation target."""
    return destination.is_symlink() and Path(os.readlink(destination)) == source


def replace_link(destination: Path, source: Path) -> None:
    """Atomically publish a link after the caller has validated collision ownership."""
    safe_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".harness-link-", dir=destination.parent)
    os.close(descriptor)
    Path(temporary).unlink()
    try:
        Path(temporary).symlink_to(source, target_is_directory=source.is_dir())
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
