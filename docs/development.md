# Development

## Requirements

- [uv](https://docs.astral.sh/uv/), it installs Python 3.12 itself if needed
- Docker with docker compose

## Commands

```bash
uv sync
uv run pre-commit install
uv run pytest
uv run ruff check .
uv run pyright
```

Tests marked `integration` run against TimescaleDB and are skipped if it is not reachable.
Start it with `docker compose up -d db`. CI sets `BATTERY_DISPATCH_REQUIRE_DB=1`, which
turns the skip into a failure. The tests only touch rows of bidding zones starting with
`TEST-`.

To run locally against the database from docker compose, put the password from `.env`
into `config/config.yaml` (template: `config/config.yaml.example`).

```bash
cp config/config.yaml.example config/config.yaml
docker compose up -d db
uv run alembic upgrade head
uv run battery-dispatch
```

## Structure

```
battery_dispatch/
  main.py                  entry point: configuration, logging, server
  core/                    controller, component base, health model
  config/                  configuration from YAML and environment variables
  logging_setup/           logging configuration
  market_data/             price model, SMARD client, importer
  storage/                 database access, migrations
    adapters/timescaledb/
    repositories/          price repository and table definitions
    migrations/
  communication/http/      FastAPI server, dependencies, routes
    api/                   routes and request/response models
config/                    default_config.yaml, logging.yaml, template for config.yaml
tests/                     mirrors the package structure
```

The controller creates the components and manages their lifecycle. See
[ADR 0001](decisions/0001-controller-and-components.md).

## Configuration

Precedence, highest first:

1. environment variables with prefix `BATTERY_DISPATCH_`, nesting with `__`,
   for example `BATTERY_DISPATCH_DATABASE__HOST=db`
2. `config/config.yaml`, local overrides, not under version control
3. `config/default_config.yaml`
4. defaults in code

Unknown keys cause an error at startup.

## Branches

A simplified Gitflow:

| Branch | Purpose |
|---|---|
| `main` | released state, only via pull request from `develop` |
| `develop` | integration branch, default branch |
| `feature-*` | individual changes, pull request into `develop` |

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).
Every pull request runs the CI checks `code-style` (Ruff, Pyright) and `test` (pytest).
