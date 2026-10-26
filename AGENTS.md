# Agent guide

## Workflow

Features and behaviour changes go through the full Superpowers workflow ([obra/superpowers](https://github.com/obra/superpowers), installed at the account level rather than in this repo): brainstorm, spec, plan, execute, verify, finish the branch.

- **Small fixes skip it.** A small fix is one you can state in a sentence and verify with one command (a flag, a typo, a version pin): change it, verify, commit.
- **Specs and plans are committed** under `docs/superpowers/` (`specs/`, `plans/`) on the branch they describe, so the reasoning ships with the code.
- **Each branch gets its own worktree** at `.worktrees/<branch-name>` (gitignored), cut from `main`.

## Commits and PRs

Agents commit locally; the maintainer pushes and opens PRs. Everything that reaches GitHub reads as the maintainer's own work:

- Commit messages are a single conventional-commit line (`fix: …`, `feat: …`, `chore: …`, `docs: …`) with no body or trailers.
- Branch names use the same prefixes: `fix/…`, `feat/…`, `chore/…`, `docs/…`.
- Commits, branch names, PR text and comments carry no AI attribution: no co-author trailers, no "generated with" lines, no tool or model names.
