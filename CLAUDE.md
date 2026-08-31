# Claude Globals

## Rules

- You must challenge my thinking, question my assumptions, and expose blind spots. If my reasoning is weak, break it down and show me why.
- Provide options only by outcome quality: correctness, security, maintainability, performance, operability. Implementation time, team size, migration or rollout costs must not be taken into consideration when ranking options. Mention risks and caveats.
- Always include the green-field option: what this would look like designed from scratch today. In that option you are allowed to extend the scope of the change and provide a refactoring before the implementation of the change.
- When you apply TDD, test our codebase and not library behavior.

## Code Quality

- Never disable linting rules.
- If existing code violates best practices, suggest a refactoring while working on a task. Never use existing code as your quality baseline for consistency if a refactor improves the end result.
- Warnings must always be addressed. Compiler warnings, linter warnings, test-runner warnings, deprecation notices, and build warnings are actionable findings, not background noise. Addressing a warning means fixing its cause. Where feasible, promote warnings to errors project-wide.

## Comments

- Default: write no comment. Add one only when removing it would leave a future maintainer confused about a non-obvious WHY (hidden constraint, subtle invariant, workaround). If it restates the code, drop it.
- When a comment is warranted, explain WHY, never WHAT. Always on its own line, never inline.

## Documentation

- Architecture documents, ADRs, long-lived READMEs and design docs describe the system at the conceptual level: responsibilities, boundaries, data flow, invariants, and the reasoning behind a decision. Never file paths, directory layouts, class or function names, or code snippets.
- Name what is stable: concepts, architectural roles, contracts, protocols, external systems. Do not name what rots: the files, symbols, and structure that currently implement them. Code is the source of truth for the implementation; documentation explains the concept and the overview.

## Review Workflow

- Developers review and merge code changes. Never merge, close, or approve a PR autonomously.
