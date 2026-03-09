"""add account agent change types

Revision ID: 0030_add_account_agent_change_types
Revises: 0029_add_agent_run_surface
Create Date: 2026-03-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0030_add_account_agent_change_types"
down_revision: str | None = "0029_add_agent_run_surface"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OLD_AGENT_CHANGE_TYPE = sa.Enum(
    "CREATE_ENTRY",
    "UPDATE_ENTRY",
    "DELETE_ENTRY",
    "CREATE_GROUP",
    "UPDATE_GROUP",
    "DELETE_GROUP",
    "CREATE_GROUP_MEMBER",
    "DELETE_GROUP_MEMBER",
    "CREATE_TAG",
    "UPDATE_TAG",
    "DELETE_TAG",
    "CREATE_ENTITY",
    "UPDATE_ENTITY",
    "DELETE_ENTITY",
    name="agentchangetype",
)

_NEW_AGENT_CHANGE_TYPE = sa.Enum(
    "CREATE_ENTRY",
    "UPDATE_ENTRY",
    "DELETE_ENTRY",
    "CREATE_ACCOUNT",
    "UPDATE_ACCOUNT",
    "DELETE_ACCOUNT",
    "CREATE_GROUP",
    "UPDATE_GROUP",
    "DELETE_GROUP",
    "CREATE_GROUP_MEMBER",
    "DELETE_GROUP_MEMBER",
    "CREATE_TAG",
    "UPDATE_TAG",
    "DELETE_TAG",
    "CREATE_ENTITY",
    "UPDATE_ENTITY",
    "DELETE_ENTITY",
    name="agentchangetype",
)


def upgrade() -> None:
    with op.batch_alter_table("agent_change_items", recreate="always") as batch_op:
        batch_op.alter_column(
            "change_type",
            existing_type=_OLD_AGENT_CHANGE_TYPE,
            type_=_NEW_AGENT_CHANGE_TYPE,
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_change_items", recreate="always") as batch_op:
        batch_op.alter_column(
            "change_type",
            existing_type=_NEW_AGENT_CHANGE_TYPE,
            type_=_OLD_AGENT_CHANGE_TYPE,
            existing_nullable=False,
        )
