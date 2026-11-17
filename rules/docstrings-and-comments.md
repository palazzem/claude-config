# Rule: Docstrings and Comments

- Every public or exported module, class, function, and method gets a docstring stating its contract — semantics, invariants, side effects, errors, an example where it helps — never a restatement of the signature. Internal code only when non-obvious. Enforce with the linter's missing-docs rule.
- Inside bodies, no comment by default. Write one only for a non-obvious WHY (hidden constraint, subtle invariant, workaround), on its own line, never inline.
