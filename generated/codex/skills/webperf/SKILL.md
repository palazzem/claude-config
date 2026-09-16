---
name: webperf
description: Run the webperf development lifecycle workflow using the installed agent-skills plugin.
---

Resolve the single enabled `agent-skills` plugin through the native plugin registry and verify its revision against harness's dependencies.lock.toml. Read `.claude/commands/webperf.md` from that complete installed package, then execute its instructions and referenced skills/resources. Do not copy or patch upstream content. If the package, resource, or revision cannot be verified, stop and report the missing native dependency. Reject duplicate-name registrations rather than shadowing them. Apply the shared agent-skills overrides to all upstream paths and approvals.

Pass the user's arguments as the command's `$ARGUMENTS`. Resolve process artifacts only in this worktree's selected `.harness/work/<slug>/` or legacy `.claude/specs/<slug>/`; stop on conflicting locations. Honor prior authorization. Never commit process artifacts. Human review and merge remain mandatory.
