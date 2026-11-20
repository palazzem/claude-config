# Rule: SDLC Rules

- Every tracked write in a repository — code, docs — happens in a fresh worktree on its own branch, never in the main checkout; it reaches `main` only through a PR.
- A spec is a Claude Doc until I confirm it, then a GitHub issue labelled `spec`.
- Plans, task lists, and PR bodies are agent artifacts in `.claude/runs/<name>/`, gitignored by each repository; they enter a PR only when I ask.
- A PR handed to a human is ready for review, never a draft. Draft is only for a PR still in flight that needs no human action; convert it before asking anyone to look.
- Users review and merge. Never approve, merge, or close a PR, push a tag, or push to a protected branch.
- Never draft, file, or suggest a bug report or issue to an upstream project; I ask when one is needed.
- A question I leave open is recorded in an issue, or wherever I name, never only in a process artifact.
