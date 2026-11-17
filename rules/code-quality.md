# Rule: Code Quality

- Never disable a lint rule or add a suppression or exception. Exceptions are mine to grant, with an owner and an expiry.
- Warnings are findings. Fix the cause of compiler, linter, test-runner, build, and deprecation warnings; promote warnings to errors project-wide where feasible.
- Existing code is not the quality bar. When it violates best practice, improve the pattern and migrate its neighbors — or file that migration — never introduce a third way.
- Name and place a module for the role it holds in the green-field design, never for what it holds today.
- Name a dependency by the interface the component consumes, never by what the other side does with it.
- For a feature not yet deployed, design no transition: no compatibility fields, no defaults for an older peer, no deploy-order text.
- Pin everything CI or an artifact build installs exactly: actions by commit SHA labelled with its release tag, toolchains by exact version, images by tag plus digest.
