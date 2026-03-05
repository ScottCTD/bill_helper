"""rename tag taxonomy category key to type

Revision ID: 0017_rename_tag_category_taxonomy
Revises: 0016_add_user_memory_to_runtime_settings
Create Date: 2026-03-03
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "0017_rename_tag_category_taxonomy"
down_revision: str | Sequence[str] | None = "0016_add_user_memory_to_runtime_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_KEY = "tag_category"
_NEW_KEY = "tag_type"
_OLD_DISPLAY = "Tag Categories"
_NEW_DISPLAY = "Tag Types"


def _taxonomy_id(bind: sa.engine.Connection, key: str) -> str | None:
    row = bind.execute(
        sa.text("SELECT id FROM taxonomies WHERE key = :key LIMIT 1"),
        {"key": key},
    ).first()
    return str(row[0]) if row else None


def _insert_taxonomy(
    bind: sa.engine.Connection,
    *,
    taxonomy_id: str,
    key: str,
    display_name: str,
    now: datetime,
) -> None:
    bind.execute(
        sa.text(
            """
            INSERT INTO taxonomies (id, key, applies_to, cardinality, display_name, created_at, updated_at)
            VALUES (:id, :key, :applies_to, :cardinality, :display_name, :created_at, :updated_at)
            """
        ),
        {
            "id": taxonomy_id,
            "key": key,
            "applies_to": "tag",
            "cardinality": "single",
            "display_name": display_name,
            "created_at": now,
            "updated_at": now,
        },
    )


def _update_taxonomy(
    bind: sa.engine.Connection,
    *,
    taxonomy_id: str,
    key: str | None = None,
    display_name: str | None = None,
    now: datetime,
) -> None:
    assignments = ["updated_at = :updated_at"]
    params: dict[str, object] = {"updated_at": now, "taxonomy_id": taxonomy_id}
    if key is not None:
        assignments.insert(0, "key = :key")
        params["key"] = key
    if display_name is not None:
        assignments.insert(0, "display_name = :display_name")
        params["display_name"] = display_name

    bind.execute(
        sa.text(
            f"""
            UPDATE taxonomies
            SET {", ".join(assignments)}
            WHERE id = :taxonomy_id
            """
        ),
        params,
    )


def _iter_terms(
    bind: sa.engine.Connection,
    *,
    taxonomy_id: str,
) -> sa.engine.RowMapping:
    return bind.execute(
        sa.text(
            """
            SELECT id, name, normalized_name, created_at, updated_at
            FROM taxonomy_terms
            WHERE taxonomy_id = :taxonomy_id
            """
        ),
        {"taxonomy_id": taxonomy_id},
    ).mappings()


def _ensure_term_for_taxonomy(
    bind: sa.engine.Connection,
    *,
    taxonomy_id: str,
    term: sa.engine.RowMapping,
    now: datetime,
) -> str:
    normalized_name = str(term["normalized_name"])
    existing_new_term_id = bind.execute(
        sa.text(
            """
            SELECT id
            FROM taxonomy_terms
            WHERE taxonomy_id = :taxonomy_id AND normalized_name = :normalized_name
            LIMIT 1
            """
        ),
        {
            "taxonomy_id": taxonomy_id,
            "normalized_name": normalized_name,
        },
    ).first()
    if existing_new_term_id is not None:
        return str(existing_new_term_id[0])

    new_term_id = str(uuid4())
    bind.execute(
        sa.text(
            """
            INSERT INTO taxonomy_terms
              (id, taxonomy_id, name, normalized_name, parent_term_id, metadata_json, created_at, updated_at)
            VALUES
              (:id, :taxonomy_id, :name, :normalized_name, NULL, NULL, :created_at, :updated_at)
            """
        ),
        {
            "id": new_term_id,
            "taxonomy_id": taxonomy_id,
            "name": str(term["name"]),
            "normalized_name": normalized_name,
            "created_at": term["created_at"] or now,
            "updated_at": term["updated_at"] or now,
        },
    )
    return new_term_id


def _copy_term_assignments(
    bind: sa.engine.Connection,
    *,
    source_taxonomy_id: str,
    source_term_id: str,
    target_taxonomy_id: str,
    target_term_id: str,
    now: datetime,
) -> None:
    assignments = bind.execute(
        sa.text(
            """
            SELECT subject_type, subject_id, position, created_at, updated_at
            FROM taxonomy_assignments
            WHERE taxonomy_id = :taxonomy_id AND term_id = :term_id
            """
        ),
        {
            "taxonomy_id": source_taxonomy_id,
            "term_id": source_term_id,
        },
    ).mappings()
    for assignment in assignments:
        existing_assignment = bind.execute(
            sa.text(
                """
                SELECT id
                FROM taxonomy_assignments
                WHERE taxonomy_id = :taxonomy_id
                  AND term_id = :term_id
                  AND subject_type = :subject_type
                  AND subject_id = :subject_id
                LIMIT 1
                """
            ),
            {
                "taxonomy_id": target_taxonomy_id,
                "term_id": target_term_id,
                "subject_type": str(assignment["subject_type"]),
                "subject_id": str(assignment["subject_id"]),
            },
        ).first()
        if existing_assignment is not None:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO taxonomy_assignments
                  (id, taxonomy_id, term_id, subject_type, subject_id, position, created_at, updated_at)
                VALUES
                  (:id, :taxonomy_id, :term_id, :subject_type, :subject_id, :position, :created_at, :updated_at)
                """
            ),
            {
                "id": str(uuid4()),
                "taxonomy_id": target_taxonomy_id,
                "term_id": target_term_id,
                "subject_type": str(assignment["subject_type"]),
                "subject_id": str(assignment["subject_id"]),
                "position": int(assignment["position"] or 0),
                "created_at": assignment["created_at"] or now,
                "updated_at": assignment["updated_at"] or now,
            },
        )


