"""expand invoices for cryptomus

Revision ID: 3f5c2b8d9e41
Revises: 1a2b3c4d5e6f
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "3f5c2b8d9e41"
down_revision: Union[str, Sequence[str], None] = "1a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("invoices")}
    existing_indexes = {index["name"] for index in inspector.get_indexes("invoices")}

    if "external_id" not in existing_columns:
        op.add_column("invoices", sa.Column("external_id", sa.String(length=100), nullable=True))

    if "provider" not in existing_columns:
        op.add_column(
            "invoices",
            sa.Column("provider", sa.String(length=20), nullable=False, server_default="CRYPTOMUS"),
        )

    if "address" not in existing_columns:
        op.add_column("invoices", sa.Column("address", sa.String(length=128), nullable=True))

    if "network" not in existing_columns:
        op.add_column("invoices", sa.Column("network", sa.String(length=20), nullable=True))

    if "amount_expected" not in existing_columns:
        op.add_column("invoices", sa.Column("amount_expected", sa.Float(), nullable=True))

    if "amount_actual" not in existing_columns:
        op.add_column(
            "invoices",
            sa.Column("amount_actual", sa.Float(), nullable=False, server_default="0"),
        )

    if "crypto_pay_id" in existing_columns:
        op.execute(
            """
            UPDATE invoices
            SET
                external_id = COALESCE(external_id, crypto_pay_id),
                provider = 'CRYPTOPAY',
                amount_expected = COALESCE(amount_expected, amount),
                amount_actual = COALESCE(
                    amount_actual,
                    CASE
                        WHEN status = 'PAID' THEN amount
                        ELSE 0
                    END
                )
            WHERE crypto_pay_id IS NOT NULL
            """
        )

    op.execute(
        """
        UPDATE invoices
        SET provider = COALESCE(provider, 'CRYPTOMUS')
        WHERE provider IS NULL OR provider = ''
        """
    )
    op.execute(
        """
        UPDATE invoices
        SET amount_expected = COALESCE(amount_expected, amount)
        WHERE amount_expected IS NULL
        """
    )
    op.execute(
        """
        UPDATE invoices
        SET amount_actual = COALESCE(
            amount_actual,
            CASE
                WHEN status = 'PAID' THEN amount
                ELSE 0
            END
        )
        WHERE amount_actual IS NULL
        """
    )

    op.alter_column("invoices", "external_id", existing_type=sa.String(length=100), nullable=False)
    op.alter_column("invoices", "provider", existing_type=sa.String(length=20), nullable=False)
    op.alter_column("invoices", "amount_expected", existing_type=sa.Float(), nullable=False)
    op.alter_column("invoices", "amount_actual", existing_type=sa.Float(), nullable=False)

    if "ix_invoices_external_id" not in existing_indexes:
        op.create_index("ix_invoices_external_id", "invoices", ["external_id"], unique=True)

    if "crypto_pay_id" in existing_columns:
        unique_constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("invoices")}
        for constraint_name in unique_constraints:
            if not constraint_name:
                continue
            if "crypto_pay_id" in constraint_name:
                op.drop_constraint(constraint_name, "invoices", type_="unique")

        if "ix_invoices_crypto_pay_id" in existing_indexes:
            op.drop_index("ix_invoices_crypto_pay_id", table_name="invoices")

        op.drop_column("invoices", "crypto_pay_id")


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("invoices")}
    existing_indexes = {index["name"] for index in inspector.get_indexes("invoices")}

    if "crypto_pay_id" not in existing_columns:
        op.add_column("invoices", sa.Column("crypto_pay_id", sa.String(length=50), nullable=True))
        op.execute(
            """
            UPDATE invoices
            SET crypto_pay_id = external_id
            WHERE external_id IS NOT NULL AND provider = 'CRYPTOPAY'
            """
        )
        op.alter_column("invoices", "crypto_pay_id", existing_type=sa.String(length=50), nullable=False)
        op.create_unique_constraint("uq_invoices_crypto_pay_id", "invoices", ["crypto_pay_id"])

    if "ix_invoices_external_id" in existing_indexes:
        op.drop_index("ix_invoices_external_id", table_name="invoices")
    if "amount_actual" in existing_columns:
        op.drop_column("invoices", "amount_actual")
    if "amount_expected" in existing_columns:
        op.drop_column("invoices", "amount_expected")
    if "network" in existing_columns:
        op.drop_column("invoices", "network")
    if "address" in existing_columns:
        op.drop_column("invoices", "address")
    if "provider" in existing_columns:
        op.drop_column("invoices", "provider")
    if "external_id" in existing_columns:
        op.drop_column("invoices", "external_id")
