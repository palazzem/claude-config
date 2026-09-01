# Skill Anatomy

This document describes the structure and format of the skills in this repository. Use it as the ruling when writing a new skill or auditing an existing one.

## File Location

Every skill lives in its own directory under `skills/`:

```
skills/
  skill-name/
    SKILL.md           # Required: The skill definition
    scripts/           # Optional: Runnable helpers used by the skill workflow
    references/        # Optional: Skill-specific reference documentation
    supporting-file.md # Optional: Reference material loaded on demand
```

`SKILL.md` is the only required file. Add `scripts/` or `references/` only when the skill actually needs them, and omit them entirely for simpler skills.

A skill is installed by placing `skills/<name>/` under `~/.claude/skills/`, as a copy or a symlink. At runtime a skill can reach only what lives inside its own directory — never a sibling skill, never a repository-root file. See [Self-Contained Skills](#self-contained-skills).

## SKILL.md Format

### Frontmatter (Required)

```yaml
---
name: skill-name-with-hyphens
description: Guides agents through [task/workflow]. Use when [specific trigger conditions].
---
```

**Rules:**
- `name`: 1–64 characters; lowercase letters, digits, and single hyphens; no leading or trailing hyphen. Must match the directory name.
- `description`: Third person. Start with what the skill does, then one or more clear "Use when" trigger conditions and the exclusions ("not for"). Include both *what* and *when*. Maximum 1024 characters.
- Optional fields Claude Code recognizes (`argument-hint`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `model`, `effort`, `context`) are allowed when the skill needs the behavior they control. A field that does not change how the skill runs is noise.

**Why this matters:** Agents discover skills by reading descriptions. The description is injected into the system prompt, so it must tell the agent both what the skill provides and when to activate it. Do not summarize the workflow — if the description contains process steps, the agent may follow the summary instead of reading the full skill.

### Standard Sections (Recommended Pattern)

The frontmatter contract above is required. The section layout below is a recommended pattern, not a rigid template: equivalent headings are acceptable when they serve the same purpose clearly.

```markdown
# Skill Title

## Overview
One-two sentences explaining what this skill does and why it matters.

## When to Use
- Bullet list of triggering conditions (symptoms, task types)
- When NOT to use (exclusions)

## [Core Process / The Workflow / Steps]
The main workflow, broken into numbered steps or phases.
Include code examples where they help.
Use flowcharts (ASCII) where decision points exist.

## [Specific Techniques / Patterns]
Detailed guidance for specific scenarios.
Code examples, templates, configuration.

## Common Rationalizations
| Rationalization | Reality |
|---|---|
| Excuse agents use to skip steps | Why the excuse is wrong |

## Red Flags
- Behavioral patterns indicating the skill is being violated
- Things to watch for during review

## Verification
After completing the skill's process, confirm:
- [ ] Checklist of exit criteria
- [ ] Evidence requirements
```

## Section Purposes

### Overview
The "elevator pitch" for the skill. Should answer: What does this skill do, and why should an agent follow it?

### When to Use
Helps agents and humans decide if this skill applies to the current task. Include both positive triggers ("Use when X") and negative exclusions ("NOT for Y").

### Core Process
The heart of the skill. This is the step-by-step workflow the agent follows. Must be specific and actionable — not vague advice.

**Good:** "Run `npm test` and verify all tests pass"
**Bad:** "Make sure the tests work"

### Common Rationalizations
The most distinctive feature of well-crafted skills. These are excuses agents use to skip important steps, paired with rebuttals. They prevent the agent from rationalizing its way out of following the process.

Think of every time an agent has said "I'll add tests later" or "This is simple enough to skip the spec" — those go here with a factual counter-argument.

### Red Flags
Observable signs that the skill is being violated. Useful during code review and self-monitoring.

### Verification
The exit criteria. A checklist the agent uses to confirm the skill's process is complete. Every checkbox should be verifiable with evidence (test output, build result, screenshot, etc.).

## Supporting Files

Create supporting files only when:
- Reference material exceeds 100 lines (keep the main SKILL.md focused)
- Code tools or scripts are needed
- Checklists are long enough to justify separate files

Keep patterns, principles, and templates inline when under 50 lines.

If a skill does not need runnable helpers, do not create an empty `scripts/` directory just to mirror other skills. Empty directories add noise without changing how the skill works.

## Self-Contained Skills

A skill is a self-contained directory, and this repository keeps it that way: nothing a skill reads or runs lives outside `skills/<name>/`. There is no repository-root `references/` for material shared across skills.

The reason is the install model. A skill reaches the harness as its own directory under `~/.claude/skills/`; a repository-root sibling does not travel with it, and a link to one resolves to nothing at runtime.

When two skills need the same material, one skill owns it and the other refers to that skill by name (see [Cross-Skill References](#cross-skill-references)). Do not copy the material into both — copies drift.

## Context Efficiency

Skills load on demand: only the skill name and description sit in context at startup. The full `SKILL.md` loads only when an agent decides the skill is relevant. To keep that load cheap:

- **Keep `SKILL.md` under 500 lines.** Move detailed reference material into supporting files.
- **Write specific descriptions.** A precise description helps the agent activate the skill at the right moment and skip it otherwise.
- **Use progressive disclosure.** Reference supporting files that are read only when the workflow reaches them.
- **Prefer scripts over inline code.** Executing a script consumes no context; only its output does. Inline code blocks are paid for on every load.
- **Keep file references one level deep.** Link directly from `SKILL.md` to supporting files rather than chaining through intermediate documents.

## Script Requirements

When a skill ships runnable helpers under `scripts/`, each script follows these conventions:

- Use a `#!/usr/bin/env bash` shebang and stay compatible with bash 3.2: macOS ships that version at `/bin/bash`, so bash 4+ features (`mapfile`, associative arrays, `${var,,}`) are unavailable on the platform this harness runs on.
- Use `set -euo pipefail` for fail-fast behavior. A long-running script that must survive a transient failure — a poller whose `gh` call times out — guards that one call explicitly (`out=$(cmd) || out=""`) and says why; it does not drop `-e` for the whole script.
- Write status messages and diagnostics to stderr: `echo "Message" >&2`.
- Write machine-readable output to stdout: a JSON document for a one-shot result, one JSON object per line for a stream of events.
- When the script creates temporary files, include a cleanup trap for them.
- Reference the script from `SKILL.md` as `${CLAUDE_SKILL_DIR}/scripts/<script>.sh`. Claude Code substitutes the installed skill directory; a repository-relative path does not resolve at runtime.

## Writing Principles

1. **Process over knowledge.** Skills are workflows, not reference docs. Steps, not facts.
2. **Specific over general.** "Run `npm test`" beats "verify the tests".
3. **Evidence over assumption.** Every verification checkbox requires proof.
4. **Anti-rationalization.** Every skip-worthy step needs a counter-argument in the rationalizations table.
5. **Progressive disclosure.** Main SKILL.md is the entry point. Supporting files are loaded only when needed.
6. **Token-conscious.** Every section must justify its inclusion. If removing it wouldn't change agent behavior, remove it.

## Naming Conventions

- Skill directories: `lowercase-hyphen-separated`
- Skill files: `SKILL.md` (always uppercase)
- Supporting files: `lowercase-hyphen-separated.md`
- Skill-specific references: a single supporting doc stays as a loose file in the skill directory; when several related docs travel with the skill, group them in a `references/` directory inside the skill directory, so the skill carries its own supporting docs.

## Cross-Skill References

Reference other skills and agents by name:

```markdown
Use the `find-docs` skill to fetch current library documentation.
Hand the proposal to the `skeptic` agent before implementation begins.
```

Don't duplicate content between skills — reference and link instead.

## Required vs Recommended

Required:

- A `skills/<skill-name>/SKILL.md` file
- Valid YAML frontmatter with `name` and `description`
- A description that includes both what the skill does and when to use it

Recommended:

- The standard section flow shown above
- Equivalent headings such as `How It Works`, `Core Process`, or `Workflow` when they read more naturally for the skill
- Supporting files only when they keep the main `SKILL.md` focused
