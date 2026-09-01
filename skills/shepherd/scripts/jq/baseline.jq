include "lib";
{ comment: newest(.comments.nodes[]),
  review:  newest(.reviews.nodes[]),
  reply:   newest(.reviewThreads.nodes[].comments.nodes[]),
  merge:   .mergeStateStatus,
  ci:      ci_state,
  state:   .state }
