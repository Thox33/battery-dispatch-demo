"""Table definition for day-ahead prices. The table is created by migration 0002."""

from sqlalchemy import Column, DateTime, Double, MetaData, Table, Text


metadata = MetaData()

day_ahead_prices = Table(
    "day_ahead_prices",
    metadata,
    Column("bidding_zone", Text, primary_key=True),
    Column("time", DateTime(timezone=True), primary_key=True),
    Column("price_eur_per_mwh", Double[float](), nullable=False),
)
