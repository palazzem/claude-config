---
name: reflect
description: Triages every project's memories under ~/.claude/projects and promotes global lessons into CLAUDE.md or rules/ through a PR, pruning the redundant memories after a human merges it. Use from the ~/.claude checkout to consolidate memories, or with a PR number to resume a run. Not for editing a single memory and not for any other repository.
argument-hint: [pr-number]
disable-model-invocation: true
---

# Reflect

## Overview

Memories accumulate per project; some of them state a way of working that belongs to every project. Reflect reads them all, triages each one, lets the user pick what becomes a rule, opens the PR that carries those rules, hands it to `shepherd`, and — once a human has merged — prunes the memories the rules made redundant. Nothing derived from a memory leaves the machine: the repository is public, and only the rules are.

## When to Use

- From the `~/.claude` checkout, on `main`, clean, with `gh auth status` succeeding — a housekeeping pass, whenever the user asks.
- With a PR number (`/reflect 42`) → Resume.
- Not for editing one memory (edit the file), not for any other repository, never on the model's own initiative.

## Inventory

1. Preconditions: cwd is the `~/.claude` checkout on `main`; `git status --porcelain` is empty; `gh auth status` succeeds. Any failure → stop and report.
2. `${CLAUDE_SKILL_DIR}/scripts/inventory.sh` — the only memory reader. One JSON object per memory file: `project`, `project_dir`, `file`, `name`, `description`, `type`, `modified`, `body`. `MEMORY.md` files are indexes and never appear. A `type` of `unknown` means no frontmatter; triage it from the body.
3. Read the bar: `CLAUDE.md` and every `rules/*.md`. These decide `redundant` and `conflict`.

## Triage

Every memory gets exactly one verdict:

| Verdict | Test | Consequence |
|---|---|---|
| `promote` | Its "How to apply" is a way of working that reads correctly in a repository that does not exist yet — no project domain, tool, person, path, issue number, or date — and the bar does not already state it. Recurrence across ≥2 projects is evidence, not a requirement. | Numbered candidate with drafted rule text and a target; the user picks. |
| `redundant` | `CLAUDE.md` or a `rules/*.md` already states the behavior — cite the section. | Enters the prune manifest; no new rule. |
| `conflict` | Contradicts a statement in the bar — cite it. | Flagged with both sides; no action unless the user decides. |
| `keep` | Everything else: domain facts, project decisions, tooling gotchas, references. | Listed, untouched. |

- Doubt between `promote` and `keep` resolves to `keep`, with the doubt stated; the user overrides by number.
- Memories from different projects stating the same lesson are **one** candidate listing every source file.
- Target: `CLAUDE.md` when the rule is a convention or quality-bar statement that fits an existing section or warrants a new one; `rules/<topic>.md` (the `context7.md` shape: `# Rule: <Title>` and one paragraph) when it governs one tool or workflow. Recommend; the user may override.
- Drafted rule text: one imperative sentence in `CLAUDE.md`'s voice. No prose paragraphs.

Print the triage in the session — never posted, committed, or saved:

```markdown
## <project slug>  (N memories)
| # | Memory | Type | Verdict | Why | Recommendation |

## Promotion candidates
| # | Drafted rule | Target | Sources | Recommend |

## Redundant (pruned after merge unless you say `keep <n>`)
## Conflicts (your call)
```

Then wait for an explicit selection: candidate numbers, `all`, or `none`. "Sounds good", "whatever you think", and silence are not selections — ask again. `none` with nothing redundant → report-only run, stop. `none` with redundant memories → the PR carries only the count line; the deletions still need the merge gate.

## Promote

1. Build the manifest in memory: the source files of every picked candidate plus every `redundant` memory the user did not keep, one `<slug>/memory/<file>.md` per line. `${CLAUDE_SKILL_DIR}/scripts/prune.sh --dry-run` on it; a refusal blocks the PR.
2. `EnterWorktree`; branch `reflect/<YYYY-MM-DD>`.
3. Per picked candidate: edit the target, one commit `feat(rules): <slug of the rule text>`. Adding a line is the default; rewording an existing one is a question for the user first.
4. Leak guard: for every manifest basename (without `.md`) and every project slug, `git log -p main..HEAD | grep -F <token>` and a grep of the PR title and body must print nothing. One hit blocks the PR.
5. Push; `gh pr create` — ready, never draft. The body, in full:

