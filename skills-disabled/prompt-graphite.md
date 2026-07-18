# Prompt: reintroduce stacked PRs with Graphite

Copy-paste this prompt to re-enable stacked-PR support across the harness once
Graphite is adopted. It restores everything that was removed when stacking was
deferred (PR review ruling, 2026-07-18).

---

Reintroduce stacked-PR support with Graphite across my harness. Prerequisites
first, then apply every file change exactly.

## Prerequisites

1. Install and authenticate: `brew install withgraphite/tap/graphite`, then
   `gt auth` with my GitHub token. Verify with `gt --version`.
2. Add a `stacking` field to the repo profile convention
   (`~/.claude/profiles/<owner>-<repo>.json`): values `graphite | none`,
   asked once via the question selector when first needed, safe default `none`
   in unattended runs.

## File changes

### skills/implement/SKILL.md

- Section 1 (Gather inputs): add `stacking` to the profile fields read here,
  with unattended default `none`.
- Section 4, the delivery step: restore stack-based delivery — "Implement the
  delivery outline as a stack of small PRs. Use Graphite (`gt`) when the repo
  profile says `stacking: graphite`: one `gt create` per delivery unit in
  outline order, `gt submit --stack --draft` to publish; a plain branch per
  unit otherwise." Interdependent units become stack units (each PR targets
  the previous unit's branch) instead of ordered commits in one PR.
- Section 5 (Push draft): PR base becomes "the profile's `base_branch`, or
  the previous stack unit's branch for upper stack PRs".
- Delivery outline wording: units map one-to-one onto stack units.

### agents/builder.md

- Working discipline: rename the "Small PRs" rule back to "Stacked small
  PRs" and note the stack follows the delivery outline order via `gt create`.

### skills/pr-shepherd/SKILL.md

- Setup: read `stacking` from the profile.
- Freshness step: when the profile says `stacking: graphite`, use Graphite
  instead of a raw rebase (`gt restack` then `gt submit`); keep the
  raw-rebase path for `stacking: none`. Keep the warning that a stacked PR
  targets the previous unit's branch, so rebasing onto the trunk would replay
  lower PRs' commits and force-push a corrupted branch — always rebase onto
  the PR's own `baseRefName`.
- MERGED terminal: restore the pre-cleanup restack step — when
  `stacking: graphite` and other PRs of the same stack are open, run
  `gt restack` then `gt submit` so branches above the merged one rebase onto
  the new base; skip on read-only trust.

### skills/push-pr/SKILL.md

- Verification-block wording: "each stacked PR's verification".
- Base-branch handling: accept the previous stack unit's branch as base for
  upper stack PRs.

### README.md

- The build workflow paragraph: work lands as stacked single-concern PRs.
- Setup section: restore the Graphite bullet (install, `gt auth` once,
  per-repo enablement via the `stacking` profile field).

## Verification

Run a two-unit feature through the chain in a test repo with
`stacking: graphite`: confirm `gt submit --stack --draft` opens two draft PRs
with the upper one targeting the lower branch, merge the bottom PR, and
confirm the shepherd restacks and resubmits the upper PR onto the new base.
