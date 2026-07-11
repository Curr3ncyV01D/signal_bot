"""remove channel settings and migrate dashboard metadata

Revision ID: 7c9e3f1a2b4c
Revises: 5d4d7d7b0f11
Create Date: 2026-07-08 00:00:00.000000

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7c9e3f1a2b4c"
down_revision: Union[str, Sequence[str], None] = "5d4d7d7b0f11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SYSTEM_METADATA_TABLE = "system_metadata"
CHANNEL_SETTINGS_TABLE = "channel_settings"
DASHBOARD_MESSAGE_ID_KEY = "dashboard_message_id"
LAST_SUMMARY_AT_KEY = "last_summary_at"


def _ensure_system_metadata_table(inspector: sa.Inspector) -> None:
    if SYSTEM_METADATA_TABLE in inspector.get_table_names():
        return

    op.create_table(
        SYSTEM_METADATA_TABLE,
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.String(length=1024), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def _upsert_metadata_value(bind: sa.Connection, key: str, value: str) -> None:
    metadata_table = sa.table(
        SYSTEM_METADATA_TABLE,
        sa.column("key", sa.String(length=100)),
        sa.column("value", sa.String(length=1024)),
    )

    existing = bind.execute(
        sa.select(metadata_table.c.key).where(metadata_table.c.key == key)
    ).first()

    if existing is None:
        bind.execute(metadata_table.insert().values(key=key, value=value))
        return

    bind.execute(
        metadata_table.update()
        .where(metadata_table.c.key == key)
        .values(value=value)
    )


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    _ensure_system_metadata_table(inspector)

    if CHANNEL_SETTINGS_TABLE not in inspector.get_table_names():
        return

    channel_settings_table = sa.table(
        CHANNEL_SETTINGS_TABLE,
        sa.column("id", sa.Integer()),
        sa.column("dashboard_message_id", sa.BigInteger()),
        sa.column("last_summary_at", sa.DateTime()),
    )

    row = bind.execute(
        sa.select(
            channel_settings_table.c.dashboard_message_id,
            channel_settings_table.c.last_summary_at,
        ).where(channel_settings_table.c.id == 1)
    ).mappings().first()

    if row is not None:
        dashboard_message_id = row.get("dashboard_message_id")
        if dashboard_message_id is not None:
            _upsert_metadata_value(bind, DASHBOARD_MESSAGE_ID_KEY, str(dashboard_message_id))

        last_summary_at = row.get("last_summary_at")
        if last_summary_at is not None:
            _upsert_metadata_value(bind, LAST_SUMMARY_AT_KEY, last_summary_at.isoformat())

    op.drop_table(CHANNEL_SETTINGS_TABLE)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if CHANNEL_SETTINGS_TABLE not in inspector.get_table_names():
        op.create_table(
            CHANNEL_SETTINGS_TABLE,
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("threshold", sa.Float(), nullable=False, server_default="100000.0"),
            sa.Column("threshold_cascade", sa.Float(), nullable=False, server_default="50000.0"),
            sa.Column("alert_cascade", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("alert_volume", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("alert_squeeze", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("alert_longs", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("alert_shorts", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("threshold_vol_pct", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("threshold_mode", sa.String(length=20), nullable=False, server_default="USD"),
            sa.Column("threshold_mcap_pct", sa.Float(), nullable=False, server_default="0.005"),
            sa.Column("threshold_mcap_usd_min", sa.Float(), nullable=False, server_default="1000.0"),
            sa.Column("threshold_cascade_mcap_pct", sa.Float(), nullable=False, server_default="0.01"),
            sa.Column("threshold_cascade_mcap_usd_min", sa.Float(), nullable=False, server_default="5000.0"),
            sa.Column("alert_oi", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("threshold_oi_percent", sa.Float(), nullable=False, server_default="10.0"),
            sa.Column("threshold_oi_value", sa.Float(), nullable=False, server_default="1000000.0"),
            sa.Column("alert_cvd", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("alert_rsi", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("dashboard_message_id", sa.BigInteger(), nullable=True),
            sa.Column("last_summary_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if SYSTEM_METADATA_TABLE not in inspector.get_table_names():
        return

    metadata_table = sa.table(
        SYSTEM_METADATA_TABLE,
        sa.column("key", sa.String(length=100)),
        sa.column("value", sa.String(length=1024)),
    )

    metadata_rows = bind.execute(
        sa.select(metadata_table.c.key, metadata_table.c.value).where(
            metadata_table.c.key.in_([DASHBOARD_MESSAGE_ID_KEY, LAST_SUMMARY_AT_KEY])
        )
    ).mappings().all()

    metadata = {row["key"]: row["value"] for row in metadata_rows}
    last_summary_at = metadata.get(LAST_SUMMARY_AT_KEY)

    bind.execute(
        sa.insert(
            sa.table(
                CHANNEL_SETTINGS_TABLE,
                sa.column("id", sa.Integer()),
                sa.column("dashboard_message_id", sa.BigInteger()),
                sa.column("last_summary_at", sa.DateTime()),
            )
        ).values(
            id=1,
            dashboard_message_id=(
                int(metadata[DASHBOARD_MESSAGE_ID_KEY])
                if DASHBOARD_MESSAGE_ID_KEY in metadata
                else None
            ),
            last_summary_at=(
                datetime.fromisoformat(last_summary_at)
                if last_summary_at is not None
                else None
            ),
        )
    )
