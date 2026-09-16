#!/usr/bin/env bash
# Validate a private hashed manifest; actual pruning also verifies merge/deployment.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$DIR/prune.py" "$@"
