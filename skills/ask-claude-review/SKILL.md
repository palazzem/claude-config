---
name: ask-claude-review
description: Use when code changes are ready for review, after completing a feature or bugfix, before merging or committing - covers code quality, tests, and conventions
---

# Reviewing Code Changes

## Overview

Dispatch **7 parallel subagents**, each focused on a single review aspect, for deep specialized feedback. Present findings in a structured table with scores.

**Core principle:** One reviewer per concern. Parallel execution. Structured output.

## Process

### Step 0: Prepare for Review

Before dispatching reviewers:

1. **Commit all changes.** Stage and commit any uncommitted work so reviewers can inspect a clean diff.
2. **Determine the base branch.** Identify the branch this work will be merged into (e.g., `main`, `master`, `develop`).
3. **Pass the base branch** to each reviewer via the prompt template below.

### Step 1: Dispatch 7 Parallel Reviewer Subagents

Launch **all 7 in a single message** using the Task tool with `code-reviewer` agent type. Each gets ONE focused mandate. Subagents autonomously retrieve the diff and read files — do NOT gather context for them.

**IMPORTANT:** All 7 MUST be dispatched in parallel, never sequentially. Do NOT set the `model` parameter, the `code-reviewer` agent defines its own model.

#### Prompt Template

Each subagent receives the following prompt. Replace `{MANDATE_NAME}`, `{MANDATE_DESCRIPTION}`, and `{BASE_BRANCH}` with the appropriate values.

```
You are reviewing code changes for **{MANDATE_NAME}**.

**Your focus:** {MANDATE_DESCRIPTION}

**Workflow:**
1. Run `git diff {BASE_BRANCH}...HEAD` to see all changes on this branch relative to the base.
2. Review ONLY changed files through the lens of your assigned focus area.
3. Score and report findings using the format below.

**Scoring (strict calibration):**
- **5/5 Exemplary**: No issues of any kind. The code is a model of best practices for this area.
- **4/5 Clean**: No warnings or critical issues. 1-2 minor suggestions at most.
- **3/5 Acceptable**: Minor warnings that should be addressed, but nothing blocking.
- **2/5 Concerning**: Critical issues or multiple warnings requiring attention.
- **1/5 Failing**: Fundamental problems requiring significant rework.

**Output format:**

## {MANDATE_NAME}: X/5

### Findings
- [Critical|Warning|Suggestion] `file:line` — Description. Fix: suggested fix.

### Summary
X critical, Y warnings, Z suggestions.

If no issues found, output:

## {MANDATE_NAME}: 5/5

No issues found. The changes are exemplary for this review area.
```

#### Review Mandates

Each subagent reviews ONLY its focus area.

**1. DRY Principles**
> Duplicated logic, repeated patterns that should be extracted, copy-pasted code with minor variations, similar structures that could share a common abstraction. Two or more occurrences of the same pattern warrant extraction.

**2. Dead Code Removal**
> Unused imports, unreachable code paths, variables assigned but never read, functions defined but never called, commented-out code blocks left behind.

**3. Comment Quality**
> Comments must explain "why" never "what". Must be on their own line, never inline at end of a code line. Remove meaningless comments that restate the code. Python docstrings must follow Google style guidelines.

**4. Implementation Quality**
> Incorrect logic, missing error handling at system boundaries, security issues (OWASP top 10), poor naming, missing type annotations, violations of language best practices. Imports must be at the top of the file, never inline.

**5. Test Quality**
> Tests must focus on behavior not implementation. No duplicate tests covering the same behavior. Don't verify library behavior, only our code. Adequate coverage for new code. Clear, descriptive test names.

**6. No Workarounds**
> Linting rules disabled or suppressed, tests skipped without justification, coverage exclusions hiding untested code, pre-commit or CI checks bypassed, code that exists solely to satisfy a linter or build rather than fixing the underlying issue.

**7. Performance Implications**
> Unnecessary allocations in hot paths, O(n^2) or worse where better alternatives exist, missing pagination on unbounded queries, synchronous blocking where async is available, N+1 query patterns, large data structures copied instead of referenced, missing caching for repeated expensive operations, unbatched I/O calls in loops.

### Step 2: Persist and Present Results

After all 7 complete:

**1. Write the full review** to `$TMPDIR/code-review-<timestamp>.md` containing the table and all detailed findings. This ensures the review survives context compacts.

**2. Present the table** to the user:

```
| # | Review Area            | Score | Key Findings Summary           | Handle? |
|---|------------------------|-------|---------------------------------|---------|
| 1 | DRY Principles         | 4/5   | Minor duplication in validators | Optional|
| 2 | Dead Code Removal      | 5/5   | No issues found                 | No      |
| 3 | Comment Quality        | 3/5   | 2 inline comments, 1 "what"    | Yes     |
| 4 | Implementation Quality | 4/5   | Missing docstring on public API | Optional|
| 5 | Test Quality           | 4/5   | Duplicate assertion in test_foo | Optional|
| 6 | No Workarounds         | 5/5   | No workarounds detected         | No      |
| 7 | Performance            | 2/5   | N+1 query in user loader       | Yes     |
```

**Handle? rules (deterministic, based on score):**
- **Score 5/5** → `No`
- **Score 4/5** → `Optional`
- **Score 1-3/5** → `Yes`

**3. Present detailed findings** for areas scoring below 5/5, grouped by review area:

```
### 1. DRY Principles (4/5)
- Warning: `src/validators.py:45-52` — Duplicate email validation logic. Fix: extract to `validate_email()` helper.
- Suggestion: `src/handlers.py:120,135` — Similar error response construction. Fix: share a response builder.

### 3. Comment Quality (3/5)
- Warning: `src/api.py:22` — Inline comment at end of line. Fix: move to its own line above.
- Warning: `src/models.py:58` — Comment restates the code ("increment counter"). Fix: remove or explain why.
```

### Step 3: Address Findings

**Do NOT ask the user which findings to fix.** Proceed autonomously:

1. **Yes:** Implement all fixes immediately.
2. **Optional:** Use `/receiving-code-review` to evaluate each finding and decide whether to implement or skip.
3. **No:** Nothing to do.

After implementing fixes, present a summary of what was changed and what was skipped (with reasoning for skipped Optional items). When implementing fixes, re-read the review file at `$TMPDIR/code-review-<timestamp>.md` if needed.

## Red Flags

- Do NOT set the `model` parameter for the `code-reviewer` agent
- Do NOT run a single monolithic review covering all aspects
- Do NOT run reviewers sequentially (they are independent)
- Do NOT skip any of the 7 review areas (include 5/5 areas in the table)
- Do NOT ask the user which findings to address — fix Yes items, evaluate Optional items
- Do NOT fabricate scores — every score must come from a subagent
- Do NOT present results without first persisting them to the review file
- Do NOT implement Optional findings blindly — use /receiving-code-review to evaluate
- Do NOT dispatch reviewers before committing all changes
