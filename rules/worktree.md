A PR's worktree is never abandoned: when a PR reaches a terminal state (merged or closed), teardown follows the worktree-lifecycle skill.

Unmerged work is never deleted: a PR closed without merge keeps its local branch, its remote branch, and any dirty worktree.
