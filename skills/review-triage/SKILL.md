---
name: review-triage
description: >
  Consume the review conversation on a PR: fetch every unresolved review
  thread, classify each into exactly one bucket (human / actionable / nit /
  ambiguous), dispatch fixes to the PR's persistent builder agent, resolve
  handled bot threads silently, and escalate genuine stop-and-ask items.
  Use when the user says "/review-triage", "triage the review comments",
  "address the review feedback", or "deal with the bot comments" on any PR
  (optional PR number or URL as argument). Also runs automatically as the
  consumption sub-step after pr-review inside the implement chain's review
  loop.
---

# Review Triage

The consumption half of the review workflow. `pr-review` generates findings;
this skill burns them down: every unresolved, non-outdated review thread ends
in exactly one bucket — HUMAN, ACTIONABLE, NIT, or AMBIGUOUS — and every
bucket has a defined outcome. Never seen-but-unhandled.

**This skill never replies to a review thread.** Not to a human's (replies to
humans come from the PR author), not to a bot's, not to its own. Handled bot
threads are resolved silently; the run report is the audit trail. The single
exception to the no-posting rule: the top-level **escalation comment** (see
Terminal step) — the only comment this skill ever posts.

Stateless by design: GitHub is the queue. Any run can crash and restart; the
unresolved threads on the PR are the complete work list.

## Dual-mode

| Mode | Entry | Behavior |
|---|---|---|
| Standalone (default) | User invokes `/review-triage` on any PR | Resolve the PR yourself; re-run `pr-review` when substantive changes exist since the last panel round; narrate each step; may ask the user via the question selector; owns the full loop through the terminal step |
| Chain sub-step | Invoked after `pr-review` inside the implement chain's review loop (the caller is the implement skill's review-loop section, run by the main agent) | The caller supplies a brief: PR number, owner/repo, head SHA, builder agent name, round number, previously escalated thread ids, and whether this is the terminal round. Skip PR resolution and panel runs (the loop owns them). Never ask the user. Return the structured report as the last output |

## Repo profile gate (Step 0)

Before touching anything, read the repo profile - the harness's per-repo project
memory, one JSON file per repository at `~/.claude/profiles/<owner>-<repo>.json`.
This skill needs `trust`:

- `trust: full-autonomy` — full behavior below: dispatch fixes, resolve
  threads, push, post the escalation comment, flip draft to open.
- `trust: read-only` — classify and report ONLY. No fixes, no resolves, no
  pushes, no comments, no `gh pr ready`. The report still buckets every
  thread so the user sees the full state.
- Field missing, standalone: ask the user once via the question selector and
  write the answer back to the profile file.
- Field missing, unattended (chain mode): default to `read-only` and add a
  flag line to the report.

Never hardcode repo names, paths, or owners anywhere in this workflow — every
repo fact comes from the profile or from `gh` at runtime.

## Narration

Standalone: emit one terse present-tense line before each step so the user can
follow without reading tool output. Chain mode: collect the same lines into
the report's `narration` array instead of printing.

Format: `[triage] <step> - <what and why>`

## Workflow

### Step 1: Resolve PR + baseline (standalone only)

If the argument looks like a PR number or URL, use it. Otherwise resolve
everything in one call and derive owner/repo from the `url` field:

```bash
gh pr view --json number,url,baseRefName,headRefOid,state,isDraft \
  --jq '{number, url, base: .baseRefName, head_sha: .headRefOid, state, is_draft: .isDraft}'
```

If the PR state is `MERGED` or `CLOSED`, there is nothing to triage — say so
and stop.

Read the last panel round marker: the `pr-review` sticky summary comment,
found by the hidden marker prefix `<!-- pr-review-summary` (full form
`<!-- pr-review-summary sha=<sha> round=<n> -->`), records the SHA the panel
last reviewed. No summary comment means the panel has never run on this PR.

### Step 2: Panel round check (standalone only)

Run `pr-review` when any of:

- no round marker exists (the panel has never reviewed this PR), or
- the diff `marker_sha..HEAD` contains substantive changes: at least one
  non-doc file (not `*.md`, `*.txt`, or pure whitespace) changed by a commit
  that does NOT carry the `Harness-Fix: true` trailer, or
- the previous triage pass of THIS invocation applied substantive fixes -
  logic or design changes, not mechanical ones (a deliberate re-round).