def _merge_taxonomy_data(
    bind: sa.engine.Connection,
    *,
    source_taxonomy_id: str,
    target_taxonomy_id: str,
    now: datetime,
) -> None:
    for source_term in _iter_terms(bind, taxonomy_id=source_taxonomy_id):
        target_term_id = _ensure_term_for_taxonomy(
            bind,
            taxonomy_id=target_taxonomy_id,
            term=source_term,
            now=now,
        )
        _copy_term_assignments(
            bind,
            source_taxonomy_id=source_taxonomy_id,
            source_term_id=str(source_term["id"]),
            target_taxonomy_id=target_taxonomy_id,
            target_term_id=target_term_id,
            now=now,
        )


def _delete_taxonomy(bind: sa.engine.Connection, *, taxonomy_id: str) -> None:
    bind.execute(
        sa.text("DELETE FROM taxonomy_assignments WHERE taxonomy_id = :taxonomy_id"),
        {"taxonomy_id": taxonomy_id},
    )
    bind.execute(
        sa.text("DELETE FROM taxonomy_terms WHERE taxonomy_id = :taxonomy_id"),
        {"taxonomy_id": taxonomy_id},
    )
    bind.execute(
        sa.text("DELETE FROM taxonomies WHERE id = :taxonomy_id"),
        {"taxonomy_id": taxonomy_id},
    )


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    old_taxonomy_id = _taxonomy_id(bind, _OLD_KEY)
    new_taxonomy_id = _taxonomy_id(bind, _NEW_KEY)

    if old_taxonomy_id is None and new_taxonomy_id is None:
        _insert_taxonomy(
            bind,
            taxonomy_id=str(uuid4()),
            key=_NEW_KEY,
            display_name=_NEW_DISPLAY,
            now=now,
        )
        return

    if old_taxonomy_id is not None and new_taxonomy_id is None:
        _update_taxonomy(
            bind,
            taxonomy_id=old_taxonomy_id,
            key=_NEW_KEY,
            display_name=_NEW_DISPLAY,
            now=now,
        )
        return

    if old_taxonomy_id is None or new_taxonomy_id is None:
        return

    _merge_taxonomy_data(
        bind,
        source_taxonomy_id=old_taxonomy_id,
        target_taxonomy_id=new_taxonomy_id,
        now=now,
    )
    _delete_taxonomy(bind, taxonomy_id=old_taxonomy_id)
    _update_taxonomy(
        bind,
        taxonomy_id=new_taxonomy_id,
        display_name=_NEW_DISPLAY,
        now=now,
    )


def downgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    old_taxonomy_id = _taxonomy_id(bind, _OLD_KEY)
    new_taxonomy_id = _taxonomy_id(bind, _NEW_KEY)

    if old_taxonomy_id is not None:
        _update_taxonomy(
            bind,
            taxonomy_id=old_taxonomy_id,
            display_name=_OLD_DISPLAY,
            now=now,
        )
        return

    if new_taxonomy_id is None:
        return

    _update_taxonomy(
        bind,
        taxonomy_id=new_taxonomy_id,
        key=_OLD_KEY,
        display_name=_OLD_DISPLAY,
        now=now,
    )
