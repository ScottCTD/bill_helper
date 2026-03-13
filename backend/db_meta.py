# CALLING SPEC:
# - Purpose: provide the `db_meta` module.
# - Inputs: callers that import `backend/db_meta.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `db_meta`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared SQLAlchemy metadata without engine/session side effects."""

