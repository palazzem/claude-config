"""Portable reader and durable resume regression fixtures."""

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/shepherd/scripts"
spec = importlib.util.spec_from_file_location("shepherd_state", SCRIPTS / "state.py")
assert spec and spec.loader
state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state)


class ShepherdTests(unittest.TestCase):
    """Verify synthetic safety and recovery contracts."""

    def test_interrupted_handling_and_identity(self) -> None:
        """Interrupted handling and identity."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "state.json"
            journal = state.Journal(path, "owner/repo#1")
            with self.assertRaises(RuntimeError):
                state.Journal(path, "owner/repo#1")
            event = {"event": "COMMENT", "url": "url", "at": "2026-01-01"}
            watermark = dict(
                comment="2026-01-01",
                review="",
                reply="",
                merge="CLEAN",
                ci="OK",
                state="OPEN",
                head="old-head",
            )
            journal.ingest(json.dumps(event) + "\n" + json.dumps(watermark))
            key = next(iter(journal.data["pending"]))
            journal.start(key)
            journal.close()
            resumed = state.Journal(path, "owner/repo#1")
            self.assertEqual(resumed.data["pending"][key]["phase"], "handling")
            resumed.complete(key, "verified comment URL")
            resumed.ingest(json.dumps(event) + "\n" + json.dumps(watermark))
            self.assertFalse(resumed.data["pending"])
            resumed.close()
            with self.assertRaises(ValueError):
                state.Journal(path, "owner/repo#2")

    def test_every_connection_limit_fails_closed(self) -> None:
        """Every connection limit fails closed."""

        def connection(count: int) -> dict[str, Any]:
            return {
                "pageInfo": {"hasPreviousPage": False, "hasNextPage": False},
                "nodes": [{} for _ in range(count)],
            }

        for surface, limit in [
            ("comments", 50),
            ("reviews", 50),
            ("reviewThreads", 50),
            ("replies", 20),
            ("checks", 100),
        ]:
            with self.subTest(surface=surface):
                pr: dict[str, Any] = {
                    "comments": connection(0),
                    "reviews": connection(0),
                    "reviewThreads": connection(0),
                    "commits": {"nodes": []},
                }
                truncated = connection(limit)
                truncated["pageInfo"]["hasPreviousPage"] = True
                if surface == "replies":
                    pr["reviewThreads"]["nodes"] = [{"comments": truncated}]
                elif surface == "checks":
                    truncated["pageInfo"] = {"hasPreviousPage": False, "hasNextPage": True}
                    pr["commits"]["nodes"] = [
                        {"commit": {"statusCheckRollup": {"contexts": truncated}}}
                    ]
                else:
                    pr[surface] = truncated
                result = subprocess.run(
                    ["jq", "-e", "-f", str(SCRIPTS / "jq/complete.jq")],
                    input=json.dumps(pr),
                    text=True,
                    capture_output=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(result.stdout)

    def test_markers_and_edits(self) -> None:
        """Markers and edits."""
        pr: dict[str, Any] = {
            "comments": {
                "nodes": [
                    dict(
                        body=body,
                        updatedAt="2026-01-02",
                        url=str(i),
                        author={"login": "a"},
                        authorAssociation="OWNER",
                    )
                    for i, body in enumerate(
                        ["<!-- claude -->\nreply", "<!-- codex -->\nreply", "edited human reply"]
                    )
                ]
            },
            "reviews": {"nodes": []},
            "reviewThreads": {"nodes": []},
        }
        result = subprocess.check_output(
            [
                "jq",
                "-L",
                str(SCRIPTS / "jq"),
                "--arg",
                "marker",
                "<!-- claude -->",
                "--arg",
                "comment",
                "2026-01-01",
                "--arg",
                "review",
                "",
                "--arg",
                "reply",
                "",
                "-c",
                "-f",
                str(SCRIPTS / "jq/events.jq"),
            ],
            input=json.dumps(pr),
            text=True,
        )
        self.assertEqual(json.loads(result)["url"], "2")

    def test_state_transitions_and_terminal(self) -> None:
        """State transitions and terminal."""

        def run_filter(name: str, pr: dict[str, Any]) -> str:
            return subprocess.check_output(
                ["jq", "-L", str(SCRIPTS / "jq"), "-r", "-f", str(SCRIPTS / "jq" / name)],
                input=json.dumps(pr),
                text=True,
            ).strip()

        pr: dict[str, Any] = {
            "state": "OPEN",
            "mergeStateStatus": "CLEAN",
            "baseRef": {"compare": {"behindBy": 1}},
            "commits": {
                "nodes": [
                    {
                        "commit": {
                            "statusCheckRollup": {
                                "contexts": {
                                    "nodes": [
                                        {
                                            "__typename": "CheckRun",
                                            "status": "COMPLETED",
                                            "conclusion": "FAILURE",
                                        }
                                    ]
                                }
                            }
                        }
                    }
                ]
            },
        }
        self.assertEqual(run_filter("pass.jq", pr), "OPEN BEHIND FAILED UNKNOWN")
        pr["mergeStateStatus"] = "DIRTY"
        pr["commits"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"][0][
            "conclusion"
        ] = "SUCCESS"
        self.assertEqual(run_filter("pass.jq", pr), "OPEN DIRTY OK UNKNOWN")
        pr["state"] = "MERGED"
        self.assertTrue(run_filter("pass.jq", pr).startswith("MERGED"))

    def test_live_ownership_and_dead_owner_transfer(self) -> None:
        """Live ownership and dead owner transfer."""
        import os
        import sys

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "state.json"
            owner = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            try:
                journal = state.Journal(path, "owner/repo#1", owner.pid)
                journal.close()
                with self.assertRaises(RuntimeError):
                    state.Journal(path, "owner/repo#1", os.getpid())
                owner.terminate()
                owner.wait()
                journal = state.Journal(path, "owner/repo#1", os.getpid())
                journal.close()
            finally:
                if owner.poll() is None:
                    owner.terminate()
                    owner.wait()

    def test_initial_backlog_edited_replies_and_approval(self) -> None:
        """Read backlog and edited submitted replies while excluding pending replies."""
        activity = dict(
            body="human",
            updatedAt="2026-01-02",
            url="reply",
            author={"login": "a"},
            authorAssociation="OWNER",
        )
        pr: dict[str, Any] = {
            "comments": {"nodes": [dict(activity, url="comment")]},
            "reviews": {"nodes": [dict(activity, body="", state="APPROVED", url="approval")]},
            "reviewThreads": {
                "nodes": [
                    {
                        "comments": {
                            "nodes": [
                                dict(activity, pullRequestReview={"state": "COMMENTED"}),
                                dict(
                                    activity, url="pending", pullRequestReview={"state": "PENDING"}
                                ),
                            ]
                        }
                    }
                ]
            },
        }
        command = [
            "jq",
            "-L",
            str(SCRIPTS / "jq"),
            "--arg",
            "marker",
            "<!-- claude -->",
            "--arg",
            "comment",
            "1970-01-01",
            "--arg",
            "review",
            "1970-01-01",
            "--arg",
            "reply",
            "2026-01-01",
            "-c",
            "-f",
            str(SCRIPTS / "jq/events.jq"),
        ]
        output = subprocess.check_output(command, input=json.dumps(pr), text=True)
        self.assertEqual(
            [json.loads(line)["event"] for line in output.splitlines()],
            ["COMMENT", "REVIEW", "THREAD_REPLY"],
        )

    def test_repeated_ci_failure_has_distinct_journal_event(self) -> None:
        """A later failure transition remains actionable after a prior one completed."""
        with tempfile.TemporaryDirectory() as directory:
            journal = state.Journal(Path(directory).resolve() / "state.json", "owner/repo#1")
            watermark = dict(
                comment="",
                review="",
                reply="",
                merge="CLEAN",
                ci="FAILED",
                state="OPEN",
                head="old-head",
            )
            output = json.dumps({"event": "CI_FAILED"}) + "\n" + json.dumps(watermark)
            journal.ingest(output)
            first = next(iter(journal.data["pending"]))
            journal.complete(first, "rerun succeeded")
            journal.ingest(output)
            second = next(iter(journal.data["pending"]))
            self.assertNotEqual(first, second)
            journal.close()

    def test_journal_symlinks_and_stale_temporary_path(self) -> None:
        """Reject redirected state and locks without following predictable temporary links."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            external = root / "external"
            external.write_text("preserve")
            for suffix in (".json", ".lock"):
                link = root / ("state" + suffix)
                link.symlink_to(external)
                with self.assertRaises(ValueError):
                    state.Journal(root / "state.json", "owner/repo#1")
                link.unlink()
            redirected = root / "redirected"
            redirected.symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                state.Journal(redirected / "state.json", "owner/repo#1")
            (root / "state.tmp").symlink_to(external)
            journal = state.Journal(root / "state.json", "owner/repo#1")
            journal.close()
            self.assertEqual(external.read_text(), "preserve")

    def test_linked_reader_runs_from_unrelated_project(self) -> None:
        """A discovered package resolves all GraphQL/jq helpers through native symlinks."""
        import os

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            package = root / "linked-skill"
            package.symlink_to(SCRIPTS.parent, target_is_directory=True)
            unrelated = root / "unrelated"
            unrelated.mkdir()
            binary = root / "bin"
            binary.mkdir()
            complete = {"nodes": [], "pageInfo": {"hasPreviousPage": False, "hasNextPage": False}}
            response = {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "state": "MERGED",
                            "mergeStateStatus": "CLEAN",
                            "comments": complete,
                            "reviews": complete,
                            "reviewThreads": complete,
                            "commits": {"nodes": []},
                        }
                    }
                }
            }
            fixture = root / "response.json"
            fixture.write_text(json.dumps(response))
            executable = binary / "gh"
            executable.write_text('#!/usr/bin/env bash\ncat "$RESPONSE_FIXTURE"\n')
            executable.chmod(0o755)
            environment = dict(
                os.environ,
                PATH=str(binary) + os.pathsep + os.environ["PATH"],
                RESPONSE_FIXTURE=str(fixture),
            )
            output = subprocess.check_output(
                [str(package / "scripts/watch-pr.sh"), "baseline", "1"],
                cwd=unrelated,
                env=environment,
                text=True,
            )
            self.assertEqual(json.loads(output.splitlines()[0]), {"event": "MERGED"})
            self.assertEqual(json.loads(output.splitlines()[1])["state"], "MERGED")

    def test_failure_on_new_head_and_repeated_transition(self) -> None:
        """A failed new head and pending-to-failed rerun both wake the watcher."""
        import os

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            binary = root / "bin"
            binary.mkdir()
            executable = binary / "gh"
            executable.write_text("""#!/usr/bin/env bash
n=0
[ ! -f "$FIXTURE_ROOT/count" ] || n=$(cat "$FIXTURE_ROOT/count")
n=$((n + 1))
printf '%s' "$n" > "$FIXTURE_ROOT/count"
cat "$FIXTURE_ROOT/response-$n.json"
""")
            executable.chmod(0o755)
            watermark = dict(
                comment="1970-01-01T00:00:00Z",
                review="1970-01-01T00:00:00Z",
                reply="1970-01-01T00:00:00Z",
                merge="CLEAN",
                ci="FAILED",
                state="OPEN",
                head="head-a",
            )

            def response(head: str, status: str) -> dict[str, Any]:
                complete = {
                    "nodes": [],
                    "pageInfo": {"hasPreviousPage": False, "hasNextPage": False},
                }
                return {
                    "data": {
                        "repository": {
                            "pullRequest": {
                                "state": "OPEN",
                                "headRefOid": head,
                                "mergeStateStatus": "CLEAN",
                                "comments": complete,
                                "reviews": complete,
                                "reviewThreads": complete,
                                "commits": {
                                    "nodes": [
                                        {
                                            "commit": {
                                                "statusCheckRollup": {
                                                    "contexts": {
                                                        "pageInfo": complete["pageInfo"],
                                                        "nodes": [
                                                            {
                                                                "__typename": "CheckRun",
                                                                "status": status,
                                                                "conclusion": "FAILURE",
                                                            }
                                                        ],
                                                    }
                                                }
                                            }
                                        }
                                    ]
                                },
                            }
                        }
                    }
                }

            environment = dict(
                os.environ,
                PATH=str(binary) + os.pathsep + os.environ["PATH"],
                FIXTURE_ROOT=str(root),
                WATCH_PR_INTERVAL="0",
                WATCH_PR_MAX_FAILURES="1",
            )
            for reads in (
                [response("head-b", "COMPLETED")],
                [response("head-a", "IN_PROGRESS"), response("head-a", "COMPLETED")],
            ):
                (root / "count").unlink(missing_ok=True)
                for index, payload in enumerate(reads, 1):
                    (root / f"response-{index}.json").write_text(json.dumps(payload))
                output = subprocess.check_output(
                    [str(SCRIPTS / "watch-pr.sh"), "watch", "1", json.dumps(watermark)],
                    env=environment,
                    text=True,
                    timeout=5,
                    stderr=subprocess.PIPE,
                )
                self.assertEqual(json.loads(output.splitlines()[0]), {"event": "CI_FAILED"})
                self.assertEqual(
                    json.loads(output.splitlines()[1])["head"],
                    reads[-1]["data"]["repository"]["pullRequest"]["headRefOid"],
                )
