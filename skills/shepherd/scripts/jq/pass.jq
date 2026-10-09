include "lib";

def ev($e; $b):
  select(.updatedAt > $b and unmarked)
  | { event: $e, url: .url, login: .author.login, assoc: .authorAssociation, at: .updatedAt };

def activity($comment; $review; $reply):
  (.comments.nodes[] | ev("COMMENT"; $comment)),
  (.reviews.nodes[]
    | select((.body // "") != "" or .state != "COMMENTED")
    | . as $r | ev("REVIEW"; $review) | .state = $r.state),
  (.reviewThreads.nodes[].comments.nodes[] | select(submitted) | ev("THREAD_REPLY"; $reply));

def watermark:
  { comment: newest(.comments.nodes[]),
    review:  newest(.reviews.nodes[]),
    reply:   newest(.reviewThreads.nodes[].comments.nodes[] | select(submitted)),
    merge:   merge_state,
    ci:      ci_state,
    state:   .state };

def terminal: .state | IN("MERGED", "CLOSED");

def events($armed; $last):
  .number as $pr
  | watermark as $now
  | if terminal then { event: .state }
    else
      ($now.merge | select(IN("BEHIND", "DIRTY") and . != $last.merge) | { event: . }),
      ($now.ci | select(. == "FAILED" and . != $last.ci) | { event: "CI_FAILED" }),
      activity($armed.comment; $armed.review; $armed.reply)
    end
  | { event, pr: $pr } + .;

def entry($w): unseen + ($w[.number | tostring] // {});

[.[]] | sort_by(.number)
| (.[] | events(entry($armed); entry($last))),
  (map(select(terminal | not) | { key: (.number | tostring), value: watermark }) | from_entries)
