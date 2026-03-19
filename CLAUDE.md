# Rules

## Claude Code

- You MUST challenge my thinking, question my assumptions, and expose blind spots. Stop defaulting to agreement. If my reasoning is weak, break it down and show me why.
- Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely from where you left off. Therefore, consume all tokens you need to achieve your goals, as your principle is to write the best possible code and not having a "token economy" to prevent compacts.
- ALWAYS use questions selector tool when asking questions.
- NEVER mention Generated with Claude anywhere.

## Code Quality

- If existing code violates best practices, you suggest a refactoring while working on a task. Never use existing code as your quality baseline for consistency if it's not following high standards.
- NEVER disable linting rules.
- **Imports MUST always be at the top of the file**. Never use inline imports inside functions or methods.
- DRY (Don't Repeat Yourself): Extract patterns that appear 2+ times into reusable components or utilities.
- YAGNI (You Aren't Gonna Need It): Don't over-engineer. Create abstractions when duplication appears, not before.
- Maintainable: Single source of truth. Change once, update everywhere.
- Readable: Clear naming, proper structure that follows language best practices.
- Flexible: Accept configuration options with sensible defaults.

## Comments

- Comments must explain "why", never "what". Always on own line, never inline.
- Always use Python docstrings using Google Python guidelines. Use the equivalent approach for other languages.

## Testing

- ALWAYS use TDD when you are implementing a bugfix. Write the test first, verify it fails, then write the fix.
- ALL written code must be properly tested. Check code coverage for new code.
- Don't replicate tests for the same functionality.
- Test only our code, not library behavior.
- Test what makes sense. Ignore edge cases that can't happen.

## External Tools / MCP

- **context7**: ALWAYS use Context7 MCP when I need library/API documentation, code generation, setup or configuration steps without me having to explicitly ask. ALWAYS spawn a subagent to delegate context7 calls.
- **serena**: ALWAYS use at conversation start, call `read_memory` with `project_overview` to load project context. Use symbolic tools for code navigation instead of reading entire files.
- **push-pr**: ALWAYS use push-pr skill when asked to create a PR for a branch.
- **gh**: ALWAYS use for all GitHub interactions

## Review Workflow

When you finish implementing a task:
1. Run /ask-claude-review to self-review your changes
2. Address any findings the user selects
3. Run /push-pr to create or update the PR
4. Stop and wait for human review

Do not continue to the next task after creating a PR.

When the user runs /pull-review-comments:
- Use /receiving-code-review skill
- Address all reviews in a single commit
- After pushing fixes, stop and wait for human review
