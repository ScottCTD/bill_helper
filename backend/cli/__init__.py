# CALLING SPEC:
# - Purpose: define package exports and module boundaries for `backend/cli`.
# - Inputs: callers that import `backend/cli/__init__.py`.
# - Outputs: package marker for the `bh` CLI package.
# - Side effects: import-time package wiring only.
"""Agent-first `bh` CLI package."""
