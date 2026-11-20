# Rule: Privacy

- Personal data from production never leaves production, in any form: not with a name swapped or fields masked, and not into a repository, an issue, a PR, a commit, a fixture, a document, or an agent's context.
- Test data is invented from scratch; it may borrow only the shape of a real record — its fields, lengths, and formats — never its values.
- Production data found outside production is a security incident.
