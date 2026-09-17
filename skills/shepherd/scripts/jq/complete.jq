# Refuse every truncated surface, including nested thread replies and checks.
def complete:
  (.pageInfo.hasPreviousPage == false and .pageInfo.hasNextPage == false);
if (.comments | complete) and (.reviews | complete)
   and (.reviewThreads | complete)
   and all(.reviewThreads.nodes[]; .comments | complete)
   and all(.commits.nodes[].commit.statusCheckRollup | select(. != null); .contexts | complete)
then . else error("incomplete GraphQL read: paginate before establishing a baseline") end
