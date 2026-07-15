"""add coin mappings table

Revision ID: 6d2f4b8a1c33
Revises: c4f7a9d2e6b1
Create Date: 2026-07-15 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6d2f4b8a1c33"
down_revision: Union[str, Sequence[str], None] = "c4f7a9d2e6b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_MAPPINGS = [
    {"symbol": "BIT", "cg_id": "bitdao", "comment": "Migrated from legacy utils.MANUAL_MAPPING"},
    {"symbol": "WLD", "cg_id": "worldcoin-org", "comment": "Migrated from legacy utils.MANUAL_MAPPING"},
    {"symbol": "PEPE", "cg_id": "pepe", "comment": "Migrated from legacy utils.MANUAL_MAPPING"},
    {"symbol": "SHIB", "cg_id": "shiba-inu", "comment": "Migrated from legacy utils.MANUAL_MAPPING"},
]


def upgrade() -> None:
    op.create_table(
        "coin_mappings",
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("cg_id", sa.String(length=100), nullable=False),
        sa.Column("comment", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("symbol"),
    )
    op.create_index(op.f("ix_coin_mappings_cg_id"), "coin_mappings", ["cg_id"], unique=False)

    coin_mappings = sa.table(
        "coin_mappings",
        sa.column("symbol", sa.String(length=20)),
        sa.column("cg_id", sa.String(length=100)),
        sa.column("comment", sa.String(length=255)),
    )
    op.bulk_insert(coin_mappings, SEED_MAPPINGS)


def downgrade() -> None:
    op.drop_index(op.f("ix_coin_mappings_cg_id"), table_name="coin_mappings")
    op.drop_table("coin_mappings")
