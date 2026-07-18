# Roster map (orchestrator-only)

This file is read by the pr-review orchestrator ONLY - for backfill choices (Step 4) and
convergence handling (Step 8). Never include any part of it, or any fact from it, in a
reviewer or persona prompt: reviewers must not know the roster, that other reviewers
exist, or that convergence analysis happens downstream (byte-level independence, Step 6).

## The two security lenses

`security-audit` (deep: data-flow trace, exploit construction, one issue at a time) and
the `security-breadth` persona (wide: OWASP-style sweep across every changed surface)
intentionally overlap. Include `security-breadth` whenever the diff touches a security
surface, even if another persona already matched. When both lenses independently flag the
same issue, that dual-lens convergence is the highest-value signal the panel produces:
call it out explicitly in the sticky summary and the terminal report. Divergence between
them is expected and fine. Depth belongs to `security-audit`; `security-breadth` findings
stay at the what-and-where level.

## Persona overlap map

These overlaps are by design; convergence between overlapping personas on the same
finding raises its priority in Step 8:

| Persona | Overlaps with | High-priority convergence signal |
|---|---|---|
| `database` | `reliability` (connection pools, resource bounds, cache invalidation), `concurrency` (lock contention, transaction ordering), `api-contracts` (a shared table is a serialization boundary) | shared-table or resource-exhaustion finding |
| `api-contracts` | `security-breadth` (response shape as exposure surface), `database` (shared-table serialization), `reliability` (deployment coexistence, rollback safety), `frontend` (client-consumed contracts) | cross-language serialization change |
| `concurrency` | `reliability` (retry caps, timeouts, idempotency), `database` (transaction isolation, lock contention), `api-contracts` (message ordering across services) | missing idempotency guard for a side effect |
| `frontend` | `api-contracts` (client-consumed response shapes, SDK compatibility), `security-breadth` (client-side-only enforcement), `reliability` (stale-state serving after config change) | client-only enforcement |
| `infra` | `reliability` (monitoring, isolation, blast radius), `security-breadth` (secrets in config, pipeline trigger safety), `api-contracts` (deployment coexistence of producer/consumer) | monitoring blind spot; pipeline misconfiguration |
| `reliability` | `concurrency`, `database`, `infra`; frequently runs alongside `security-breadth` as the other default fill | unbounded operation or missing idempotency |
| `security-breadth` | `security-audit` (the deep lens - see above), `api-contracts`, `frontend`, `infra` | same issue as `security-audit` (dual-lens) |