Excluding `Harness-Fix: true` commits is the guard against the unrequested
fix-flag-fix loop: mechanical auto-fixes never re-trigger a round on their
own. A deliberate re-round after major triage fixes is different - when
invoking `pr-review` for one, pass the round number so its own-fixes-only
skip does not cancel the requested round. Doc-only diffs never re-trigger.

Cap: at most 3 panel rounds per invocation. At the cap, proceed to triage and
then the terminal step regardless of remaining churn.

In chain mode both rules are the caller's job — never spawn the panel from a
sub-step.

### Step 3: Fetch and pre-classify threads (both modes)

Fetch all review threads, filter to unresolved and non-outdated, and trim each
body to a 1500-char head **at the jq layer** — bot review bodies can be tens
of KB each, and fetching full payloads every round is the biggest context cost
of the loop. The first few hundred chars carry the tag, severity, and finding
summary, which is enough to classify. Refetch the full body only for the
single thread you are about to action (see Step 4, ACTIONABLE).

```bash
gh api graphql -f query='
  query($owner:String!, $repo:String!, $num:Int!) {
    repository(owner:$owner, name:$repo) {
      pullRequest(number:$num) {
        reviewThreads(first:100) {
          nodes {
            id
            isResolved
            isOutdated
            comments(first:20) {
              nodes {
                databaseId
                author { login __typename }
                body
                path
                line
              }
            }
          }
        }
      }
    }
  }' -F owner=<owner> -F repo=<repo> -F num=<pr_number> \
  | jq '[
      .data.repository.pullRequest.reviewThreads.nodes[]
      | select(.isResolved == false and .isOutdated == false)
      | {
          id,
          path: .comments.nodes[0].path,
          line: .comments.nodes[0].line,
          author_login: .comments.nodes[0].author.login,
          author_type: .comments.nodes[0].author.__typename,
          first_comment_id: .comments.nodes[0].databaseId,
          body_head: (.comments.nodes[0].body[:1500]),
          body_truncated: ((.comments.nodes[0].body | length) > 1500),
          reply_count: ((.comments.nodes | length) - 1),
          participants: ([.comments.nodes[]
            | {login: .author.login, type: .author.__typename,
               automated: (.body[:200] | contains("**Harness automated comment**"))}]
            | unique)
        }
    ]'
```

Keep the raw response: a second jq pass over the same fetch (no extra API
call) lists RESOLVED threads with human participants — input for lesson
capture in Step 6.

#### Bot or human — classify every comment, not just the first

A comment is **automated** if any of:

- author `__typename == "Bot"`,
- author login ends with `[bot]`,
- author login matches a known review-bot product (contains `coderabbit`,
  `greptile`, `cursor`, `sonarcloud`, `sourcery`, `ellipsis`, `codescene`,
  `copilot`, `dependabot`) — many review bots post through plain `User`
  accounts, so the typename check alone is not enough,
- the body carries the `**Harness automated comment**` header. This is the
  load-bearing check for the harness's own posts: `pr-review` and past triage
  runs post through the user's own account (typed `User`), so the header —
  not the account — is the machine-readable bot signal.

If ANY comment in a thread is none of the above — a real person opened it or
replied in it — the whole thread is HUMAN. If you cannot confidently classify
a participant, treat them as human. Uncertain = human, always.

#### Skip stale bot reviews

Inline threads are already filtered by `isOutdated == false`. For top-level
bot review comments (summary-style reviews), SHA-sniff the body: patterns like
"reviewing commit `<sha>`", "in `<sha>`", or a `/commit/<sha>` link. If a
referenced SHA is present and differs from HEAD, skip the comment as stale —
the bot will re-evaluate the new HEAD. When in doubt (no SHA but the review
predates the latest push), prefer skipping to acting.

### Step 4: Bucket every thread

Severity calibration (from the harness severity scale):

| Finding severity | Default bucket |
|---|---|
| CRITICAL / HIGH, concrete + localized + no design decisions | ACTIONABLE |
| CRITICAL / HIGH failing any actionability test | AMBIGUOUS |
| Convergent finding (multiple reviewers, same concern) | treat as CRITICAL/HIGH |
| MEDIUM | AMBIGUOUS |
| LOW / NIT, style-only, speculative, duplicate, already addressed | NIT |

