# Rule: Stacked PR Titles and Bodies

`gh stack submit --auto` and `gh stack link` take no title or body. A layer with one commit gets that commit's subject and body; any other layer gets its branch name as the title and an empty body; a pull request template replaces the body. Decide every layer's title and body before the stack ships — the plan sets one conventional-commit subject per layer, the build writes one body file per layer.

Ship a stack in this order: `gh stack push`; per layer, bottom-up, `gh pr create --head <layer> --base <layer-below or trunk> --title "<title>" --body-file <file>`; then `gh stack link <bottom> … <top>`, which groups the existing PRs and creates nothing; verify with `gh stack view --json`. Use `gh stack submit --auto --open` only when every layer is exactly one commit.

After a layer of a published stack merges, push nothing: GitHub restacks the layers above. Fetch, reset each local layer to its remote, and rebase only to follow a trunk change from outside the stack or to fix a conflict GitHub reports.
