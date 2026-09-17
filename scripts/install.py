"""Expose only target selection and dry-run for the shared native harness installer."""

import argparse
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    """Validate target arguments, print the native plan, and deploy or report a conflict."""
    from scripts.installer import native
    from scripts.installer.core import deploy, mapping, verify_native_links

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", action="store_true")
    parser.add_argument("--claude", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    targets = {target for target in ("codex", "claude") if getattr(args, target)}
    if not targets:
        parser.error("select --codex, --claude, or both")
    try:
        native.preflight(ROOT, targets)
        for command in native.commands(ROOT, targets):
            print("native:", shlex.join(command))

        def install_native(checkout: Path, selected: set[str]) -> None:
            from scripts.installer.core import locations

            links = mapping(checkout, selected, locations(dict(os.environ)))
            backups = checkout.parent / "backups" / f"native-links-{time.time_ns()}"
            native.install(
                checkout,
                selected,
                after_operation=lambda: verify_native_links(checkout, links, backups),
            )

        deploy(ROOT, targets, dict(os.environ), args.dry_run, install_native)
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"install: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
