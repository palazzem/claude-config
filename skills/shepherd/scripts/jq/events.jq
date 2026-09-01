include "lib";
def ev($e; $b):
  select(.updatedAt > $b and unmarked)
  | { event: $e, url: .url, login: .author.login, assoc: .authorAssociation, at: .updatedAt };

(.comments.nodes[] | ev("COMMENT"; $comment)),
(.reviews.nodes[]
  | select((.body // "") != "" or .state != "COMMENTED")
  | . as $r | ev("REVIEW"; $review) | .state = $r.state),
(.reviewThreads.nodes[].comments.nodes[] | ev("THREAD_REPLY"; $reply))
