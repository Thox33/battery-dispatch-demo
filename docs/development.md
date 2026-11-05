# Development

This document answers how to set up, run and change the project.

## Requirements

- [uv](https://docs.astral.sh/uv/), it installs Python 3.12 itself if needed
- Docker with docker compose

## Setup

```bash
uv sync
uv run pre-commit install
cp .env.example .env
cp config/config.yaml.example config/config.yaml
```

`.env` sets the password of the database from docker compose. Tests and runs on the host read
it from `config/config.yaml`. The two examples hold the same value; if you change one, change
the other. `BATTERY_DISPATCH_DATABASE__PASSWORD` can be set instead of the file.

## Checks

These are the checks every change has to pass:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv lock --check
docker compose up -d db
BATTERY_DISPATCH_REQUIRE_DB=1 uv run pytest
uv run pre-commit run --all-files
```

What the tests need from the database, what a skip means and what the tests cover is described
in [testing.md](testing.md#markers-and-the-database).

To run the application on the host against the database from docker compose:

```bash
docker compose up -d db
uv run alembic upgrade head
uv run battery-dispatch
```

The TimescaleDB image is pinned in `docker-compose.yml` and in the CI workflow; change
both together. Each image ships the older versions of the extension as well, so a
database volume created with an earlier image keeps working after an image update and
keeps its extension version. To move it to the version of the new image, run the update
as the first command of a fresh session:

```bash
docker compose exec db psql -X -U battery_dispatch -d battery_dispatch \
  -c "ALTER EXTENSION timescaledb UPDATE"
```

## Structure

```
battery_dispatch/
  main.py                  entry point: configuration, logging, server
  core/                    controller, component base, health model
  config/                  configuration from YAML and environment variables
  logging_setup/           logging configuration
  market_data/             price model, SMARD client, importer
  optimization/            battery parameters, schedule, optimiser, dispatch planner
  storage/                 database access, migrations
    adapters/timescaledb/
    repositories/          price repository and table definitions
    migrations/
  communication/http/      FastAPI server, dependencies, routes
    api/                   routes and request/response models
    frontend/              web page served at /ui/, vendored uPlot under vendor/
config/                    default_config.yaml, logging.yaml, template for config.yaml
tests/                     mirrors the package structure
```

The controller creates the components and manages their lifecycle. See
[ADR 0001](decisions/0001-controller-and-components.md). The dispatch planner holds no
resources of its own; the controller creates it, but it is not a component. How the parts
work together is described in [architecture.md](architecture.md).

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

Work packages run through the [planner, builder and reviewer workflow](workflow.md); their
branch is named in the plan. Commit messages follow
[Conventional Commits](https://www.conventionalcommits.org/).
Every pull request runs the CI checks `code-style` (Ruff, Pyright) and `test` (pytest).
