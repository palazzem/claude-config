# A cancelled run on the current head is a manual cancel, not a superseded
# push (those runs belong to the old head), and it blocks the merge box.
def ci_state:
  [ .commits.nodes[0].commit.statusCheckRollup.contexts.nodes[]?
    | if .__typename == "CheckRun" then
        if .status != "COMPLETED" then "PENDING"
        elif .conclusion == "STALE" then "PENDING"
        elif (.conclusion | IN("FAILURE", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE", "CANCELLED")) then "FAILED"
        else "OK" end
      else
        if (.state | IN("ERROR", "FAILURE")) then "FAILED"
        elif (.state | IN("PENDING", "EXPECTED")) then "PENDING"
        else "OK" end
      end ]
  | if index("FAILED") then "FAILED"
    elif index("PENDING") then "PENDING"
    elif length == 0 then "NONE"
    else "OK" end;

def newest(s): [s | .updatedAt] | max // $epoch;

def unmarked:
  ((.body // "") | ltrimstr("﻿") | gsub("^\\s+"; "") | startswith($marker)) | not;
