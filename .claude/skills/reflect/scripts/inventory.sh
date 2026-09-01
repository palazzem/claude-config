#!/usr/bin/env bash
# inventory.sh — the reflect skill's memory reader. Lists every project memory
# under the memory root as JSON, one object per file, so the triage reads one
# stream instead of dozens of files.
#
# Usage:
#   inventory.sh          root: $REFLECT_MEMORY_ROOT, default $HOME/.claude/projects
#
# Output — one JSON object per memory file on stdout, sorted by project, then file:
#   {"project":…,"project_dir":…,"file":…,"name":…,"description":…,"type":…,"modified":…,"body":…}
#   project      directory slug under the root
#   project_dir  absolute path of that directory
#   file         absolute path of the memory file
#   name, description, type, modified   frontmatter fields (type and modified
#                sit under metadata:); quoted values are unquoted and unescaped
#   body         everything after the frontmatter
# MEMORY.md is an index, never inventory. A file without frontmatter yields
# type "unknown" and name = basename without .md, with a note on stderr; the
# run continues. Diagnostics go to stderr.
#
# Exit codes: 0 ok; 1 root missing; 2 invocation error.

set -euo pipefail

if [ "$#" -ne 0 ]; then
  echo "usage: inventory.sh   (root from REFLECT_MEMORY_ROOT, default \$HOME/.claude/projects)" >&2
  exit 2
fi

ROOT="${REFLECT_MEMORY_ROOT:-$HOME/.claude/projects}"
if [ ! -d "$ROOT" ]; then
  echo "inventory: memory root not found: $ROOT" >&2
  exit 1
fi
ROOT="$(cd "$ROOT" && pwd -P)"

# "yes" when line 1 is --- and a closing --- follows; "no" otherwise.
has_frontmatter() {
  awk 'NR == 1 { if ($0 != "---") exit; next }
       $0 == "---" { found = 1; exit }
       END { print (found ? "yes" : "no") }' "$1"
}

# Value of the first "key:" line in the frontmatter, at any indentation, or
# nothing. Surrounding double or single quotes are stripped and their escapes
# undone; the key must start the trimmed line, so "type" never matches "node_type".
fm_field() {
  awk -v key="$2" '
    NR == 1 { next }
    $0 == "---" { exit }
    {
      line = $0
      sub(/^[ \t]+/, "", line)
      if (index(line, key ":") != 1) next
      val = substr(line, length(key) + 2)
      sub(/^[ \t]+/, "", val)
      sub(/[ \t\r]+$/, "", val)
      if (val ~ /^".*"$/) { val = substr(val, 2, length(val) - 2); gsub(/\\"/, "\"", val) }
      else if (val ~ /^\x27.*\x27$/) { val = substr(val, 2, length(val) - 2); gsub(/\x27\x27/, "\x27", val) }
      print val
      exit
    }' "$1"
}

# Everything after the frontmatter; the whole file when there is none.
fm_body() {
  awk 'NR == 1 && $0 == "---" { infm = 1; next }
       infm && $0 == "---" { infm = 0; next }
       !infm { print }' "$1"
}

shopt -s nullglob
for project_dir in "$ROOT"/*/; do
  project_dir="${project_dir%/}"
  project="${project_dir##*/}"
  for file in "$project_dir"/memory/*.md; do
    base="${file##*/}"
    [ "$base" = "MEMORY.md" ] && continue

    if [ "$(has_frontmatter "$file")" = "yes" ]; then
      name="$(fm_field "$file" name)"
      description="$(fm_field "$file" description)"
      type="$(fm_field "$file" type)"
      modified="$(fm_field "$file" modified)"
    else
      echo "inventory: no frontmatter: $file" >&2
      name="" description="" type="" modified=""
    fi
    [ -n "$name" ] || name="${base%.md}"
    [ -n "$type" ] || type="unknown"
    body="$(fm_body "$file")"

    jq -nc \
      --arg project "$project" --arg project_dir "$project_dir" --arg file "$file" \
      --arg name "$name" --arg description "$description" --arg type "$type" \
      --arg modified "$modified" --arg body "$body" \
      '{project: $project, project_dir: $project_dir, file: $file, name: $name,
        description: $description, type: $type, modified: $modified, body: $body}'
  done
done
