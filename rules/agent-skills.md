# Rule: agent-skills Overrides

The `agent-skills` plugin supplies the process; `CLAUDE.md` supplies the bar. This file holds every place this configuration replaces a plugin default, so the bar stays free of plugin mechanics. Wherever a plugin skill or command names a path or behaviour listed here, this file wins. Future overrides of the same kind belong here, one section per concern.

## Artifact paths

`<slug>` is the name of the worktree the session runs in: the last component of its path. Every process artifact lives under `.claude/specs/<slug>/` inside that worktree and is never staged, committed, or included in a PR.

- Spec → `.claude/specs/<slug>/spec.md`. Replaces `SPEC.md` at the repository root wherever `/spec`, `/plan`, `/build`, or `/build auto` names it. Module specs from a capability map sit alongside it as `.claude/specs/<slug>/spec-<module>.md`.
- Plan → `.claude/specs/<slug>/plan.md`. Replaces `tasks/plan.md`.
- Task list → `.claude/specs/<slug>/todo.md`. Replaces `tasks/todo.md` as the task list target.
- `tasks/` is never created or written by these commands; in `~/.claude` it is Claude Code's own state directory.

The check for an existing incomplete plan looks only at `.claude/specs/<slug>/`.

## `/build auto`

- The spec requirement is satisfied by `.claude/specs/<slug>/spec.md`. `SPEC.md`, `docs/SPEC.md`, and `spec/` are not consulted; when the file is missing, stop and tell the user to run `/spec`.
- The clean-baseline check treats uncommitted files under `.claude/specs/<slug>/` as the expected planning artifacts; anything else uncommitted stops the run.
- The plan is not committed before the first task: artifacts never enter a PR.

## Other slugs

`.claude/specs/<other-slug>/` is another agent's work in flight. Never read, overwrite, or delete it, and never count it when checking for an existing plan.
