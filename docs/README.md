# Documentation Index

This folder contains the source-of-truth documentation for the current MVP implementation.

## Contents

- `architecture.md`: system architecture, runtime flow, and design decisions.
- `agent-billing-assistant.md`: billing assistant agent architecture, prompts, and tools (descriptions, arguments, expected outputs).
- `high-level-data-flow.md`: system-level graph model, storage layout, and end-to-end data flows.
- `repository-structure.md`: directory and file-level map of the current codebase.
- `backend.md`: backend package responsibilities and behavior.
- `frontend.md`: frontend package responsibilities and behavior.
- `api.md`: REST API contract reference for `/api/v1`.
- `data-model.md`: relational schema and domain modeling rules.
- `development.md`: local setup, build/test commands, and contributor workflow.
- `documentation-system.md`: source-of-truth ownership matrix and anti-drift workflow.
- `feature-entry-lifecycle.md`: focused entry-domain flow map.
- `feature-dashboard-analytics.md`: focused dashboard analytics flow map.
- `feature-account-reconciliation.md`: account table workflow, snapshot checkpointing, and reconciliation semantics.
- `adr/README.md`: architecture decision record process and index.
- `../benchmark/README.md`: agent import benchmark framework for evaluating LLMs on statement-to-entry extraction.

Historical implementation docs:

- `completed/*.md`: closed implementation plans and migration notes. These are archival and not source-of-truth for current behavior.
- `todo/*.md`: active/planned proposal notes that are not source-of-truth behavior docs.
- `todo/account_markdown_notes.md`: proposal for adding account-level markdown notes editing (parity with entries).
- `todo/agent_review_workflow_frontend_refactor.md`: proposal for pending-proposal editing workflow and review UX/tool-call transparency refactor.
- `completed/entry_group_graph_workspace.md`: completed implementation plan for graph-first entry group workspace where group CRUD intent is handled through link operations (no first-class group CRUD).

## How To Use

1. Read `architecture.md` first for mental model.
2. Use `backend.md`, `frontend.md`, and `api.md` for implementation details.
3. Use `feature-*.md` for quickest path to high-change workflows.
4. Use `development.md` for setup and operational commands.
5. Run `uv run python scripts/check_docs_sync.py` before finalizing behavior/schema changes.
6. Keep this docs set updated whenever behavior, schema, routes, or UX changes.
