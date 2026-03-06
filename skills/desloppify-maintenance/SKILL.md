---
name: desloppify-maintenance
description: Run this repository's desloppify-driven code health workflow when the user explicitly asks to use desloppify, improve the strict/objective score, work through `desloppify next`, or run a debt-reduction/refactor campaign. Use `uv run desloppify ...`, review excludes before applying them, follow scan/next instructions as the source of truth, record durable fix batches in dated fix-log docs under `docs/exec-plans/completed/`, and rerun the repo verification gates.
---

# Objective

Improve the codebase honestly through the repo's desloppify workflow. The tool's queue is the source of truth; do not replace it with ad hoc prioritization.

# Core Rules

1. Use `uv run desloppify ...` for all invocations in this repository.
2. Ask before excluding questionable directories. Only exclude obvious generated/runtime/vendor/build output on your own.
3. Use `scan` and `next` as the primary loop. If scan says review/plan work is required, do that first.
4. Fix root causes, not scores. Avoid mass `wontfix` or cosmetic churn.
5. After each durable fix batch, record the finding, concrete fix, and prevention rule in a dated fix-log doc under `docs/exec-plans/completed/`.

# Setup

If desloppify is not installed in the environment, use:

```bash
uv add "desloppify[full]"
uv run desloppify update-skill codex
```

# Workflow

## 1. Exclude review

Before scanning:

- Inspect directories that look like generated output, vendored code, local runtime state, benchmark artifacts, worktrees, or caches.
- Exclude obvious non-source paths with `uv run desloppify exclude <path>`.
- Bring questionable candidates back to the user before excluding them.

Typical obvious candidates:

- build outputs (`dist/`, `build/`, generated bundles)
- vendored dependencies
- runtime artifacts (`logs/`, `.playwright-cli/`, `output/playwright/`)
- local tool state (`.desloppify/`, scorecards)

## 2. Scan and follow tool guidance

Start with:

```bash
uv run desloppify scan --path .
uv run desloppify next
```

Rules:

- Treat scan output and `next` instructions as authoritative.
- If scan reports stale subjective review coverage or tells you to run `review`, follow that path before chasing strict-score deltas manually.
- Use `plan` only to cluster/reorder related work when the queue is clearly improvable.

## 3. Main execution loop

Repeat:

```bash
uv run desloppify next
```

For each item:

1. Fix the code properly.
2. Run the exact `desloppify resolve ...` command the tool prints.
3. Batch related fixes before rescanning unless the tool explicitly tells you to rescan sooner.

Useful supporting commands:

```bash
uv run desloppify next --count 10
uv run desloppify plan
uv run desloppify plan cluster create <name>
uv run desloppify plan reorder <pattern> top
uv run desloppify show <pattern>
uv run desloppify show --status open
```

## 4. Repo-specific verification

For behavior/schema/tooling changes, run:

```bash
OPENROUTER_API_KEY=test uv run --extra dev pytest backend/tests -q
uv run python scripts/check_docs_sync.py
```

Add more targeted verification when the touched area needs it (frontend build, Playwright smoke, migration tests, etc.).

## 5. Integration work

If the user asks for rebases or mainline integration during a large cleanup:

- checkpoint the current refactor state first
- rebase onto the requested base
- resolve conflicts
- rerun the relevant verification suite
- rerun smoke tests if user-facing flows may have shifted

# Local Artifacts

Desloppify writes local state such as `.desloppify/` and `scorecard.png`. Keep those out of commits unless the user explicitly asks otherwise.
