"""Private durable event journal; the Bash/jq reader remains authoritative."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def safe_path(path: Path) -> None:
    """Reject a state path or ancestor that redirects writes through a symlink."""
    for entry in (path.absolute(), *path.absolute().parents):
        if entry.is_symlink():
            raise ValueError(f"unsafe journal symlink: {entry}")


class Journal:
    """Hold an OS ownership lock while reading, recording, or handling a PR."""

    def __init__(self, path: Path, identity: str, owner_pid: int | None = None) -> None:
        """Open a private journal bound to an immutable repository/PR identity."""
        safe_path(path)
        safe_path(path.with_suffix(".lock"))
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = path
        lock_fd = os.open(path.with_suffix(".lock"), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        self.lock = os.fdopen(lock_fd, "a+")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise RuntimeError("another shepherd owns this PR") from None
        try:
            self.data: dict[str, Any] = (
                json.loads(path.read_text())
                if path.exists()
                else {"identity": identity, "watermark": None, "pending": {}, "handled": {}}
            )
            owner_pid = os.getpid() if owner_pid is None else owner_pid
            if owner_pid <= 0:
                raise ValueError("owner PID must be positive")
            os.kill(owner_pid, 0)
            previous_owner = self.data.get("owner_pid")
            if previous_owner and previous_owner != owner_pid:
                try:
                    os.kill(previous_owner, 0)
                except ProcessLookupError:
                    pass
                else:
                    raise RuntimeError("another live session owns this journal")
            self.data["owner_pid"] = owner_pid
            if self.data["identity"] != identity:
                raise ValueError("journal PR identity mismatch")
            self.save()
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        """Release ownership; process exit also releases the kernel lock."""
        self.lock.close()

    def release(self) -> None:
        """Make an explicit handoff resumable without discarding pending work or watermark."""
        self.data["owner_pid"] = None
        self.save()

    def save(self) -> None:
        """Atomically persist pending events together with their watermark."""
        safe_path(self.path)
        fd, temporary_name = tempfile.mkstemp(
            prefix=self.path.name + ".", suffix=".tmp", dir=self.path.parent
        )
        temporary = Path(temporary_name)
        with os.fdopen(fd, "w") as stream:
            json.dump(self.data, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)

    def ingest(self, lines: str) -> None:
        """Record a complete reader pass before exposing events for handling."""
        records = [json.loads(line) for line in lines.splitlines() if line]
        if not records or "event" in records[-1]:
            raise ValueError("missing watermark; reader output is incomplete")
        watermark = records.pop()
        required = {"comment", "review", "reply", "merge", "ci", "state", "head"}
        if set(watermark) not in (required, required | {"seen"}):
            raise ValueError("invalid watermark")
        self.data["sequence"] = self.data.get("sequence", 0) + 1
        for event in records:
            # State events must recur after transitions, even if the event body is identical.
            material = {"event": event, "sequence": self.data["sequence"]}
            if "url" in event:
                material = {"event": event}
            key = hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()
            if key not in self.data["handled"]:
                self.data["pending"].setdefault(
                    key,
                    {"event": event, "phase": "handling" if event.get("reconcile") else "pending"},
                )
        self.data["watermark"] = watermark
        self.save()

    def start(self, key: str) -> None:
        """Persist intent before effects; interrupted handling requires reconciliation."""
        self.data["pending"][key]["phase"] = "handling"
        self.save()

    def complete(self, key: str, evidence: str) -> None:
        """Record verified effects before removing an event from the pending queue."""
        if not evidence.strip():
            raise ValueError("completion requires effect or no-action evidence")
        event = self.data["pending"].pop(key)
        self.data["handled"][key] = {"event": event["event"], "evidence": evidence}
        self.save()


def main() -> None:
    """Run one locked journal operation, including the authoritative reader."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path)
    parser.add_argument("identity", help="verified owner/repository#PR")
    parser.add_argument("action", choices=["read", "show", "start", "complete", "release"])
    parser.add_argument("value", nargs="?")
    parser.add_argument("--evidence", default="")
    parser.add_argument(
        "--owner-pid",
        type=int,
        required=True,
        help="long-lived client/session PID, not a transient shell",
    )
    args = parser.parse_args()
    journal = Journal(args.state, args.identity, args.owner_pid)
    try:
        if args.action == "read":
            if not args.value or not args.value.isdigit():
                parser.error("read requires a PR number")
            if not args.identity.endswith("#" + args.value):
                parser.error("PR number does not match identity")
            if journal.data["pending"]:
                raise RuntimeError("reconcile pending events before reading again")
            reader = str(Path(__file__).parent / "watch-pr.sh")
            watermark = journal.data["watermark"]
            command = (
                [reader, "baseline", args.value]
                if watermark is None
                else [reader, "watch", args.value, json.dumps(watermark)]
            )
            environment = dict(os.environ, GH_REPO=args.identity.rsplit("#", 1)[0])
            journal.ingest(subprocess.check_output(command, text=True, env=environment))
        elif args.action == "release":
            journal.release()
        elif args.action == "start":
            if args.value is None:
                parser.error("start requires an event key")
            journal.start(args.value)
        elif args.action == "complete":
            if args.value is None:
                parser.error("complete requires an event key")
            journal.complete(args.value, args.evidence)
        print(json.dumps(journal.data, sort_keys=True))
    finally:
        journal.close()


if __name__ == "__main__":
    main()
