# Groups member CLI follow-up

Status: **completed (2026-03-20).**

## Decision

We **will not** change the `bh groups add-member` / `bh groups remove-member` CLI surface. Both commands stay **JSON-only** (`--payload-json` / `--payload-file`) so the nested, discriminated proposal payload is defined in one place (contracts + reference docs), not duplicated in argparse.

An experiment with `entry` subcommands and proposal-id flags was **reverted** for that reason.

## Outcome

- Canonical payload documentation: [backend/cli/reference.py](../../backend/cli/reference.py) (`CommandSpec` for `bh groups add-member` / `bh groups remove-member`).
- Broader review of proposal/review/apply consistency (e.g. tags vs entities) is tracked in [tasks/2026_03_20-agent_review_dependency_audit.md](../../tasks/2026_03_20-agent_review_dependency_audit.md).

## Note on `git reset`

Archiving this task is a normal **move + edit** in git history; **`git reset` is not required** and would only undo uncommitted work if used carelessly. Use `git mv` or move the file and commit the rename if you want history to show the relocation clearly.
