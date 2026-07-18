# Cross-Cutting Anti-Patterns — Seed Library

Stack-agnostic failure patterns distilled from real production incidents, stripped of any
specific technology. This is the SEED that grounds the `qa-domains` personas; it does not
grow by mining git history (a poison loop that relearns existing mistakes as correct). It
grows only through the defined lessons layer — real post-merge escapes append repo-specific
patterns to the target repo's lessons, and generic patterns are appended here.

Each entry: **what it is**, **why it bites**, **review signals**.

---

## 1. Unbounded operations

**What it is.** A loop, fetch, retry, cache population, or resource allocation with no
ceiling — it processes or allocates as much as the input happens to demand.

**Why it bites.** It works on median data and fails on the outlier: the tenant with a
million rows, the retry that never stops, the cache that loads the whole table into memory.
The failure is an OOM, a pool exhaustion, or a runaway cost, and it appears only in
production on the largest account.

**Review signals.**
- Data loading, cache population, or fan-out sized by customer/tenant volume without
  pagination or streaming.
- Retry loops without a maximum attempt count.
- Queries without a bounded range (date, id, limit).
- Connection or task creation inside a loop without a pool cap.

---

## 2. Fail-silent defaults

**What it is.** A default value or fallback that keeps the system running while doing the
wrong thing — a selector matching zero targets, a filter returning empty, an error
swallowed, a config default that quietly degrades.

**Why it bites.** There is no error, no alert, no crash — just wrong behavior served
indefinitely until a human notices the symptom hours or days later. The absence of a
failure signal is the failure.

**Review signals.**
- `except`/`catch` blocks that swallow without logging, re-raising, or alerting.
- Default values that match nothing or return empty on a lookup miss.
- Operations that skip silently when a precondition is unmet.
- Missing error propagation across a boundary (a failed sub-operation the caller never
  learns about).

---

## 3. Client-side-only enforcement

**What it is.** An access, targeting, or filtering rule enforced only in the UI or client
SDK, with no matching enforcement on the server.

**Why it bites.** The client is fully controllable by the user. Anything gated only there
is bypassable by anyone who edits a request — the "hidden" feature is served, the "filtered"
data is returned, the "disabled" action executes.

**Review signals.**
- Feature flags, permissions, or visibility decided in frontend/SDK code with no server
  counterpart.
- Filtering applied after the server returned the full dataset.
- "Targeting" or "audience" logic that lives only client-side.
- Validation present on the client but absent on the server handler.

---

## 4. Single-service testing of multi-service changes

**What it is.** A change that spans a boundary (serialization format, shared table, API
contract) tested only against the service that changed, not the downstream consumers.

**Why it bites.** The producer's tests pass because the producer is internally consistent.
The consumer — often in another language with a stricter decoder — breaks in production
during the deploy window, and nothing in CI saw it.

**Review signals.**
- Serialization/format changes with tests only on the writer.
- Shared-table schema changes without a test exercising the other writer/reader.
- Contract changes without an integration test crossing the actual boundary.
- Cache/queue format changes without a test reading already-written data.

---

## 5. Manual deployment steps

**What it is.** A deployment or fix that depends on a human remembering to do something — an
approval gate, a publish button, a cache-warm command, a follow-up migration.

**Why it bites.** The manual step gets skipped. The fix that "shipped" never actually
deployed; the code merged but the artifact was never published. Detection is a fresh
incident on top of the original.

**Review signals.**
- CDN/artifact publishing that requires a manual approval or button-press.
- Multi-step deploys where a later step is documented in a comment, not automated.
- "Remember to run X after deploy" in a PR description.
- Cache warming, index building, or backfill left as an out-of-band manual task.

---

## 6. Environment asymmetry

**What it is.** A configuration or infrastructure difference between environments or regions
such that a change behaves differently in one than another.

**Why it bites.** It passes in dev and staging, then breaks one production region because
that region's topology, scale, or config differs. The incident is confined to where the
asymmetry lives, making it slow to diagnose.

**Review signals.**
- Config values that differ per environment/region without a clear reason.
- Infrastructure changes (networking, mesh, DNS) tested only in a lower environment.
- Hardcoded assumptions about scale, topology, or available services.
- Feature enabled in one environment's config but not another's, with no parity check.

