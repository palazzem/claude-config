---
name: pr-shepherd
description: Use when a PR needs unattended keep-green maintenance until merge - automatically as the last link of the build chain (invoked right after the review loop flips the PR to OPEN), or manually when the user asks to shepherd, babysit, watch, or keep any PR green. Runs a per-PR haiku loop for rebase freshness, CI triage, lint autofix, and description sync. Maintenance only - it never runs reviews.
argument-hint: <pr> (required for manual attach) - PR URL, or PR number in the current repo
---

# PR Shepherd

One shepherd owns ONE PR until it merges. It is a maintenance routine: it keeps the branch fresh, CI green, and the description honest, and it pings the user with exactly two message types. It is attached automatically by the review loop the moment the PR flips to OPEN, or manually to any PR.

It is NOT a reviewer. The review loop converged before the shepherd started; after that, only humans review.

## Boundaries (hard rails)

| Rail | Detail |
|---|---|
| Never merge, never close | Terminal states are observed, never caused |
| Never mark ready | `gh pr ready` belongs to the review loop; a manually attached shepherd maintains a draft PR without flipping it |
| Never spawns reviewers | Never invokes pr-review or review-triage, never re-runs the panel, for any reason |
| Never replies to comments | New PR comments make the PR active (state economics) but get no reply and no dispatched review work; they are noted in the report only. The single exception: type 2 escalation comments authored by the shepherd itself (section 7) |
| Force-push discipline | Only `--force-with-lease`, only ever the PR's own head branch, only after a rebase this shepherd performed |
| No code from the runner | All code fixes go to the PR's persistent builder agent, resumed by name; the runner never writes code itself |
| Read-only trust | Observe and report only: no pushes, no reruns, no comments, no builder dispatch (section 3) |
| Two-strike rule | Two consecutive failures of the same sub-task: stop retrying it and flag (section 9) |
| No chat | The two message types of section 7 are the only user-facing messages; never chat beyond them |

## 1. Spawn the runner (invoking agent)

1. Resolve the PR: `<owner>`, `<repo>`, `<number>`, full URL, head branch (`gh pr view <pr> --json url,number,headRefName,headRepositoryOwner` from the repo when given a bare number).
2. Spawn the runner via the Agent tool: `subagent_type: general-purpose`, `model: "haiku"`, stable name `shepherd-<owner>-<repo>-<number>`. Prompt = sections 2 through 9 of this file verbatim, prefixed with the resolved PR identifiers.
3. The runner is self-paced: after every iteration it schedules its own next wake-up (ScheduleWakeup with the interval from section 6). Where wake-up scheduling is unavailable, drive it instead with the loop runner in self-paced mode: `/loop /pr-shepherd <url>`.

Everything below is addressed to the runner.

## 2. Setup (first iteration only)

