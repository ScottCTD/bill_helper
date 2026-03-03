"""add taxonomy core tables and backfill entity categories

Revision ID: 0007_taxonomy_core
Revises: 0006_agent_append_only_core
Create Date: 2026-02-09
"""

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "0007_taxonomy_core"
down_revision: str | None = "0006_agent_append_only_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalize_term_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    normalized = " ".join(raw.split()).strip().lower()
    return normalized or None


def upgrade() -> None:
    op.create_table(
        "taxonomies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("applies_to", sa.String(length=50), nullable=False),
        sa.Column("cardinality", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_taxonomies_key", "taxonomies", ["key"], unique=True)

    op.create_table(
        "taxonomy_terms",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("taxonomy_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        sa.Column("parent_term_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["parent_term_id"], ["taxonomy_terms.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["taxonomy_id"], ["taxonomies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("taxonomy_id", "normalized_name", name="uq_taxonomy_terms_name"),
    )
    op.create_index("ix_taxonomy_terms_normalized_name", "taxonomy_terms", ["normalized_name"], unique=False)
    op.create_index("ix_taxonomy_terms_parent_term_id", "taxonomy_terms", ["parent_term_id"], unique=False)
    op.create_index("ix_taxonomy_terms_taxonomy_id", "taxonomy_terms", ["taxonomy_id"], unique=False)

    op.create_table(
        "taxonomy_assignments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("taxonomy_id", sa.String(length=36), nullable=False),
        sa.Column("term_id", sa.String(length=36), nullable=False),
        sa.Column("subject_type", sa.String(length=50), nullable=False),
        sa.Column("subject_id", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["taxonomy_id"], ["taxonomies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["term_id"], ["taxonomy_terms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "taxonomy_id",
            "subject_type",
            "subject_id",
            "term_id",
            name="uq_taxonomy_assignments_subject_term",
        ),
    )
    op.create_index("ix_taxonomy_assignments_subject_id", "taxonomy_assignments", ["subject_id"], unique=False)
    op.create_index("ix_taxonomy_assignments_subject_type", "taxonomy_assignments", ["subject_type"], unique=False)
    op.create_index("ix_taxonomy_assignments_taxonomy_id", "taxonomy_assignments", ["taxonomy_id"], unique=False)
    op.create_index("ix_taxonomy_assignments_term_id", "taxonomy_assignments", ["term_id"], unique=False)

    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    entity_category_taxonomy_id = str(uuid4())
    tag_type_taxonomy_id = str(uuid4())

    bind.execute(
        sa.text(
            """
            INSERT INTO taxonomies (id, key, applies_to, cardinality, display_name, created_at, updated_at)
            VALUES (:id, :key, :applies_to, :cardinality, :display_name, :created_at, :updated_at)
            """
        ),
        {
            "id": entity_category_taxonomy_id,
            "key": "entity_category",
            "applies_to": "entity",
            "cardinality": "single",
            "display_name": "Entity Categories",
            "created_at": now,
            "updated_at": now,
        },
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO taxonomies (id, key, applies_to, cardinality, display_name, created_at, updated_at)
            VALUES (:id, :key, :applies_to, :cardinality, :display_name, :created_at, :updated_at)
            """
        ),
        {
            "id": tag_type_taxonomy_id,
            "key": "tag_type",
            "applies_to": "tag",
            "cardinality": "single",
            "display_name": "Tag Types",
            "created_at": now,
            "updated_at": now,
        },
    )

    rows = bind.execute(
        sa.text("SELECT id, category FROM entities WHERE category IS NOT NULL")
    ).mappings()
    term_id_by_name: dict[str, str] = {}
    for row in rows:
        normalized_term_name = _normalize_term_name(row["category"])
        if normalized_term_name is None:
            continue

        term_id = term_id_by_name.get(normalized_term_name)
        if term_id is None:
            term_id = str(uuid4())
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
                    "id": term_id,
                    "taxonomy_id": entity_category_taxonomy_id,
                    "name": normalized_term_name,
                    "normalized_name": normalized_term_name,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            term_id_by_name[normalized_term_name] = term_id

        bind.execute(
            sa.text(
                """
                INSERT INTO taxonomy_assignments
                  (id, taxonomy_id, term_id, subject_type, subject_id, position, created_at, updated_at)
                VALUES
                  (:id, :taxonomy_id, :term_id, :subject_type, :subject_id, 0, :created_at, :updated_at)
                """
            ),
            {
                "id": str(uuid4()),
                "taxonomy_id": entity_category_taxonomy_id,
                "term_id": term_id,
                "subject_type": "entity",
                "subject_id": row["id"],
                "created_at": now,
                "updated_at": now,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_taxonomy_assignments_term_id", table_name="taxonomy_assignments")
    op.drop_index("ix_taxonomy_assignments_taxonomy_id", table_name="taxonomy_assignments")
    op.drop_index("ix_taxonomy_assignments_subject_type", table_name="taxonomy_assignments")
    op.drop_index("ix_taxonomy_assignments_subject_id", table_name="taxonomy_assignments")
    op.drop_table("taxonomy_assignments")

    op.drop_index("ix_taxonomy_terms_taxonomy_id", table_name="taxonomy_terms")
    op.drop_index("ix_taxonomy_terms_parent_term_id", table_name="taxonomy_terms")
    op.drop_index("ix_taxonomy_terms_normalized_name", table_name="taxonomy_terms")
    op.drop_table("taxonomy_terms")

    op.drop_index("ix_taxonomies_key", table_name="taxonomies")
    op.drop_table("taxonomies")
