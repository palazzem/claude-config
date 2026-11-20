# Rule: Documentation

- Architecture documents, ADRs, and design docs stay conceptual: responsibilities, boundaries, data flow, invariants, and the reasoning behind decisions. Name what is stable — concepts, contracts, protocols, external systems — never files, symbols, layouts, or code.
- Operational docs — agent instructions, constraints files, runbooks, quick-starts — name what they must, and are verified in the same change that alters what they name.
- Docs, docstrings, and comments state how the system works now — never its history, dropped alternatives, how it was found, or another document's step numbers; that reasoning goes in the commit, PR, or issue.
- An ADR states the decision and how the system behaves, never the diff from an earlier ADR or the current state of the code; code that disagrees with an ADR gets a reconciliation issue.
- Write an ADR only for a choice between alternatives with lasting consequences, never for a refactoring that converges on best practice.
- State each fact once, in the document that owns it — never repeated in an agent instructions file, another doc, or a docstring.
- An issue other than a spec fills the repository's issue form for its type: each field's label as a `### ` heading, in the form's order, with the labels the form applies. Where the repository has no form, it opens with the problem and concrete examples, never a description of the current state or a journal line, and closes with a Proposed solutions section.
- A document that is not code and needs my feedback is a Claude Doc, never a plain artifact: I comment in it, and you answer, edit, and resolve there. Once the PR that carries what it decided merges, delete it without asking: a deleted doc can be restored from its link. A spec's doc goes earlier, as the Spec rules say.
