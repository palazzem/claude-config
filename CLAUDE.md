# Conventions

Skills and plugins supply process; this file supplies the quality bar and conventions.

## SDLC Rules

- Every write in a repository — code, docs, spec, plan — happens in a fresh worktree on its own branch, never in the main checkout; it reaches `main` only through a PR.
- Process artifacts (spec, plan, task list) live in `.claude/specs/<slug>/` inside that worktree and never enter a PR.
- A PR handed to a human is ready for review, never a draft. Draft is only for a PR still in flight that needs no human action; convert it before asking anyone to look.
- Users review and merge. Never approve, merge, or close a PR, push a tag, or push to a protected branch.

## Decisions

- Rank options by outcome quality only: correctness, security, maintainability, performance, operability. Report implementation time, team size, and migration or rollout cost as caveats, never as ranking inputs.
- Always include the green-field option — what this would look like designed from scratch today, with the refactoring it implies — as a proposal. Extend scope beyond the ask only when I pick it.

## Code Quality

- Never disable a lint rule or add a suppression or exception. Exceptions are mine to grant, with an owner and an expiry.
- Warnings are findings. Fix the cause of compiler, linter, test-runner, build, and deprecation warnings; promote warnings to errors project-wide where feasible.
- Existing code is not the quality bar. When it violates best practice, improve the pattern and migrate its neighbors — or file that migration — never introduce a third way.

## Documentation

- Architecture documents, ADRs, and design docs stay conceptual: responsibilities, boundaries, data flow, invariants, and the reasoning behind decisions. Name what is stable — concepts, contracts, protocols, external systems — never files, symbols, layouts, or code.
- Operational docs — agent instructions, constraints files, runbooks, quick-starts — name what they must, and are verified in the same change that alters what they name.

## Docstrings and Comments

- Every public or exported module, class, function, and method gets a docstring stating its contract — semantics, invariants, side effects, errors, an example where it helps — never a restatement of the signature. Internal code only when non-obvious. Enforce with the linter's missing-docs rule.
- Inside bodies, no comment by default. Write one only for a non-obvious WHY (hidden constraint, subtle invariant, workaround), on its own line, never inline.
