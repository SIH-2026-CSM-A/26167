"""create users

Revision ID: a1320a97a680
Revises: ed7c2c7c6c4a
Create Date: 2026-09-19 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1320a97a680"
down_revision: str | None = "ed7c2c7c6c4a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("auth_provider", sa.String(length=20), nullable=False),
        sa.Column("provider_subject", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("provider_subject"),
    )


def downgrade() -> None:
    op.drop_table("users")
