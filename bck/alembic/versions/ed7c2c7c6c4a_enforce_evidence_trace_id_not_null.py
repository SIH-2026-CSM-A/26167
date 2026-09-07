"""Enforce the Evidence-to-ExecutionTrace relationship for existing databases.

Revision ID: ed7c2c7c6c4a
Revises: c9c6d725a002
Create Date: 2026-09-07 16:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "ed7c2c7c6c4a"
down_revision: str | None = "c9c6d725a002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Require every persisted Evidence row to reference an execution trace."""
    op.alter_column(
        "evidence",
        "trace_id",
        existing_type=sa.String(length=64),
        nullable=False,
    )


def downgrade() -> None:
    """Restore the nullable trace reference used by the originally deployed revision."""
    op.alter_column(
        "evidence",
        "trace_id",
        existing_type=sa.String(length=64),
        nullable=True,
    )
