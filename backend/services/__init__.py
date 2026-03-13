# CALLING SPEC:
# - Purpose: define package exports and module boundaries for `backend/services`.
# - Inputs: callers that import `backend/services/__init__.py` and pass module-defined arguments or framework events.
# - Outputs: package-level exports for `backend/services`.
# - Side effects: import-time package wiring only.
"""Domain services for bill helper."""
