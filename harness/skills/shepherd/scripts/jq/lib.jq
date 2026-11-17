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

# mergeStateStatus says BEHIND only when the base branch rule requires up-to-date
# heads; the base-to-head comparison sees a moved base regardless.
def merge_state:
  if .mergeStateStatus == "DIRTY" then "DIRTY"
  elif .mergeStateStatus == "BEHIND" or ((.baseRef.compare.behindBy // 0) > 0) then "BEHIND"
  else .mergeStateStatus end;

def newest(s): [s | .updatedAt] | max // $epoch;

def submitted: .pullRequestReview.state != "PENDING";

def unmarked:
  ((.body // "") | ltrimstr("﻿") | gsub("^\\s+"; "") | startswith($marker)) | not;
