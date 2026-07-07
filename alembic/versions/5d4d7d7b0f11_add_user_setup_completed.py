"""add user is_setup_completed

Revision ID: 5d4d7d7b0f11
Revises: 9f6b3f7a0b21
Create Date: 2026-07-06 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5d4d7d7b0f11"
down_revision: Union[str, Sequence[str], None] = "9f6b3f7a0b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "is_setup_completed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "is_setup_completed")