A thread is ACTIONABLE only if ALL hold:

1. Severity HIGH or CRITICAL, or a convergent finding.
2. The fix is concrete — a reader knows exactly what to change (a specific
   rename, a missing null check, a forgotten await, an off-by-one).
3. The change is localized — one file or a small set of tightly related edits.
4. Applying it requires no new design decisions, dependencies, or scope
   changes.

**Hard carve-outs — never ACTIONABLE regardless of severity:**

- Findings from the `correct-design` reviewer (design judgment). An
  auto-applied restructure is an unsupervised rewrite.
- Test-writing suggestions from any reviewer. An auto-written passing test
  encodes current behavior as correct.

For carved-out findings the only permitted outcomes are: (a) resolve with a
reasoned push-back recorded in the report — concrete codebase evidence for
CRITICAL/HIGH, logical reasoning for MEDIUM, per receiving-code-review — or
(b) escalate. Never a code change.

Handle each bucket:

**HUMAN** — never fix, never resolve, NEVER reply. Humans get replies from
the PR author only. Count as `deferred_human`, list in the report with
author, `file:line`, and a one-line gist. This rule protects the human review
conversation and applies however trivial the suggested change looks.

**ACTIONABLE** — dispatch the fix to the PR's builder (see Builder dispatch
below). If `body_truncated == true`, refetch the FULL body first — the only
path that pulls a full body into context, one thread at a time:

```bash
gh api graphql -f query='
  query($id:ID!) {
    node(id:$id) {
      ... on PullRequestReviewThread {
        comments(first:1) { nodes { body } }
      }
    }
  }' -F id=<thread_id>
```

One commit per thread, carrying the `Harness-Fix: true` git trailer. No
per-thread pushes — a single push at the end of the run (Step 5). The thread
is resolved only after that push lands. Report line: `file:line` + commit SHA
+ one-line description.

**NIT** — resolve silently via GraphQL, no reply. Record the one-line reason
in the report ("intentional - <reason>" / "out of scope - follow-up" /
"already addressed in <sha>" / "disagree - <reason>"). The report is the only
audit trail for silent resolves — never skip the reason.

**AMBIGUOUS** — run the autonomy ladder (below). Threads whose ids arrived in
the chain brief as already-escalated skip the ladder and stay ESCALATED.

To resolve a thread (the only thread mutation this skill performs), use the
gh-inline-comment skill, Mode 4 - the single source for the GraphQL
`resolveReviewThread` mutation. The thread node ids from the Step 3 fetch are
the mutation input.

#### The autonomy ladder (receiving-code-review calibration)

Applies to AMBIGUOUS bot threads only — never to HUMAN threads, never to the
hard carve-outs above. Verify the finding against the codebase before ranking
it; evaluate the suggestion optimal-first (a reviewer proposing a band-aid
over a structural fix does not get the band-aid implemented — the structural
question escalates).

1. **Just do it** — the outcome is unambiguously better and there is
   essentially one sensible way to get there (trivial, reversible). Dispatch
   to the builder, resolve after the batch push. Count as `promoted`.
