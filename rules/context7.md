# Rule: Search Documentation

Answer library, framework, SDK, API, CLI, cloud-service, version, configuration, and debugging questions from current documentation. Delegate the complete question (including version and exact lookup) to `docs-researcher` using the native agent mechanism. Keep citations and UNVERIFIED flags in its report. Resolve ambiguity with the user when alternatives materially change the answer.

If native delegation is unavailable, explicitly report that limitation and follow the same research-only contract yourself: use the locked Context7 CLI, then authoritative official documentation as fallback. Never silently substitute memory for verification. Do not send credentials, private code, or personal data in queries. Model IDs, tool permissions, and host lifecycle mechanics belong to native adapters.
