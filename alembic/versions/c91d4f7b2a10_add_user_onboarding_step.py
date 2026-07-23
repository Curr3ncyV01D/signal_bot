"""add user onboarding_step

Revision ID: c91d4f7b2a10
Revises: 8f1c7a2b9d44
Create Date: 2026-07-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c91d4f7b2a10"
down_revision: Union[str, Sequence[str], None] = "8f1c7a2b9d44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "onboarding_step",
            sa.String(length=32),
            nullable=False,
            server_default="LANGUAGE",
        ),
    )
    op.execute("UPDATE users SET onboarding_step = 'COMPLETED' WHERE is_setup_completed = TRUE")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "onboarding_step")
