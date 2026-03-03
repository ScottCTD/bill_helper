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


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    old_taxonomy_id = _taxonomy_id(bind, _OLD_KEY)
    new_taxonomy_id = _taxonomy_id(bind, _NEW_KEY)

    if old_taxonomy_id is None and new_taxonomy_id is None:
        bind.execute(
            sa.text(
                """
                INSERT INTO taxonomies (id, key, applies_to, cardinality, display_name, created_at, updated_at)
                VALUES (:id, :key, :applies_to, :cardinality, :display_name, :created_at, :updated_at)
                """
            ),
            {
                "id": str(uuid4()),
                "key": _NEW_KEY,
                "applies_to": "tag",
                "cardinality": "single",
                "display_name": _NEW_DISPLAY,
                "created_at": now,
                "updated_at": now,
            },
        )
        return

    if old_taxonomy_id is not None and new_taxonomy_id is None:
        bind.execute(
            sa.text(
                """
                UPDATE taxonomies
                SET key = :new_key, display_name = :display_name, updated_at = :updated_at
                WHERE id = :taxonomy_id
                """
            ),
            {
                "new_key": _NEW_KEY,
                "display_name": _NEW_DISPLAY,
                "updated_at": now,
                "taxonomy_id": old_taxonomy_id,
            },
        )
        return

    if old_taxonomy_id is None or new_taxonomy_id is None:
        return

    old_terms = bind.execute(
        sa.text(
            """
            SELECT id, name, normalized_name, created_at, updated_at
            FROM taxonomy_terms
            WHERE taxonomy_id = :taxonomy_id
            """
        ),
        {"taxonomy_id": old_taxonomy_id},
    ).mappings()

    for old_term in old_terms:
        normalized_name = str(old_term["normalized_name"])
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
                "taxonomy_id": new_taxonomy_id,
                "normalized_name": normalized_name,
            },
        ).first()
        new_term_id = str(existing_new_term_id[0]) if existing_new_term_id else str(uuid4())
        if existing_new_term_id is None:
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
                    "taxonomy_id": new_taxonomy_id,
                    "name": str(old_term["name"]),
                    "normalized_name": normalized_name,
                    "created_at": old_term["created_at"] or now,
                    "updated_at": old_term["updated_at"] or now,
                },
            )

        assignments = bind.execute(
            sa.text(
                """
                SELECT subject_type, subject_id, position, created_at, updated_at
                FROM taxonomy_assignments
                WHERE taxonomy_id = :taxonomy_id AND term_id = :term_id
                """
            ),
            {
                "taxonomy_id": old_taxonomy_id,
                "term_id": str(old_term["id"]),
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
                    "taxonomy_id": new_taxonomy_id,
                    "term_id": new_term_id,
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
                    "taxonomy_id": new_taxonomy_id,
                    "term_id": new_term_id,
                    "subject_type": str(assignment["subject_type"]),
                    "subject_id": str(assignment["subject_id"]),
                    "position": int(assignment["position"] or 0),
                    "created_at": assignment["created_at"] or now,
                    "updated_at": assignment["updated_at"] or now,
                },
            )

    bind.execute(
        sa.text("DELETE FROM taxonomy_assignments WHERE taxonomy_id = :taxonomy_id"),
        {"taxonomy_id": old_taxonomy_id},
    )
    bind.execute(
        sa.text("DELETE FROM taxonomy_terms WHERE taxonomy_id = :taxonomy_id"),
        {"taxonomy_id": old_taxonomy_id},
    )
    bind.execute(
        sa.text("DELETE FROM taxonomies WHERE id = :taxonomy_id"),
        {"taxonomy_id": old_taxonomy_id},
    )
    bind.execute(
        sa.text(
            """
            UPDATE taxonomies
            SET display_name = :display_name, updated_at = :updated_at
            WHERE id = :taxonomy_id
            """
        ),
        {
            "display_name": _NEW_DISPLAY,
            "updated_at": now,
            "taxonomy_id": new_taxonomy_id,
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    old_taxonomy_id = _taxonomy_id(bind, _OLD_KEY)
    new_taxonomy_id = _taxonomy_id(bind, _NEW_KEY)

    if old_taxonomy_id is not None:
        bind.execute(
            sa.text(
                """
                UPDATE taxonomies
                SET display_name = :display_name, updated_at = :updated_at
                WHERE id = :taxonomy_id
                """
            ),
            {
                "display_name": _OLD_DISPLAY,
                "updated_at": now,
                "taxonomy_id": old_taxonomy_id,
            },
        )
        return

    if new_taxonomy_id is None:
        return

    bind.execute(
        sa.text(
            """
            UPDATE taxonomies
            SET key = :old_key, display_name = :display_name, updated_at = :updated_at
            WHERE id = :taxonomy_id
            """
        ),
        {
            "old_key": _OLD_KEY,
            "display_name": _OLD_DISPLAY,
            "updated_at": now,
            "taxonomy_id": new_taxonomy_id,
        },
    )
