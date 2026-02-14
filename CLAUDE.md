## Review Workflow

When you finish implementing a task:
1. Run /ask-claude-review to self-review your changes
2. Address any findings the user selects
3. Run /push-pr to create or update the PR
4. Stop and wait for human review

Do not continue to the next task after creating a PR.

When the user runs /pull-review-comments:
- Address each thread applying /receiving-code-review principles
- After pushing fixes, stop and wait for re-review
