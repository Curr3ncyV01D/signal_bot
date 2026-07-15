"""drop invoice.amount column

Revision ID: b8c1d0e9f123
Revises: 3f5c2b8d9e41
Create Date: 2026-07-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "b8c1d0e9f123"
down_revision: Union[str, Sequence[str], None] = "3f5c2b8d9e41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("invoices")}

    if "amount" not in existing_columns:
        return

    if "amount_expected" in existing_columns:
        op.execute(
            """
            UPDATE invoices
            SET amount_expected = COALESCE(amount_expected, amount)
            WHERE amount_expected IS NULL
            """
        )

    op.drop_column("invoices", "amount")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("invoices")}

    if "amount" in existing_columns:
        return

    op.add_column("invoices", sa.Column("amount", sa.Float(), nullable=True))
    if "amount_expected" in existing_columns:
        op.execute(
            """
            UPDATE invoices
            SET amount = amount_expected
            WHERE amount IS NULL AND amount_expected IS NOT NULL
            """
        )
    op.alter_column("invoices", "amount", existing_type=sa.Float(), nullable=False)

