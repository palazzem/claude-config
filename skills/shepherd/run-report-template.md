<!--
Run report template — /shepherd.
Contract:
- Printed in the session at every terminal (MERGED / CLOSED / NO-CHANGE / FAILED). Never posted, never committed, never saved anywhere.
- All five sections, in this order, always present — a section with nothing to report says `none`.
- Facts come from the run record — PR body, commits, threads, posted reviews, marked comments on the input issue — plus the session itself.
- Lessons come exclusively from the human's feedback during this run — never from agent output, and nothing to do with auto-memory.
- Replace each guidance line as you fill a section; delete this comment too.
-->

**Run report — #<issue> <title> — <MERGED | CLOSED | NO-CHANGE | FAILED>**

- **Lane:** _confirmed type → lane, e.g. `spec → full (confirmed at /deliver)`_
- **Stages:** _the stages this run actually executed, in order, with loop counts where one repeated, e.g. `design (2 skeptic rework loops) → implement → review-panel → shepherd`_
- **Halts:** _one entry per halt, `·`-separated: what fired → how the user ruled; `none` when the run never halted_
- **Review loops:** _panel: rounds, findings count, dispositions — n fixed, n contested (who prevailed), n deferred → #tracking-issue · human: rounds, comments, disposition_
- **Lessons** (from human feedback only): _one entry per lesson: what the human corrected → the takeaway; `none` when the human changed nothing_
