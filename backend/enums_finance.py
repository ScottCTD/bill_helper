# CALLING SPEC:
# - Purpose: provide the `enums_finance` module.
# - Inputs: callers that import `backend/enums_finance.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `enums_finance`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from enum import StrEnum


class EntryKind(StrEnum):
    EXPENSE = "EXPENSE"
    INCOME = "INCOME"
    TRANSFER = "TRANSFER"


class GroupType(StrEnum):
    BUNDLE = "BUNDLE"
    SPLIT = "SPLIT"
    RECURRING = "RECURRING"


class GroupMemberRole(StrEnum):
    PARENT = "PARENT"
    CHILD = "CHILD"


class LinkType(StrEnum):
    RECURRING = "RECURRING"
    SPLIT = "SPLIT"
    BUNDLE = "BUNDLE"
