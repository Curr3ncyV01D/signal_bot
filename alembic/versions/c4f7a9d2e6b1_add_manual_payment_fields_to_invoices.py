"""add manual payment fields to invoices

Revision ID: c4f7a9d2e6b1
Revises: b8c1d0e9f123
Create Date: 2026-07-14 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "c4f7a9d2e6b1"
down_revision: Union[str, Sequence[str], None] = "b8c1d0e9f123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("invoices")}

    if "screenshot_file_id" not in existing_columns:
        op.add_column("invoices", sa.Column("screenshot_file_id", sa.String(length=255), nullable=True))

    if "approved_by_admin_id" not in existing_columns:
        op.add_column("invoices", sa.Column("approved_by_admin_id", sa.BigInteger(), nullable=True))

    if "rejection_reason" not in existing_columns:
        op.add_column("invoices", sa.Column("rejection_reason", sa.String(length=255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("invoices")}

    if "rejection_reason" in existing_columns:
        op.drop_column("invoices", "rejection_reason")

    if "approved_by_admin_id" in existing_columns:
        op.drop_column("invoices", "approved_by_admin_id")

    if "screenshot_file_id" in existing_columns:
        op.drop_column("invoices", "screenshot_file_id")
