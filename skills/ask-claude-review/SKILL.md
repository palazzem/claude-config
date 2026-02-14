---
name: ask-claude-review
description: Use when code changes are ready for review, after completing a feature or bugfix, before merging or committing - covers code quality, tests, and conventions
---

# Reviewing Code Changes

## Overview

Dispatch **7 parallel subagents**, each focused on a single review aspect, for deep specialized feedback. Present findings in a structured table with scores.

**Core principle:** One reviewer per concern. Parallel execution. Structured output.

## Process

### Step 1: Identify Changed Files

Use `git diff main --name-only` (or appropriate base). Read changed files to provide context to reviewers.

### Step 2: Dispatch 7 Parallel Reviewer Subagents

Launch **all 7 in a single message** using the Task tool with `feature-dev:code-reviewer` type. Each gets: changed file contents, the diff, and ONE focused mandate.

**IMPORTANT:** All 7 MUST be dispatched in **one message** with 7 parallel Task calls. Never sequentially.

#### Review Mandates

Each subagent reviews ONLY its focus area. Score 1-5 with file:line references.

**1. DRY Principles**
> Duplicated logic, repeated patterns that should be extracted, copy-pasted code with minor variations, similar structures that could share a common abstraction.

**2. Dead Code Removal**
> Unused imports, unreachable code paths, variables assigned but never read, functions defined but never called, commented-out code blocks left behind.

**3. Comment Quality**
> Comments must explain "why" never "what", must be on their own line (never inline at end of a code line), remove meaningless comments that restate the code.

**4. Implementation Quality**
> Incorrect logic, missing error handling at system boundaries, security issues (OWASP top 10), poor naming, missing type annotations, violations of project conventions.

**5. Test Quality**
> Tests must focus on behavior not implementation, no duplicate tests covering the same behavior, don't verify library behavior (only our code), adequate coverage, clear test names.

**6. No Workarounds**
> Linting rules disabled or suppressed without justification, tests skipped without reason, coverage exclusions hiding untested code, pre-commit or CI checks bypassed, any code that exists solely to satisfy a linter or build rather than fixing the underlying issue.

**7. Performance Implications**
> Unnecessary allocations in hot paths, O(n^2) or worse algorithms where better alternatives exist, missing pagination on unbounded queries, synchronous blocking where async is available, N+1 query patterns, large data structures copied instead of referenced, missing caching for repeated expensive operations, unbatched I/O calls in loops.

### Step 3: Present Results

After all 7 complete, build this **exact table**:

```
| # | Review Area            | Score | Key Findings Summary           | Handle? |
|---|------------------------|-------|---------------------------------|---------|
| 1 | DRY Principles         | 4/5   | Minor duplication in validators | Yes     |
| 2 | Dead Code Removal      | 5/5   | Clean, no unused code           | No      |
| 3 | Comment Quality        | 3/5   | 2 inline comments, 1 "what"    | Yes     |
| 4 | Implementation Quality | 4/5   | Missing docstring on public API | Yes     |
| 5 | Test Quality           | 4/5   | Duplicate assertion in test_foo | Optional|
| 6 | No Workarounds         | 5/5   | No workarounds detected         | No      |
| 7 | Performance            | 4/5   | N+1 query in user loader       | Yes     |
```

**Handle? values:** `Yes` (should fix), `No` (no issues), `Optional` (minor, up to user).

Below the table, provide **detailed findings** for areas scoring below 5/5, with file:line references.

### Step 4: Ask the User

> "Which findings would you like me to address? You can select by number (e.g., 1, 3, 4) or say 'all'."

Wait for the user's response before making any changes.

## Red Flags

- Do NOT run a single monolithic review covering all aspects
- Do NOT run reviewers sequentially (they are independent)
- Do NOT skip any of the 7 review areas (include 5/5 areas in the table)
- Do NOT auto-fix findings without asking the user first
- Do NOT fabricate scores — every score must come from a subagent
