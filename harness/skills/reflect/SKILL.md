---
name: reflect
description: Triages every project's memories under ~/.claude/projects and promotes each chosen lesson into the global rules in ~/.claude or into the rules of the project it came from, as the user picks, through one PR per target repository, pruning the redundant memories after a human merges it. Use to consolidate memories, or with a PR URL to resume a run. Not for editing a single memory.
argument-hint: [pr-url]
disable-model-invocation: true
---

# Reflect

## Overview

Memories accumulate per project and stay on the machine. Some state a way of working that belongs to every project; some state a convention that belongs to the project they came from. Reflect reads them all, triages each one, lets the user pick what becomes a rule and where it lands — the global rules in `~/.claude` or the project's own rules — opens one PR per target repository, hands each to `harness:shepherd`, and, once a human has merged, prunes the memories the rules made redundant. Nothing derived from a memory leaves the machine except the rule text itself.

## When to Use

- Whenever the user asks for a housekeeping pass, with `gh auth status` succeeding.
- With a PR URL (`/harness:reflect https://github.com/<owner>/<repo>/pull/42`) → Resume.
- Not for editing one memory (edit the file).

## Targets

| Target | Repository | File |
|---|---|---|
| `global` | the `~/.claude` checkout | `rules/<topic>.md` |
| `project` | the repository the memory's project directory belongs to | its `.claude/rules/<topic>.md`, or its `CLAUDE.md` when the repository keeps its rules there |

Resolve a memory's repository from the working directory its project's transcripts record: `jq -r 'select(.cwd) | .cwd' <project_dir>/*.jsonl | head -1`, then `git -C <cwd> rev-parse --show-toplevel`. The project directory's name is not decodable, since both `/` and `.` become `-`. A project whose repository cannot be resolved has no `project` target: its lessons are kept unless they pass the `global` test as drafted.

## Inventory

1. Preconditions: `gh auth status` succeeds, and the session is not inside a worktree (`git rev-parse --git-dir` equals `--git-common-dir`, or there is no repository). A failure → stop and report.
2. `${CLAUDE_SKILL_DIR}/scripts/inventory.sh` — the only memory reader. One JSON object per memory file: `project`, `project_dir`, `file`, `name`, `description`, `type`, `modified`, `body`. `MEMORY.md` files are indexes and never appear. A `type` of `unknown` means no frontmatter; triage it from the body.
3. Read the bar: every `~/.claude/rules/*.md`, and for each resolved project its `CLAUDE.md` and `.claude/rules/*.md`, read from `<default>` with `git -C <repo> show origin/<default>:<file>` after a `git -C <repo> fetch --quiet`. These decide `redundant` and `conflict`.

## Triage

Every memory gets exactly one verdict:

| Verdict | Test | Consequence |
|---|---|---|
| `promote` | Its "How to apply" is a way of working the bar does not already state. It is `global` when it reads correctly in a repository that does not exist yet — no project domain, tool, person, path, issue number, or date — and `project` when it holds only for the project it came from. Recurrence across ≥2 projects is evidence for `global`, not a requirement. | Numbered candidate with drafted rule text, a recommended target, and a file; the user picks. |
| `redundant` | The global rules or its project's rules already state the behavior — cite the file. | Enters the prune manifest; no new rule. |
| `conflict` | Contradicts a statement in the bar — cite it. | Flagged with both sides; no action unless the user decides. |
| `keep` | Everything else: domain facts, one-off decisions, references, anything another document already owns. | Listed, untouched. |

- Doubt between `promote` and `keep` resolves to `keep`, with the doubt stated; the user overrides by number.
- Memories stating the same lesson are **one** candidate listing every source file. A candidate whose sources span several projects is `global`, or is split into one `project` candidate per project; a single `project` candidate never carries another project's memory.
- File: the existing `<topic>.md` the rule belongs to, or a new one in the `# Rule: <Title>` shape. Recommend; the user may override.
- Drafted rule text: one imperative sentence. No prose paragraphs.

Print the triage in the session — never posted, committed, or saved:

```markdown
## <project slug>  (N memories)
| # | Memory | Type | Verdict | Why | Recommendation |

## Promotion candidates
| # | Drafted rule | Target | File | Sources |

## Redundant (pruned once you confirm, unless you say `keep <n>`)
## Conflicts (your call)
```

Then wait for an explicit selection: candidate numbers, each with `global` or `project` where the user overrides the recommended target, or `all`, or `none`. "Sounds good", "whatever you think", and silence are not selections — ask again. `none` with nothing redundant → report-only run, stop. Redundant memories need no PR, since the rule that makes them redundant is already on the default branch: after the user confirms the redundant list, `prune.sh --dry-run`, then `prune.sh`, on a manifest of those files alone.

## Promote

Run once per target repository that the selection touches, `<repo>` being its main checkout and `<default>` its default branch. The session works on it from outside, with `git -C`, so nothing depends on where the session started:

1. Preconditions: `git -C <repo> status --porcelain` is empty and `<repo>` is on `<default>`. A failure → skip this repository, report it, go on with the next.
2. Build the manifest in memory: the source files of every picked candidate for this repository, one `<slug>/memory/<file>.md` per line. `${CLAUDE_SKILL_DIR}/scripts/prune.sh --dry-run` on it; a refusal blocks this repository's PR.
3. `git -C <repo> fetch --quiet`, then `git -C <repo> worktree add -b reflect/<YYYY-MM-DD> <repo>/.claude/worktrees/reflect-<YYYY-MM-DD> origin/<default>`; `<wt>` is that path.
4. Per picked candidate: edit the target file under `<wt>`, one commit `feat(rules): <slug of the rule text>`. Adding a line is the default; rewording an existing one is a question for the user first.
5. Leak guard: for every manifest basename (without `.md`) and every project slug, `git -C <wt> log -p origin/<default>..HEAD | grep -F <token>` and a grep of the PR title and body must print nothing. One hit blocks the PR.
6. `git -C <wt> push -u origin reflect/<YYYY-MM-DD>`; `gh pr create -R <owner>/<repo> --head reflect/<YYYY-MM-DD>` — ready, never draft. The body, in full:

