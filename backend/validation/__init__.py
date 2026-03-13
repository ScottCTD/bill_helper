# CALLING SPEC:
# - Purpose: define package exports and module boundaries for `backend/validation`.
# - Inputs: callers that import `backend/validation/__init__.py` and pass module-defined arguments or framework events.
# - Outputs: package-level exports for `backend/validation`.
# - Side effects: import-time package wiring only.
"""Shared validation helpers used across backend layers."""
