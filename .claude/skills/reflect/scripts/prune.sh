#!/usr/bin/env bash
# prune.sh — delete the memory files a merged reflect PR made redundant, and
# drop their lines from the sibling MEMORY.md index.
#
# Usage:
#   prune.sh [--dry-run] < manifest
# The manifest is one path per line, <slug>/memory/<file>.md relative to the
# root or absolute under it; blank lines are ignored. Root: REFLECT_MEMORY_ROOT,
# default $HOME/.claude/projects.
#
# Every line is validated before anything is touched — inside the root, exactly
# <slug>/memory/<file>.md, not MEMORY.md, no empty or "." / ".." component. One
# bad line fails the whole run with every offender on stderr and nothing deleted.
# --dry-run runs the same path and skips the writes.
#
# Output — one JSON object on stdout:
#   {"deleted":[…],"skipped":[…],"index_lines_removed":n,"dry_run":bool}
#   deleted   root-relative paths removed (with --dry-run: that would be)
#   skipped   paths already absent; their index lines are still removed
# Diagnostics go to stderr.
#
# Exit codes: 0 done; 1 root missing; 2 invalid manifest or invocation — nothing deleted.

set -euo pipefail

usage() { echo "usage: prune.sh [--dry-run] < manifest" >&2; }

DRY=false
case "$#" in
  0) ;;
  1) if [ "$1" = "--dry-run" ]; then DRY=true; else usage; exit 2; fi ;;
  *) usage; exit 2 ;;
esac

ROOT="${REFLECT_MEMORY_ROOT:-$HOME/.claude/projects}"
if [ ! -d "$ROOT" ]; then
  echo "prune: memory root not found: $ROOT" >&2
  exit 1
fi
ROOT="$(cd "$ROOT" && pwd -P)"

TMP=""
trap '[ -n "$TMP" ] && rm -f -- "$TMP"' EXIT

# Validate every line; collect the root-relative paths.
entries=()
bad=0
reject() { echo "prune: $1: $2" >&2; bad=1; }
while IFS= read -r line || [ -n "$line" ]; do
  line="${line%$'\r'}"
  case "$line" in
    ''|*[![:space:]]*) ;;
    *) continue ;;
  esac
  [ -z "$line" ] && continue

  rel="$line"
  case "$rel" in
    "$ROOT"/*) rel="${rel#"$ROOT"/}" ;;
    /*) reject "outside root" "$line"; continue ;;
  esac

  IFS=/ read -r slug mid file extra <<EOF
$rel
EOF
  if [ -z "$slug" ] || [ -z "$file" ] || [ -n "${extra:-}" ] || [ "$mid" != "memory" ]; then
    reject "not <slug>/memory/<file>.md" "$line"; continue
  fi
  case "$slug" in .|..) reject "bad component" "$line"; continue ;; esac
  case "$file" in .|..) reject "bad component" "$line"; continue ;; esac
  case "$file" in *.md) ;; *) reject "not a .md file" "$line"; continue ;; esac
  if [ "$file" = "MEMORY.md" ]; then
    reject "index file is never pruned" "$line"; continue
  fi
  entries+=("$rel")
done

if [ "$bad" -ne 0 ]; then
  echo "prune: invalid manifest — nothing deleted" >&2
  exit 2
fi
if [ "${#entries[@]}" -eq 0 ]; then
  echo "prune: empty manifest — nothing to do" >&2
  exit 2
fi

# Act.
deleted='[]'
skipped='[]'
removed=0
for rel in "${entries[@]}"; do
  abs="$ROOT/$rel"
  base="${rel##*/}"
  index="${abs%/*}/MEMORY.md"

  if [ -f "$abs" ]; then
    if [ "$DRY" = false ]; then rm -- "$abs"; fi
    deleted="$(jq -c --arg p "$rel" '. + [$p]' <<<"$deleted")"
  else
    skipped="$(jq -c --arg p "$rel" '. + [$p]' <<<"$skipped")"
  fi

  if [ -f "$index" ]; then
    n="$(awk -v pat="](${base})" 'index($0, pat) { c++ } END { print c + 0 }' "$index")"
    if [ "$n" -gt 0 ] && [ "$DRY" = false ]; then
      TMP="$(mktemp "${index}.XXXXXX")"
      awk -v pat="](${base})" 'index($0, pat) == 0' "$index" > "$TMP"
      mv -- "$TMP" "$index"
      TMP=""
    fi
    removed=$((removed + n))
  fi
done

jq -nc --argjson deleted "$deleted" --argjson skipped "$skipped" \
  --argjson n "$removed" --argjson dry "$DRY" \
  '{deleted: $deleted, skipped: $skipped, index_lines_removed: $n, dry_run: $dry}'
