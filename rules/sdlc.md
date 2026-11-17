# Rule: SDLC Rules

- Every tracked write in a repository — code, docs — happens in a fresh worktree on its own branch, never in the main checkout; it reaches `main` only through a PR.
- Process artifacts (spec, plan, task list) are written in `.claude/specs/<name>/` in the main checkout, with no worktree; when the first layer is built the worktree is created and they move into it. They enter a PR only when I ask.
- A PR handed to a human is ready for review, never a draft. Draft is only for a PR still in flight that needs no human action; convert it before asking anyone to look.
- Users review and merge. Never approve, merge, or close a PR, push a tag, or push to a protected branch.
- Never draft, file, or suggest a bug report or issue to an upstream project; I ask when one is needed.
- A question I leave open is recorded in an issue, or wherever I name, never only in a process artifact.
