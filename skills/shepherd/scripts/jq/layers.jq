([.[].number] | unique) as $read
| [ $read[], (.[].stack.entries.nodes[]? | .pullRequest | select(.state == "OPEN") | .number) ] | unique
| select(. != $read) | join(" ")