```markdown
## Promoted
| Rule | File |

_N memory files are pruned locally after merge._
```

Nothing derived from a memory — slug, filename, description, body, project name — goes in a commit message, the PR title or body, or any tracked file; the drafted rule text is the one exception. Conflicts stay in the session.

7. Write the manifest: `mkdir -p ~/.claude/reflect` and one line per entry into `~/.claude/reflect/<owner>-<repo>-<YYYY-MM-DD>.manifest` — the repository is the PR's, the date is the branch's — and the absolute path of `<repo>` into the `.checkout` file of the same name. These files are the only record of what to prune and where.

Once every repository has its PR, invoke `harness:shepherd` on the first, with its commands run from that PR's `<wt>`; arm the next when that watch ends, one watch at a time. At the terminal, the worktree step for these watches is `git -C <repo> worktree remove --force <wt>` only, never `ExitWorktree`, which acts on the session's own worktree instead.

## Prune

Runs per PR after `harness:shepherd` reaches Terminal — after its summary, its cleanup, and its sync of the main checkout.

- `MERGED`: confirm this PR's rule is live — `gh pr view <pr-url> --json state,mergeCommit` reports `MERGED`, and in the checkout the `.checkout` file names, `git fetch --quiet && git merge-base --is-ancestor <mergeCommit.oid> HEAD` — then `${CLAUDE_SKILL_DIR}/scripts/prune.sh < <manifest>`, print its JSON summary, and `rm` the manifest and its `.checkout`. A failed check → report, prune nothing, tell the user to run `/harness:reflect <pr-url>` once the checkout is synced. A missing manifest → report and stop; never rebuild one from the triage, the session, or the PR.
- `CLOSED`: nothing under `~/.claude/projects/` changes; `rm` the manifest and its `.checkout`. Report.
- Either way, `git -C <repo> worktree remove --force <wt>` and `git -C <repo> branch -D reflect/<YYYY-MM-DD>` when shepherd left them.

## Resume

`/harness:reflect <pr-url>` → `gh pr view <pr-url> --json state,headRefName`; the PR's repository and its head branch `reflect/<YYYY-MM-DD>` name the manifest and its `.checkout`. `MERGED` → Prune (idempotent: files already gone are `skipped`). `OPEN` → `harness:shepherd` on the PR's branch, from its `<wt>`: `<repo>/.claude/worktrees/reflect-<YYYY-MM-DD>`, `<repo>` read from the `.checkout` file. `CLOSED` → Prune's `CLOSED` branch.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "This memory is obviously global — skip the selection and open the PR." | The user picks the rule and its target. A wrong global promotion is a rule every future session in every project obeys. |
| "The lesson came from this project, so it is a project rule." | Where it came from is evidence, not the test. A way of working that reads correctly in a repository that does not exist yet is `global`. |
| "Listing the pruned files in the PR body makes the record complete." | The manifest is local state; the PR names rules and counts, nothing else. |
| "The PR is merged — delete now, sync later." | A memory goes only once its rule is live in the checkout. Sync check first. |
| "The manifest is gone but I remember the triage." | Never rebuild it. Report and stop. |
| "It's two files — skip the dry run." | The dry run is the only check on the destructive path, and it costs nothing. |
| "Reading the memory files directly is quicker than the script." | One reader. The script handles the frontmatter edge cases an eye misses, and its count is checkable. |
| "Two memories say nearly the same thing — promote both." | Same lesson, one candidate, every source listed. |
| "This one could go either way — promote it." | Doubt resolves to `keep`, and says so. The user can override; a silent promotion cannot be. |

## Red Flags

- A deletion of a memory in a PR manifest before that PR's merge commit is in its repository's checkout; a merge check on any other signal; a redundant memory pruned before the user confirmed the list.
- A memory slug, filename, description, or project name in a commit message, a PR title or body, or a tracked file.
- A manifest rebuilt from the triage, the session, or the PR; a manifest kept anywhere but `~/.claude/reflect/`.
- `rm`, `sed`, or an edit on a memory file or a `MEMORY.md` outside `prune.sh`.
- A PR opened without a passing `prune.sh --dry-run`; a draft PR; one PR carrying rules for two repositories.
- A target picked by the session; a `project` lesson promoted `global` because its repository could not be resolved; a selection inferred from "sounds good", "whatever you think", or silence.
- `gh pr merge`, `gh pr review --approve`, or `gh pr close` from the session.

## Verification

Before ending a run:

- [ ] The triage listed every project and every memory `inventory.sh` printed, each with a verdict and a reason.
- [ ] The selection named every candidate's target explicitly or accepted the recommended one by number; nothing was written before it.
- [ ] Redundant memories were pruned only after the user confirmed the list and `prune.sh --dry-run` accepted it.
- [ ] Each target repository got one PR, `prune.sh --dry-run` accepted its manifest before `gh pr create`, and the leak guard printed nothing.
- [ ] Each PR is ready, its body matches the contract exactly, and its manifest exists under `~/.claude/reflect/`.
- [ ] After `MERGED`: the sync check passed, `prune.sh` ran on the manifest, its `deleted` list matches, and the manifest is gone. After `CLOSED`: nothing under `~/.claude/projects/` changed, and the manifest is gone.
