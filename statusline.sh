#!/bin/bash
# Claude Code Status Line — Catppuccin Mocha + Nerd Font
set -euo pipefail

input=$(cat)

# Parse JSON input
model=$(echo "$input" | jq -r '.model.display_name // "Claude"' | sed 's/^Claude //')
remaining=$(echo "$input" | jq -r '.context_window.remaining_percentage // empty')
cwd=$(echo "$input" | jq -r '.workspace.current_dir // "~"')

# Catppuccin Mocha palette (256-color)
DYL='\033[38;5;178m'   # Dark Yellow — project
BLU='\033[38;5;111m'   # Blue — git branch
GRN='\033[38;5;150m'   # Green — clean / low usage
RED='\033[38;5;211m'   # Red — dirty / high usage
MAU='\033[38;5;183m'   # Mauve — model
YEL='\033[38;5;223m'   # Yellow — medium usage
DIM='\033[38;5;60m'    # Surface2 — separators
TXT='\033[38;5;189m'   # Text
RST='\033[0m'

sep="${DIM}│${RST}"

# ── Project name + Git ──
cd "$cwd" 2>/dev/null || cd ~
if git rev-parse --git-dir > /dev/null 2>&1; then
    project=$(basename "$(git -c core.useBuiltinFSMonitor=false rev-parse --show-toplevel 2>/dev/null)")
    branch=$(git -c core.useBuiltinFSMonitor=false rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")

    if git -c core.useBuiltinFSMonitor=false diff-index --quiet HEAD -- 2>/dev/null; then
        status_icon="${GRN}✓${RST}"
    else
        status_icon="${RED}✗${RST}"
    fi

    git_section="${BLU}󰊢 ${branch}${RST} ${status_icon}"
else
    project=$(basename "$cwd")
    git_section=""
fi

# ── Context progress bar (20 chars) — shows USED context ──
ctx_section=""
if [ -n "$remaining" ]; then
    used=$((100 - $(printf "%.0f" "$remaining")))
    bar_w=20
    filled=$((used * bar_w / 100))
    empty=$((bar_w - filled))

    if [ "$used" -lt 40 ]; then bar_c="$GRN"
    elif [ "$used" -lt 70 ]; then bar_c="$YEL"
    else bar_c="$RED"; fi

    bar="${bar_c}"
    for ((i = 0; i < filled; i++)); do bar+="█"; done
    bar+="${DIM}"
    for ((i = 0; i < empty; i++)); do bar+="░"; done
    bar+="${RST}"

    ctx_section="${bar} ${TXT}${used}%${RST}"
fi

# ── Assemble ──
line1="${DYL}󰮄 ${project}${RST}"
[ -n "$git_section" ] && line1="${line1} ${sep} ${git_section}"

line2="${MAU}󰧑 ${model}${RST}"
[ -n "$ctx_section" ] && line2="${line2}   ${ctx_section}"

echo -e "${line1}\n${line2}"
