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
