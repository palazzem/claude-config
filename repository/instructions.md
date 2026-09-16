# Maintaining harness

This repository owns shared engineering rules, portable skills, and reviewed native configuration for Codex and Claude. Runtime client homes contain credentials, sessions, memories, and unrelated packages; they are not source checkouts.

Read `rules/engineering.md`, `rules/agent-skills.md`, `rules/context7.md`, and `rules/gh-stack.md` before changing this repository. Use a fresh feature worktree and branch; publish through human-reviewed PRs. Respect existing user authorization for implementation and publication. Never merge, approve, or close a PR.

Keep new process artifacts in `.harness/work/<worktree-slug>/`, ignored by Git. Resume legacy `.claude/specs/<worktree-slug>/` work in place; stop on conflicting old/new artifacts. The overhaul's existing execution artifacts remain in that legacy directory.

Edit shared source and native metadata, then run `python3 scripts/render.py`; commit generated outputs with their inputs. `python3 scripts/render.py --check` must pass. Run `python3 -m unittest discover -s tests`, the configured lint, formatting, and type checks. Read `CONSTRAINTS.md` when present and never weaken it to pass a change. Add meaningful behavioral tests for installation, state, and recovery changes. No lint suppressions.

Keep `reflect` repository-local and explicit-only. Never install it into a user skill directory. Use synthetic memories and disposable client homes in tests. Never install this feature branch into real client homes, rename the repository, or merge as part of implementation: those are post-acceptance release steps.

The installer has only `--codex`, `--claude`, and `--dry-run`. Preserve authoritative settings, stable installation-worktree symlinks, native dependency ownership, and unrelated runtime state. Never turn it into a management CLI or merge settings per key.
