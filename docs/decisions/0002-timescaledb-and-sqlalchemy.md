# ADR 0002: TimescaleDB, async SQLAlchemy and Alembic

Status: accepted, 2026-10-19

## Context

Prices are a time series at quarter-hour resolution. Queries almost always cover a time
range. Repeated imports must not create duplicates.

## Decision

- **PostgreSQL with TimescaleDB.** The price table becomes a hypertable partitioned by
  time. This takes a single call to `create_hypertable` and keeps range queries fast as
  the data grows. A unique key on timestamp and bidding zone prevents duplicates; the
  import writes with `ON CONFLICT`.
- **SQLAlchemy 2 in async mode with asyncpg.** FastAPI is asynchronous, and so is the SMARD
  client. A fully asynchronous chain avoids thread pools for database access.
- **Alembic for the schema.** Migrations are written by hand, since TimescaleDB commands
  are not generated automatically anyway. The container runs `alembic upgrade head` before
  starting the API.

## Consequences

- Plain PostgreSQL would be enough for the data volume of a demo. TimescaleDB is a
  deliberate choice in case more time series are added.
- The optimisation itself is CPU-bound and synchronous. It will run in a worker thread so
  that it does not block the event loop.
