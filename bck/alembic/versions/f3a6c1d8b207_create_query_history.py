"""create query_history

Revision ID: f3a6c1d8b207
Revises: b7e2f5a91c34
Create Date: 2026-09-20 06:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3a6c1d8b207"
down_revision: str | None = "b7e2f5a91c34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "query_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("query_text", sa.String(), nullable=False),
        sa.Column("answer_text", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("modality", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_foreign_key(
        "fk_query_history_user_id",
        "query_history",
        "users",
        ["user_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_query_history_user_id", "query_history", type_="foreignkey")
    op.drop_table("query_history")
