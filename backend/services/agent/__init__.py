# CALLING SPEC:
# - Purpose: define package exports and module boundaries for `backend/services/agent`.
# - Inputs: callers that import `backend/services/agent/__init__.py` and pass module-defined arguments or framework events.
# - Outputs: package-level exports for `backend/services/agent`.
# - Side effects: import-time package wiring only.
"""Agent service package.

Import public APIs from explicit modules (for example `runtime`, `review`).
"""
