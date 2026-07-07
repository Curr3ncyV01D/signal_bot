"""add user language_code

Revision ID: 9f6b3f7a0b21
Revises: c15c32e4d47c
Create Date: 2026-07-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f6b3f7a0b21'
down_revision: Union[str, Sequence[str], None] = 'c15c32e4d47c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('language_code', sa.String(length=2), nullable=False, server_default='ru'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'language_code')
