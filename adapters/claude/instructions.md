# Claude adapter

Delegate documentation research with the Agent tool and `subagent_type: docs-researcher`. The agent's `permissionMode: plan` is a requested restriction, not a security guarantee: parent auto/acceptEdits/bypass modes can override it. Verify effective permissions before research; Bash remains capable of writes, so obey the research-only contract. Report unavailable or weaker isolation explicitly.

Use the installed agent-skills plugin's existing commands and personas. Its resources remain in the native plugin package. Use native Monitor for shepherd only when available and confirmed running.
