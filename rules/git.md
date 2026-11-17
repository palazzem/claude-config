# Rule: Git Authentication

Git reaches GitHub over SSH, and the SSH agent holds no key until I load it. When a git command fails to authenticate — `Permission denied (publickey)`, or `ssh-add -l` lists no identity — stop, ask me to load the key, and rerun the same git command once I confirm. Never work around the failure: no `gh` or GitHub API call in place of the git operation, no HTTPS remote, no token.
