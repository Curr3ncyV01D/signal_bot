"""add cactus multicurrency fields to invoices

Revision ID: e1a2b3c4d5f6
Revises: d4e5f6a7b8c9
Create Date: 2026-08-06 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "e1a2b3c4d5f6"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("invoices")}

    if "currency" not in existing_columns:
        op.add_column(
            "invoices",
            sa.Column(
                "currency",
                sa.String(length=3),
                nullable=False,
                server_default="USD",
            ),
        )

    if "amount_expected_native" not in existing_columns:
        op.add_column(
            "invoices",
            sa.Column(
                "amount_expected_native",
                sa.Float(),
                nullable=False,
                server_default="0.0",
            ),
        )

    if "amount_actual_native" not in existing_columns:
        op.add_column(
            "invoices",
            sa.Column(
                "amount_actual_native",
                sa.Float(),
                nullable=False,
                server_default="0.0",
            ),
        )

    if "expires_at" not in existing_columns:
        op.add_column(
            "invoices",
            sa.Column(
                "expires_at",
                sa.DateTime(),
                nullable=True,
                server_default=None,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("invoices")}

    if "expires_at" in existing_columns:
        op.drop_column("invoices", "expires_at")

    if "amount_actual_native" in existing_columns:
        op.drop_column("invoices", "amount_actual_native")

    if "amount_expected_native" in existing_columns:
        op.drop_column("invoices", "amount_expected_native")

    if "currency" in existing_columns:
        op.drop_column("invoices", "currency")
