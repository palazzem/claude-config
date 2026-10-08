---
name: deliver
description: Delivers an approved spec as pull requests ready for a human to review and merge, one concern per PR. Use when a spec exists and the user wants it built and published in one run instead of stepping through `/plan`, `/build`, `/code-simplify`, `/review`, and `/ship` by hand, or to resume a delivery that stopped. Not for writing the spec — run `/spec` first — and not for building one task at a time under the user's eye, which is `/build`.
---

# Deliver

## Overview

One workflow takes a spec to pull requests under watch, whatever the number of layers: a delivery is a stack of layers — one PR, one concern each — and every layer is reviewed exactly once, by its position. The human who merges gets small PRs, and no review is paid for twice.

## When to Use

- A spec exists and the change should be built and published in one run.
- A delivery stopped: re-invoke to resume it (see Resuming).
- Not without a spec: stop and tell the user to run `/spec`. Not for a PR already published, which is `shepherd`; not for one task at a time, which is `/build`.

## Definitions

| Term | Meaning |
|---|---|
| `<spec-dir>` | The directory of the spec path given as the skill's argument, in the main checkout. It holds every artifact. |
| `<trunk>` | The repository's default branch. Ranges use `origin/<trunk>`; `gh` commands take `<trunk>`. |
| `<base>` | The branch a layer builds on: the layer below, or `origin/<trunk>` for the bottom layer. |
| `<top>` | The branch of the last layer. |
| Last layer | The top layer of the plan when its build ends with `DONE`. |
