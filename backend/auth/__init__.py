# CALLING SPEC:
# - Purpose: define package exports and module boundaries for `backend/auth`.
# - Inputs: callers that import `backend/auth/__init__.py` and pass module-defined arguments or framework events.
# - Outputs: package-level exports for `backend/auth`.
# - Side effects: import-time package wiring only.
"""Auth package."""
