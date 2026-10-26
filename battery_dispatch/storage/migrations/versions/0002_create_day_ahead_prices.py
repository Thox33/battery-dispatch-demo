"""Create the day_ahead_prices hypertable.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-26
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE day_ahead_prices (
            bidding_zone      text             NOT NULL,
            time              timestamptz      NOT NULL,
            price_eur_per_mwh double precision NOT NULL,
            PRIMARY KEY (bidding_zone, time)
        )
        """
    )
    op.execute(
        "SELECT create_hypertable('day_ahead_prices', 'time', "
        "chunk_time_interval => INTERVAL '30 days')"
    )


def downgrade() -> None:
    op.execute("DROP TABLE day_ahead_prices")