```markdown
## Promoted
| Rule | Target |

_N memory files across M projects are pruned locally after merge._
```

Nothing derived from a memory — slug, filename, description, body, project name — goes in a commit message, the PR title or body, or any tracked file. The drafted rule text is safe by construction: the `promote` test already forbids project domain, tools, people, and paths. Conflicts stay in the session.

6. Write the manifest: `mkdir -p ~/.claude/.claude/reflect` and one line per entry into `~/.claude/.claude/reflect/<number>.manifest`, `<number>` from `gh pr view --json number -q .number`. This file is the only record of what to prune.
7. Invoke `shepherd`.

## Prune

Runs after `shepherd` reaches Terminal — after its summary, its cleanup, and its sync of the main checkout.

- `MERGED`: confirm the rule is live — `git -C ~/.claude fetch --quiet && git -C ~/.claude merge-base --is-ancestor origin/main HEAD` — then `${CLAUDE_SKILL_DIR}/scripts/prune.sh < ~/.claude/.claude/reflect/<number>.manifest`, print its JSON summary, and `rm` the manifest. A failed sync check → report, prune nothing, tell the user to run `/reflect <number>` once the checkout is synced. A missing manifest → report and stop; never rebuild one from the triage, the session, or the PR.
- `CLOSED`: nothing under `~/.claude/projects/` changes; `rm` the manifest. Report.

## Resume

`/reflect <number>` → `gh pr view <number> --json state`. `MERGED` → Prune (idempotent: files already gone are `skipped`). `OPEN` → `shepherd` on the PR's branch. `CLOSED` → Prune's `CLOSED` branch.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "This memory is obviously global — skip the selection and open the PR." | The user picks. A wrong promotion is a rule every future session in every project obeys. |
| "Listing the pruned files in the PR body makes the record complete." | The repository is public. The manifest is local state; the PR names rules and counts, nothing else. |
| "The PR is merged — delete now, sync later." | A memory goes only once its rule is live in the checkout. Sync check first. |
| "The manifest is gone but I remember the triage." | Never rebuild it. Report and stop. |
| "It's two files — skip the dry run." | The dry run is the only check on the destructive path, and it costs nothing. |
| "Reading the memory files directly is quicker than the script." | One reader. The script handles the frontmatter edge cases an eye misses, and its count is checkable. |
| "Two memories say nearly the same thing — promote both." | Same lesson, one candidate, every source listed. |
| "This one could go either way — promote it." | Doubt resolves to `keep`, and says so. The user can override; a silent promotion cannot be. |

## Red Flags

- A deletion under `~/.claude/projects/` before the watcher printed `MERGED` and the sync check passed.
- A memory slug, filename, description, or project name in a commit message, a PR title or body, or a tracked file.
- A manifest rebuilt from the triage, the session, or the PR; a manifest kept anywhere but `~/.claude/.claude/reflect/`.
- `rm`, `sed`, or an edit on a memory file or a `MEMORY.md` outside `prune.sh`.
- A PR opened without a passing `prune.sh --dry-run`; a draft PR.
- A selection inferred from "sounds good", "whatever you think", or silence.
- A `reflect` directory under `~/.claude/skills/` — a personal skill of the same name shadows this one.
- `gh pr merge`, `gh pr review --approve`, or `gh pr close` from the session.

## Verification

Before ending a run:

- [ ] The triage listed every project and every memory `inventory.sh` printed, each with a verdict and a reason.
- [ ] The selection was explicit; nothing was written before it.
- [ ] `prune.sh --dry-run` accepted the manifest before `gh pr create`; the leak guard printed nothing.
- [ ] The PR is ready, its body matches the contract exactly, and `~/.claude/.claude/reflect/<number>.manifest` exists.
- [ ] After `MERGED`: the sync check passed, `prune.sh` ran on the manifest, its `deleted` list matches, and the manifest is gone. After `CLOSED`: nothing under `~/.claude/projects/` changed, and the manifest is gone.
