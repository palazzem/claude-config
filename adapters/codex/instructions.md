# Codex adapter

Use native custom-agent spawning for `docs-researcher`; inspect effective sandbox permissions and keep research read-only. If delegation is unavailable, report the gap and follow the shared documented fallback. Do not translate Claude model IDs or permission allowlists.

Use `$spec`, `$plan`, `$build`, `$test`, `$constraints`, `$review`, `$webperf`, `$code-simplify`, and `$ship` for lifecycle wrappers. Each loads its original command from the registered, pinned agent-skills plugin package. Native `/plan` and `/review` remain client commands. Do not create duplicate upstream skills or rename them.

Shepherd runs during the active task and resumes explicitly from persisted state; ending the task does not promise automatic wake-up.
