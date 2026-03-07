"""normalize runtime settings user memory into json lists

Revision ID: 0025_user_memory_json_list
Revises: 0024_entity_root_accounts
Create Date: 2026-03-07
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0025_user_memory_json_list"
down_revision: str | None = "0024_entity_root_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LIST_PREFIXES = ("- ", "* ", "+ ")


def _normalize_text(raw: str | None) -> str | None:
    normalized = " ".join((raw or "").split()).strip()
    return normalized or None


def _normalize_item(raw: str | None) -> str | None:
    normalized = _normalize_text(raw)
    if normalized is None:
        return None
    for prefix in _LIST_PREFIXES:
        if normalized.startswith(prefix):
            normalized = _normalize_text(normalized.removeprefix(prefix))
            break
    return normalized or None


def _normalize_items(raw_value: object) -> list[str]:
    if raw_value is None:
        return []
    if isinstance(raw_value, list):
        raw_items = [str(item) for item in raw_value]
    else:
        normalized_text = str(raw_value).replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized_text:
            return []
        try:
            decoded = json.loads(normalized_text)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, list):
            raw_items = [str(item) for item in decoded]
        else:
            raw_items = normalized_text.split("\n")

    items: list[str] = []
    seen_keys: set[str] = set()
    for raw_item in raw_items:
        item = _normalize_item(raw_item)
        if item is None:
            continue
        item_key = item.casefold()
        if item_key in seen_keys:
            continue
        seen_keys.add(item_key)
        items.append(item)
    return items


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, user_memory
            FROM runtime_settings
            WHERE user_memory IS NOT NULL
            """
        )
    ).mappings()
    for row in rows:
        items = _normalize_items(row["user_memory"])
        bind.execute(
            sa.text(
                """
                UPDATE runtime_settings
                SET user_memory = :user_memory
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "user_memory": json.dumps(items, ensure_ascii=False) if items else None,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, user_memory
            FROM runtime_settings
            WHERE user_memory IS NOT NULL
            """
        )
    ).mappings()
    for row in rows:
        items = _normalize_items(row["user_memory"])
        bind.execute(
            sa.text(
                """
                UPDATE runtime_settings
                SET user_memory = :user_memory
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "user_memory": "\n".join(items) if items else None,
            },
        )