---

## 7. Shared infrastructure without isolation

**What it is.** A cache, queue, database, or connection pool shared across services or
tenants without per-consumer resource limits or isolation.

**Why it bites.** One consumer's spike becomes everyone's outage — blast radius by default.
A runaway job on the shared cache evicts every other service's entries; a flood on the
shared queue starves every other consumer.

**Review signals.**
- A critical service reading/writing the same cache or queue as best-effort background
  work, with no quota.
- Connection pools shared without per-caller limits.
- No rate limiting or quota between tenants on a shared resource.
- Bulk/background operations running against the same instance that serves the hot path.

---

## 8. Monitoring blind spots

**What it is.** Missing observability for a failure mode the change introduces — no alert on
a new service, no metric on cold/historical data, no visibility into queue backlog or
storage internals.

**Why it bites.** The failure happens and nothing signals it. Detection depends on a user
complaint, producing multi-hour gaps. What you cannot see, you cannot page on.

**Review signals.**
- New service, endpoint, or job with no alerting.
- Monitoring that covers only hot/incoming data, not historical/cold integrity.
- Operations that drop, truncate, or reject without recording that they did.
- Crash-loop or idle-period metrics that can read as healthy while broken.
- No dashboard/metric for a new queue, pool, or backlog the change creates.

---

## 9. Missing idempotency on side effects

**What it is.** An operation producing an external side effect (email, webhook, payment,
notification, external write) without an idempotency key or dedupe guard.

**Why it bites.** Delivery is at-least-once in every real system. Retries, redeliveries, and
"stalled job" resets all re-run the side effect: duplicate emails, double charges, repeated
webhooks. Exactly-once is a design you build, not a default you get.

**Review signals.**
- Side-effect calls in a retryable path with no idempotency key.
- Job reapers or "stalled" resets without a retry cap.
- Queue consumers without dedupe on redelivery.
- External writes that assume they run exactly once.

---

## 10. Retry amplification

**What it is.** Retry or fallback logic without a circuit breaker, backoff, and jitter, so
retries pile load onto a dependency that is already struggling.

**Why it bites.** A transient blip triggers retries across many callers simultaneously; the
synchronized retry storm (thundering herd) drives the wounded dependency fully down and
keeps it down. One slow service cascades into a fleet outage.

**Review signals.**
- Retry logic with no circuit breaker.
- Fixed-interval retries without exponential backoff and jitter.
- Fallback chains where every caller retries the same failing layer.
- No cap on total retry attempts or total in-flight retries.

---

## 11. N+1 patterns

**What it is.** Code that issues one query/request per item in a collection instead of one
batched or joined operation — including the subtle admin/list-surface variant where a new
foreign key fires a full-table lookup per rendered row.

**Why it bites.** It is invisible at small scale and quadratic at large scale: fine on ten
rows in the test, a latency and load incident on ten thousand in production. On shared
infrastructure it also amplifies blast radius.

**Review signals.**
- Queries or remote calls inside a loop over a collection.
- A new relation on a list/detail/admin surface without a bounded lookup widget.
- Serialization that lazily loads a related object per element.
- Missing batch/join/prefetch where the access pattern is clearly one-per-item.

---

## 12. Loose dependency pinning

**What it is.** Dependency constraints expressed as ranges (`>=`, `^`, `~`) rather than
exact pins, or unpinned CI actions and base images.

**Why it bites.** The build resolves to whatever the registry serves at build time, so a
compromised or breaking upstream release enters without any code change of yours. It widens
the supply-chain attack surface and makes builds non-reproducible.

**Review signals.**
- Version constraints loosened from exact to range.
- New dependencies added with a range specifier.
- CI actions or base images referenced by mutable tag rather than pinned digest/version.
- Lockfile changes that broaden rather than pin resolved versions.

---

## Growth

This library is a seed, not a ceiling. New generic patterns are appended here through the
lessons layer when a real post-merge escape reveals a stack-agnostic failure class.
Repo-specific patterns never land here — they go to the target repository's
`.claude/lessons/` (P2). Personas load the matching repo lessons in addition to this seed at
review time.