1. **Repo profile.** Read the repo profile - the harness's per-repo project memory, one JSON file per repository at `~/.claude/profiles/<owner>-<repo>.json`. Fields needed: `trust` (full-autonomy | read-only), `base_branch`. If a field is missing: attended, ask the user once via the question selector tool and write the answer back to the profile file; unattended, use the safe default (`trust: read-only`; skip freshness if `base_branch` is unknown) and flag the assumption in every report.
2. **Builder name.** The persistent builder for a chain-built PR is `builder-<branch-slug>` - the head branch lowercased with every non-alphanumeric run replaced by a single hyphen. Derive it from `headRefName`; there is no lookup file. On a manual attach to a PR the chain did not build, do nothing yet; section 5 creates one builder on the first legit CI failure.
3. **Worktree.** Find the local checkout of the PR branch (an existing worktree from the build). If none exists and trust is full-autonomy: `git fetch origin <headRefName>` then `git worktree add <repo-root>/.worktrees/<headRefName> <headRefName>`. Never a second worktree for the same branch.
4. **Baseline.** Fetch the PR state once (section 5 step 1's full fetch) and remember it - you are a persistent agent and your transcript IS your state across iterations; nothing is written to disk. Initialize `pinged_for_sha` (in-context) to the current head SHA - the review loop's flip message (or the user's own attach decision) already covers the state at attach time, so no ping fires for it.

## 3. Trust gate

`trust: full-autonomy` enables everything below. `trust: read-only` degrades the shepherd to a watcher: it runs the state check (section 5, step 1) and the terminal handling (section 8, minus branch deletion and pushes), reports what it observes, and escalates via type 2 messages delivered to the user only - never as PR comments, never with pushes, reruns, or builder dispatch. Every read-only report states that actions were skipped due to trust.

## 4. In-context state and the quiet check (the economics)

Track in your own context - no state files, your transcript survives every
iteration and a resumed agent keeps it: `updated_at`, `head_sha`,
`ci_conclusion`, `last_comment_at`, `pinged_for_sha`, `upkeep_sha`, per-task
failure counters, `open_escalations`, and a one-line history of actions taken.
A freshly attached shepherd has no memory of the PR and simply performs the
first full fetch (section 2, step 4); that is the entire recovery story.

`ci_conclusion` is the roll-up of the head SHA's checks: `failure` when any check concluded FAILURE, `pending` when any check has not reached a terminal conclusion, otherwise `success` (all SUCCESS or SKIPPED).

The PR is **quiet** (do nothing this iteration) when its current head SHA matches the remembered `head_sha`, its CI conclusion is unchanged and not failing, and it has no comments newer than `last_comment_at`. Anything else makes it **active**. `updated_at` is a cheap pre-filter, but only when the remembered `ci_conclusion` is terminal-good (`success` or `skipped`): completing check runs do not bump a PR's `updatedAt`, so a PR remembered as pending or failing still needs the full per-PR fetch even when `updatedAt` is unchanged.

On a quiet iteration the single `gh pr view` of step 1 is the only API call made - reschedule and stop. This is what makes an idle shepherd cost effectively nothing.

## 5. Iteration

### Step 1: Cheap state check

```bash
gh pr view <url> --json updatedAt,state
```

- `state` MERGED or CLOSED: go to section 8.
- `updatedAt` equals the remembered `updated_at` AND remembered `ci_conclusion` is terminal-good: **quiet** - reschedule (section 6), zero further calls.
- Otherwise, full fetch:

```bash
gh pr view <url> --json headRefOid,baseRefName,headRefName,isDraft,mergeStateStatus,statusCheckRollup,title,body
gh api 'repos/<owner>/<repo>/pulls/<number>/comments?sort=created&direction=desc&per_page=20' \
  --jq '[.[] | {id, user: .user.login, created_at}]'
```

Derive `ci_conclusion` from `statusCheckRollup` and classify per section 4. Still quiet: remember the new `updated_at`, reschedule. Active: continue. New comments never trigger replies or review work (Boundaries); record the newest `created_at` and note them in the status line.

### Step 2: Freshness

When `mergeStateStatus` is BEHIND, refresh the branch in the worktree. Rebase onto the PR's OWN base from `baseRefName` (fetched in step 1's full fetch) - never assume the profile's trunk; the PR's actual base is authoritative:

```bash
git fetch origin
git rebase origin/<baseRefName>
git push --force-with-lease origin <headRefName>
```

Only ever the PR's own head branch. On conflict: a conflict is safely resolvable only when it sits in a generated file the repo can regenerate with a command (lockfiles, generated snapshots) - regenerate, `git add`, continue. Any other conflict: `git rebase --abort`, add the conflict to `open_escalations`, fire a type 2 message (section 7), skip the rest of this iteration.

`mergeStateStatus` DIRTY (conflicts with base) escalates the same way.

### Step 3: CI

Skip when `ci_conclusion` is `success`. When `pending`: wait in place instead of burning wake-cycles on polling - `timeout 3600 gh pr checks <url> --watch --interval 30` blocks until every check concludes, then re-derive `ci_conclusion` from the fresh result and continue this same iteration; if the timeout expires with checks still pending, reschedule short. When `failure`:

1. Collect failed logs: take failing runs from `statusCheckRollup` (or `gh pr checks <url>`), then `gh run view <run-id> --log-failed` per failing run.
2. Spawn a classification agent (Agent tool, `subagent_type: general-purpose`, `model: "sonnet"`) with the failed logs and a summary of the PR diff. It returns, per failed check: `flaky` or `legit`, with a one-line reason.
3. **Flaky**: `gh run rerun <run-id> --failed`. A check classified flaky twice in a row without an intervening pass is treated as legit from then on.
4. **Legit**: dispatch the fix to the RESUMED builder by its derived name - SendMessage with the failing check name, the relevant log excerpt, and the instruction: fix on the PR branch in its worktree, TDD for bugfixes (failing test first), commit with the git trailer `Harness-Fix: true`, push. Then reschedule short and skip steps 4 and 5 this iteration - the builder's push shows up as a new head SHA next time.
5. **No builder exists** (manual attach on a PR the chain did not build - the resume goes unanswered): spawn ONE persistent builder now - Agent tool, `subagent_type: builder` (its model comes from the agent definition; do not override), the same derived stable name `builder-<branch-slug>`. Prompt it with the PR title, body, diff summary, and the failure. Every later round derives the same name and resumes this same agent. Never spawn a fresh fixer per round.

### Step 4: Mechanical upkeep

Run only when `ci_conclusion` is `success` and the head SHA differs from `upkeep_sha`. Both tasks run as sonnet agents (Agent tool, `subagent_type: general-purpose`, `model: "sonnet"`):

1. **Lint/format autofix**: in the worktree, discover the repo's autofix commands (package scripts, Makefile targets, pre-commit hooks), run them scoped to files changed versus the base branch, and if anything changed commit `style: apply repo autofixes` with the trailer `Harness-Fix: true`, then push.
2. **Description sync**: compare `git diff <base_branch>...HEAD` against the PR body; when the diff has drifted from what the body describes (substantive changes the body does not cover), regenerate the body via the push-pr skill (it updates existing PRs, preserves the template, and never mentions automation).

Set `upkeep_sha` to the resulting head SHA.

### Step 5: Pings

Apply section 7. Fire a type 1 message when the PR is green, up to date with base, has no open escalations, and the current head SHA differs from `pinged_for_sha` - the human's last-known-good view is stale (the shepherd fixed CI or rebased since). Set `pinged_for_sha` to the head SHA after sending. At most one type 1 per head SHA, never on quiet iterations.

### Step 6: Remember and reschedule

Update your in-context state (`updated_at`, `head_sha`, `ci_conclusion`, `last_comment_at`, bookkeeping) and append one history line per action taken. Emit a one-line status (`quiet`, `rebased + pushed`, `CI fix dispatched to <builder>`, `escalated: <item>`), then schedule the next wake-up per section 6.

## 6. Pacing

The runner picks each interval from what it is waiting on:

| Situation after the iteration | Next wake-up |
|---|---|
| CI running on the current head | handled in-iteration by `gh pr checks --watch`; reschedule short only on watch timeout |
| Builder fix dispatched, awaiting new commits | 10-15 min |
| Quiet, green, waiting on the human | 30-60 min |
| Escalation outstanding (blocked on the human) | 2-4 h |
| Read-only watcher mode, quiet | 2-4 h |

## 7. Pings - the two message types

Exactly two human-facing message types exist. Deliver them via SendMessage to the main agent for the user; never chat beyond them.

| Type | Message | Fires when |
|---|---|---|
| 1 | "ready for your final review - push back or merge" | The PR is back to green-and-current after shepherd activity the human has not seen (section 5, step 5) |
| 2 | "escalated items - findings pushed back with uncertainty, your call" | A new item enters `open_escalations`: an unresolvable rebase conflict, a two-strike abandonment, or an action blocked by read-only trust |

Type 2 items are ALSO posted as a top-level PR comment whose first line is exactly:

```markdown
**Harness automated comment**
```

followed by the escalated items as a list. Skip the PR comment on read-only repos (trust forbids posting); the user still gets the message directly. Escalate each item once: only new entries in `open_escalations` fire a message; existing ones just hold the slow heartbeat.

## 8. Terminal states

### MERGED

1. **Cleanup**: `git worktree remove <path>`, `git branch -D <headRefName>`, delete the remote branch if it still exists (`git push origin --delete <headRefName>`; skip when the repo auto-deletes merged branches or trust is read-only).
2. **Learning pass**: spawn a session-model agent (Agent tool, `subagent_type: general-purpose`, NO `model` parameter so it inherits the session model) with this prompt, filled in:
   - Read the merged PR's full paper trail: PR body, all review threads and top-level comments (panel findings, triage outcomes, escalation comments, the user's own comments), the commit list with messages and `Harness-Fix` trailers, and the implementation brief at `~/.claude/state/implement/<branch-slug>/brief.md` (slug derived from the head branch) if present.
   - Read the target repo's `.claude/lessons/INDEX.md` and any lesson files this PR itself added, to know what is already captured.
   - Distill every durable lesson NOT already captured - constraints discovered mid-build, escalation resolutions, and negative lessons (panel findings the user rejected become noise-pruning rules).
   - Write each as `~/.claude/state/lessons/<owner>-<repo>/<domain>/<slug>.md` in the standard lesson format: YAML frontmatter with `name`, one-line `summary`, `domains: [list]`, `globs: [path patterns]`, then the lesson body. Update-don't-duplicate; write nothing when nothing new was learned.
   - Touch nothing in the repository: staged lessons ride the next PR for that repo - the next build commits them into `.claude/lessons/` and regenerates `INDEX.md`.
3. Delete the brief directory `~/.claude/state/implement/<branch-slug>/` after the learning pass completes.
5. **Final report** to the main agent: actions over the PR's life (from `history`), flags raised, lessons staged. Then cancel any scheduled wake-up and stop.

### CLOSED (not merged)

Report to the main agent that the PR was closed, with the action history. Leave the branch and worktree in place (the PR may be reopened). Cancel any scheduled wake-up and stop.

## 9. Failure handling (two-strike rule)

Track consecutive failures per sub-task in your in-context counters (keys like `rebase`, `rerun`, `ci-fix:<check>`, `lint`, `description-sync`). A success resets its counter to zero. At two consecutive failures of the same sub-task: stop retrying it, add it to `open_escalations`, fire a type 2 message, and keep running the other duties. The abandoned sub-task becomes eligible again only when the PR's head or base moves (reset its counter then).
