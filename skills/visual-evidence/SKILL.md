---
name: visual-evidence
description: Capture screenshots and a GIF of the key interaction as visual evidence for frontend PRs. Invoked by the implement chain's review loop when the PR changes UI, or manually on any PR. Re-captures when the PR HEAD moves. Produces before/after pairs when behavior changed and embeds everything in one upserted PR comment.
---

# Visual Evidence for Frontend PRs

Prove UI changes visually: one screenshot per reachable state of every affected
screen, a GIF of the key interaction, before/after pairs when behavior changed.
Evidence is published as a Claude Code artifact — one page per PR, the SAME
artifact URL across re-captures — and linked from a single upserted PR comment.
Nothing is ever committed to the repository.

## Trigger

- **Automatic**: invoked by the review loop's owner (the implement skill) when
  the PR's diff changes user-facing UI (routes, pages, components, styles),
  whenever the PR HEAD differs from the SHA recorded in the evidence comment.
- **Manual**: `/visual-evidence` on any PR, any repo.

## Runtime inputs

Nothing is stored: every fact is derived at run time. The base branch comes from
the PR (`gh pr view --json baseRefName`). The launch command is discovered from
the repository (package manifest scripts, README, Makefile, container files); if
it cannot be determined confidently, ask the user once via the question selector
- in an unattended run, skip capture and flag "visual evidence skipped - launch
command unknown" in the report.

## Steps

1. **Resolve inputs.** Determine PR number, current
   `HEAD_SHA` (`gh pr view <n> --json headRefOid -q .headRefOid`), and the
   evidence working directory in the session scratchpad (capture files feed
   the artifact; nothing lands in the repository).

2. **Staleness check.** Find the existing evidence comment (hidden marker
   `<!-- visual-evidence -->`); it records the SHA it was captured for. Same
   SHA as the current HEAD: stop, evidence is current. Different or no
   comment: proceed to re-capture.

3. **Derive the capture plan from the diff.** Read `git diff <base_branch>...HEAD`
   and map changed routes, pages, and components to the screens that render them.
   For each affected screen list the states to capture: empty, loading, error,
   populated — only where reachable (do not fabricate states the app cannot
   enter). Pick the single key interaction the PR changes (the flow a reviewer
   would manually click through) for the GIF. Note whether the PR CHANGES
   existing behavior (before/after needed) or only ADDS new surface (after only).

4. **Spawn the capture runner** — a general-purpose agent via the Agent tool.
   Pass it the capture plan, the launch command, and the output
   directory. The runner:
   1. Starts the app with the launch command and waits for readiness.
   2. Drives it with playwright via npx (`npx playwright ...`; browsers are
      expected in the local cache — run `npx playwright install chromium` if not).
   3. Captures one screenshot per screen/state from the plan
      (`page.screenshot`), named `<screen>-<state>.png`.
   4. Records the key interaction with playwright video recording
      (`recordVideo` context option), then converts the resulting webm to GIF
      using playwright's bundled ffmpeg (locate the `ffmpeg-*` binary in the
      playwright browsers cache; if absent, `npx playwright install ffmpeg`):
      `ffmpeg -i interaction.webm -vf "fps=10,scale=960:-1:flags=lanczos" -loop 0 interaction.gif`
   5. Returns the file list plus any states it could not reach (recorded in the
      manifest, never silently dropped).

5. **Before/after pairs** — only when step 3 found changed behavior. Create a
   worktree at the PR's base branch (`git worktree add <scratch>/base <base-branch>`),
   run the same capture plan there via the runner (same screens/states), store as
   `before-<screen>-<state>.png` next to the `after` shots, remove the worktree.

6. **Build and publish the evidence page** — one self-contained HTML file in
   the scratchpad: per-screen sections with each state's screenshot,
   before/after grids where behavior changed, the key-interaction GIF, and an
   unreachable-states list with reasons. Every image embedded as a `data:` URI
   (artifact pages block external requests). Keep it light: screenshots capped
   at 1280px wide, GIF at 960px / 10fps / a short loop — compress before
   embedding. Publish with the Artifact tool: title `PR <n> visual evidence -
   <repo>`, a STABLE file path per PR so every re-capture redeploys the SAME
   artifact URL. The tool requires an emoji favicon parameter — that is a
   browser-tab icon, exempt from the no-emoji text rule; keep it constant
   across redeploys. Artifact pages are private to the user by default, which
   fits the director model; on org repos other reviewers cannot open the link,
   so the comment's text summary must stand on its own.

7. **Upsert the evidence comment.** Exactly ONE comment per PR, identified by the
   hidden marker. Search existing comments for `<!-- visual-evidence -->`;
   found: edit it, not found: create it. Body layout:

   ```markdown
   **Harness automated comment**
   <!-- visual-evidence -->

   Visual evidence for <short-sha>: <artifact URL>

   | Screen | State | Before | After |
   |---|---|---|---|
   | ... | ... | captured / - | captured |

   (unreachable states, with reasons, if any)
   ```

   The recorded `<short-sha>` is the re-capture key: the review loop
   compares it with the PR HEAD after each fix round and re-invokes this skill
   when they differ. Re-capture ends when the loop does — after the PR flips
   OPEN, evidence is refreshed only by a manual invocation.

## Rails

- If the PR comment cannot be posted (no comment access), report the artifact
  link and the summary table to the user directly instead.
- Never merge, close, or modify anything in the repository; the evidence
  comment (and the artifact) are this skill's only outputs.
- If the app fails to launch twice, stop retrying: report the failure and the
  launch output instead of posting partial evidence.
- The artifact page IS the storage (user ruling): no evidence files are ever
  committed to the repository.
