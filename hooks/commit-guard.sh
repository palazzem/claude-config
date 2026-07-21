#!/usr/bin/env bash
# PreToolUse hook (settings.json, matcher Bash): receives the tool call as JSON on stdin.
set -euo pipefail

cmd=$(jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
[ -n "$cmd" ] || exit 0

printf '%s' "$cmd" | grep -qE '\bgit\b[^|;&]*\bcommit\b|\bgh\b[^|;&]*\bpr\b[^|;&]*\b(create|edit)\b' || exit 0

if printf '%s' "$cmd" | grep -qiE 'generated with claude|co-authored-by:.*claude|noreply@anthropic\.com'; then
  echo "commit-guard: blocked - commit or PR text contains Claude/Anthropic attribution (Generated with Claude, Co-Authored-By: ...claude, or an Anthropic noreply email); remove it and run the command again." >&2
  exit 2
fi

exit 0
