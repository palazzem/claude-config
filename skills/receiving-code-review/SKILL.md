---
name: receiving-code-review
description: Use whenever review feedback is being handled - before implementing any reviewer suggestion, when triage findings arrive at a builder, when the user relays review comments, or when feedback seems unclear or technically questionable. Verification-first evaluation, never performative agreement or blind implementation.
---

# Receiving Code Review

Review feedback is a set of claims to evaluate, not orders to follow. This discipline applies to every source: triage findings dispatched to a builder, comments the user relays, any external reviewer, human or automated.

## The loop

1. **Read** the complete feedback without reacting.
2. **Restate** each item's technical requirement in your own words. If any item is unclear, stop and ask before implementing anything - items may be related, and partial understanding produces wrong implementations.
3. **Verify** against the codebase: read the code the feedback is about. Is the claim true here? Would the suggestion break existing behavior? Is there a reason the current implementation is the way it is?
4. **Evaluate** the suggestion optimal-first (below).
5. **Respond or implement** - one item at a time, testing each; or push back with evidence.

## No performative agreement

Banned: "You're absolutely right", "Great point", "Good catch", any expression of gratitude, any agreement issued before verification. Actions over words: state the technical requirement, ask the clarifying question, push back with reasoning, or just make the fix - the diff itself is the acknowledgment. When feedback is correct, the full response is the fix plus one factual line about what changed.

## Severity-calibrated push-back burden

Severity calibrates the burden of proof required to push back - it never dictates blind implementation.

| Severity | Default | To push back |
|---|---|---|
| CRITICAL / HIGH | implement | Concrete codebase evidence: code references, test output, or an architectural constraint that proves the finding wrong or harmful. Logic alone is not sufficient |
| MEDIUM | consider | Logical reasoning suffices: does not apply in this context, YAGNI, trade-off not worth it |
| LOW / NIT | nothing to evaluate | n/a |

Push-back is always explicit and carries its reasoning. Never silently drop a finding.

## Autonomy ladder (autonomous mode)

When handling feedback without a human in the loop, every verified item lands on exactly one rung:

1. **Just do it** - the outcome is unambiguously better and there is essentially one sensible way to get there. Implement and record.
2. **Do it and flag the alternative** - more than one reasonable solution exists. Make the call, implement, and record the reasoning plus the alternative considered so the decision can be redirected cheaply.
3. **Stop and ask** - genuinely unclear which outcome is better, a design decision is required, or doubt about safety is itself the signal. Escalate with the uncertainty stated; never guess.

## Optimal-first evaluation

Evaluate every suggestion by outcome quality only - correctness, security, maintainability, performance, operability - never by implementation effort. A reviewer proposing a band-aid over a structural problem gets pushed back with the green-field alternative: name the structural fix, state why the band-aid entrenches the problem, and propose the better option even when it is the bigger change. Never accept a suboptimal patch because it is smaller.

## YAGNI scope check

When a reviewer suggests "implementing X properly", grep the codebase for actual usage first. Unused: propose removal instead ("nothing calls this - remove it?"). Used: then implement it properly. YAGNI governs scope (no unrequested features), never structure (never keep a bad design to avoid change).

## Verification limits

If a claim cannot be verified with what is available, say so and ask for direction instead of proceeding on faith: "cannot verify without X - investigate, ask, or proceed?"

## Correcting your own push-back

If you pushed back and were wrong, state it factually and move on: "Verified - the finding is correct: <what you checked, what it showed>. Fixing." No extended apology, no defense of the original push-back, no over-explanation.

## GitHub mechanics

- Replies to threads opened by HUMANS come only via the user, or from you as the PR author addressing feedback on your own PR. Automated triage never replies to human threads.
- When replying as the PR author, reply IN the comment thread (`gh api repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies`), never as a top-level PR comment.
- Any comment posted autonomously (not directed by the user) begins with the exact first line `**Harness automated comment**`.
- The no-performative-agreement rules apply verbatim in thread replies.
