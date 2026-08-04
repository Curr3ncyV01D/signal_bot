"""add rsi filter thresholds

Revision ID: d4e5f6a7b8c9
Revises: c91d4f7b2a10
Create Date: 2026-07-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c91d4f7b2a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "filter_rsi_min",
            sa.Float(),
            nullable=False,
            server_default="100.0",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "filter_rsi_max",
            sa.Float(),
            nullable=False,
            server_default="0.0",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "filter_rsi_max")
    op.drop_column("users", "filter_rsi_min")
