include "lib";
def ev($e; $b; $surface):
  select(.updatedAt >= $b and unmarked)
  | . as $source
  | select(.updatedAt > $b or
      (((($ARGS.named.seen // {})[$surface] // [])
        | any(.[]; . == ($source | activity_version))) == false))
  | { event: $e, url: .url, login: .author.login, assoc: .authorAssociation,
      at: .updatedAt, version: activity_version,
      reconcile: (.updatedAt == $b and (($ARGS.named.seen // {})[$surface] == null)) };

(.comments.nodes[] | ev("COMMENT"; $comment; "comment")),
(.reviews.nodes[]
  | select((.body // "") != "" or .state != "COMMENTED")
  | . as $r | ev("REVIEW"; $review; "review") | .state = $r.state),
(.reviewThreads.nodes[].comments.nodes[] | select(submitted) | ev("THREAD_REPLY"; $reply; "reply"))