2. **Do it and flag the alternative** — more than one reasonable solution
   exists. Make the call, dispatch, resolve — and the report entry MUST state
   the reasoning and the alternative considered ("did X because Y -
   alternative was Z"). Count as `promoted`. Surface these prominently, never
   folded into a bare count, so the user can redirect cheaply.
3. **Stop and ask** — genuinely unclear which outcome is better, a design
   decision is required, or the doubt itself is the signal. Count as
   `escalated`: the thread stays UNRESOLVED, the item goes into the type-2
   message and the top-level escalation comment (Terminal step) with its
   uncertainty stated.

When in doubt about whether a fix is safe to apply at all, that doubt is the
stop-and-ask signal — an escalated item is cheaper than a wrong push.

**Invariant:** every fetched unresolved thread ends in exactly one outcome —
`resolved` (nit), `actioned`, `promoted`, `escalated`, or `deferred_human` —
and the counts reconcile against the fetch. The only threads left open on
GitHub are escalated and human ones.

### Builder dispatch — resumed, never fresh

All code changes go to the PR's persistent builder agent, resumed by name via
`SendMessage`. The builder was spawned when the PR was implemented and holds
the PR's full implementation context; a fresh fixer would cold-read the diff
and lose the rationale. **Never spawn a fresh fixer for a fix round.**

- Chain mode: the brief carries the builder's agent name.
- Standalone: read `~/.claude/state/implement/<owner>-<repo>-pr-<number>.json`
  for the builder's name and resume that agent. Only if the record is missing
  (ad-hoc PR that never went through the implement chain), spawn ONCE with
  the Agent tool: `subagent_type: builder` (its model comes from the agent
  definition; do not override it), stable name `builder-<branch-slug>` - the
  head branch lowercased with every non-alphanumeric run replaced by a single
  hyphen - and a brief (PR number, branch, diff summary, link to the spec if
  any). Then write the implement state record
  (`{"builder": "builder-<branch-slug>"}`) so every later skill resumes this
  same agent. Never spawn when a record exists - that would create the second
  builder this section forbids.

Reproducers: before dispatching, read the pr-review state file
`~/.claude/state/pr-review/<owner>-<repo>-<pr>.json` and match its stored
reproducers to threads by `file:line` (or finding id). A matched reproducer
travels with the dispatch.

Each dispatch message contains: thread id, `file:line`, the FULL finding body
(refetched if truncated), the reproducer matched from the pr-review state
file if any, and the commit contract:

- **Reproducer-first**: when the finding was verified with a reproducer (a
  failing test or concrete exploit trace), the builder's fix must make that
  reproducer pass, and the suite must be green, before the fix counts as
  done.
- One commit for this thread only. Imperative subject describing the fix —
  never mention AI, Claude, or reviewers in the message. Git trailer:
  `Harness-Fix: true`.
- Commit locally, do NOT push. Reply with the commit SHA.

If the builder cannot be resumed or spawned, do not patch the code yourself —
leave the thread open, count it as `escalated` with reason "builder
unavailable", and flag it in the report.

### Step 5: Batch push, then resolve

After all dispatches for this run have reported their commit SHAs: one single
`git push` for the whole run. Then, and only then, resolve each actioned and
promoted thread via the GraphQL mutation — never resolve a thread whose fix
has not been pushed. If the push fails, no thread is resolved; report the
failure.

### Step 6: Lesson capture — repo lessons ride this PR, generic rulings grow the panel

Capture events:

| Event | Lesson |
|---|---|
| User pushes back on or overrides a triage decision (standalone) | A care-about ruling: what the user cares about, why, one worked example. `domains: [standards]` |
| User rejects a panel finding | Negative rule: "do not flag X in context Y", domain of the reviewer that produced the finding |
| Resolved thread with human participation (from the Step 3 resolved-threads pass) not yet captured | Distill the human's point into a lesson for the matching domain |

Routing - every captured ruling goes to exactly one destination:

- **Repository-specific** (it depends on this repo's code, stack, or
  conventions): a lesson in the TARGET repository's `.claude/lessons/`, per
  the convention below. It rides this PR.
- **Generalizable** (it would hold in any repository) - the panel itself
  learns, in the harness config:
  - A user push-back or override ruling: append a care-about entry (heading,
    **Care**, **Why** with the user's reasoning generalized, one worked
    **Example** drawn from the real case - zero repo-specific facts) below
    the `<!-- GROWTH-APPEND -->` marker in
    `~/.claude/skills/pr-review/reviewers/standards.md`. Update-don't-
    duplicate: a ruling that refines an existing care-about edits that entry
    instead.
  - A user-rejected finding from a qa-domains persona: append the negative
    rule ("do not flag X in context Y") to that persona's file at
    `~/.claude/skills/pr-review/reviewers/personas/<domain>.md`.
  - A user-rejected finding from any other reviewer: keep it as a negative
    lesson in the target repo (the reviewer files grow only through the two
    paths above).
  - Record every harness-config append in the run report; the harness repo's
    git history is the user's review surface for panel growth.

Convention for repository lessons (mandatory):

- File: `.claude/lessons/<domain>/<slug>.md` in the TARGET repository.
- Frontmatter: `name`, `summary` (one line), `domains: [list]`,
  `globs: [path patterns]`. Body: the lesson, why it exists, provenance (PR
  number, thread).
- Regenerate `.claude/lessons/INDEX.md` whenever a lesson is written: one
  line per lesson (summary + domains).
- Ensure the repo `CLAUDE.md` imports the index via
  `@.claude/lessons/INDEX.md`; add the import if missing.
- Check the INDEX before writing: update an existing lesson rather than
  duplicating it.

Commit repository lessons as their own commit (with the `Harness-Fix: true`
trailer), included in the Step 5 batch push. Read-only repos: skip repository
lesson capture entirely; generalizable rulings may still grow the panel files
(they touch only the harness config, never the repo).

### Step 7: Report

The report is the audit trail — silent resolves have no other record.

Standalone, print:

```
[triage] done - sha=<short_sha> panel=<ran|skip> resolved=<n> actioned=<n> promoted=<n> escalated=<n> deferred_human=<n>
```

followed by one line per thread: bucket, `file:line`, and the reason or
commit SHA (for `promoted` rung-2 items, the alternative considered; for
`deferred_human`, the author and gist). Include any profile-default flags.

Chain mode, end with exactly this structured result and nothing after it:

```json
{
  "round": 2,
  "head_sha_in": "<HEAD when this run started>",
  "new_head_sha": "<HEAD after fixes; == head_sha_in if none>",
  "resolved": 0,
  "actioned": 0,
  "promoted": 0,
  "escalated": 0,
  "deferred_human": 0,
  "substantive_fixes": false,
  "threads": [
    {"outcome": "actioned", "file": "src/foo.ts", "line": 42,
     "commit": "abc1234", "reason": "add null check on session lookup"},
    {"outcome": "escalated", "file": "src/api.ts", "line": 10,
     "reason": "two viable designs; uncertainty: retry semantics unclear"}
  ],
  "flags": [],
  "narration": ["[triage] ..."]
}
```

`substantive_fixes` tells the loop whether a panel re-round could be
warranted (non-doc fixes were applied). The loop decides; this sub-step never
spawns the panel.

### Step 8: Terminal step — flip and message

The loop terminates when no re-round is warranted (no substantive fixes, or
only mechanical ones) or the round cap (3) is hit. Standalone, this skill
detects termination itself; in chain mode the caller decides and marks the
terminal round in the brief — a brief with `terminal: true` may arrive as a
dedicated final pass after fixes: re-fetch threads (Step 3), handle any
residue, then run this step. On termination, in full-autonomy repos:

1. If any items are `escalated` (still-unresolved after the final round):
   upsert ONE top-level escalation comment on the PR — find an existing
   comment carrying `<!-- triage-escalation -->` and PATCH it, else POST it:

   ```markdown
   **Harness automated comment**
   <!-- triage-escalation -->

   Escalated review items - pushed back with uncertainty, your call:

   1. `src/api.ts:10` (security-audit, HIGH) - <one-line finding>.
      Uncertainty: <why the ladder stopped>.
   ```

   Every item states its uncertainty. This is the only comment this skill
   ever posts.
2. Flip the PR from draft to open: `gh pr ready <number>`. Draft means
   machines are iterating; open means humans are involved — the flip happens
   the moment a human-facing message fires, never before.
3. Emit exactly one human-facing message — standalone: print it; chain mode:
   include it in the report for the caller to deliver:
   - **Type 1** (nothing escalated): "ready for your final review - push
     back or merge"
   - **Type 2** (escalations present): "escalated items - findings pushed
     back with uncertainty, your call" plus the escalated list.

Read-only repos: no comment, no flip, no push — the report carries the full
classification and the would-be message instead.

Hard rails, both modes: never merge, never close, never push except the
Step 5 batch push, never `gh pr ready` except at the terminal step.

## Terminal conditions (standalone)

Stop cleanly and print the report when any of:

- PR is `MERGED` or `CLOSED`.
- Every unresolved thread has been bucketed and handled and no panel re-round
  is warranted (or the round cap is hit) — run the Terminal step, then stop.
- The user interrupts — stop at the next natural checkpoint, print the
  report.

Escalated and human threads are never a reason to keep looping: they are the
expected terminal residue, surfaced for the human.

## Dependencies and degradation

- `pr-review` — generation half; standalone Step 2 invokes it. If it is
  missing or fails, warn and still triage the existing threads: the skill
  provides value without a fresh panel round.
- Builder agent — all code fixes. Unreachable and unspawnable: escalate the
  affected threads, never patch inline.
- `gh` CLI — all GitHub interactions (REST, GraphQL, `gh pr ready`).
- No PR found (standalone): ask for a PR number or URL, then stop.
