"""add community bonus flag

Revision ID: 8f1c7a2b9d44
Revises: 6d2f4b8a1c33
Create Date: 2026-07-20 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f1c7a2b9d44"
down_revision: Union[str, Sequence[str], None] = "6d2f4b8a1c33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "is_community_bonus_used",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "is_community_bonus_used")
