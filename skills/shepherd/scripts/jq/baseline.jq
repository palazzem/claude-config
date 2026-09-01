include "lib";
{ comment: newest(.comments.nodes[]),
  review:  newest(.reviews.nodes[]),
  reply:   newest(.reviewThreads.nodes[].comments.nodes[] | select(submitted)),
  merge:   merge_state,
  ci:      ci_state,
  state:   .state }
