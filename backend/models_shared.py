# CALLING SPEC:
# - Purpose: provide the `models_shared` module.
# - Inputs: callers that import `backend/models_shared.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `models_shared`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def uuid_str() -> str:
    return str(uuid4())

