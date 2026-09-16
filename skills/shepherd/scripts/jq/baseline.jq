include "lib";
{ comment: newest(.comments.nodes[]),
  review:  newest(.reviews.nodes[]),
  reply:   newest(.reviewThreads.nodes[].comments.nodes[] | select(submitted)),
  merge:   merge_state,
  ci:      ci_state,
  state:   .state,
  head:    (.headRefOid // "UNKNOWN"),
  seen: {
    comment: boundary_versions(.comments.nodes[]),
    review: boundary_versions(.reviews.nodes[]),
    reply: boundary_versions(.reviewThreads.nodes[].comments.nodes[] | select(submitted))
  } }
