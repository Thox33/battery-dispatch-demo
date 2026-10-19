# ADR 0001: Controller and components

Status: accepted, 2026-10-19

## Context

The application consists of a few parts with their own lifecycle: database access, later
an HTTP client for SMARD. These parts need an ordered startup, an ordered shutdown and a
health check for `/health`.

FastAPI offers its own means for this with `lifespan` and `Depends`. Spreading the setup
across them makes it hard to read in one place and hard to test outside of FastAPI.

## Decision

- Every component derives from `ComponentBase` and provides `start`, `stop` and `health`.
- The `Controller` creates the components from the configuration, starts them in order
  and stops them in reverse order. If a start fails, the components already started are
  stopped again.
- FastAPI is the outer layer: `lifespan` only calls `Controller.running()`, routes get the
  controller through a dependency.
- The database connection is opened on first use. If the database is unreachable, the
  application still starts and reports the outage through `/health` with status 503.

## Consequences

- Lifecycle and health can be tested without a server and without a database.
- New parts such as the SMARD client are added as further components.
- For an application of this size this is somewhat more structure than strictly needed.
  The benefit is a single, clear place where everything is wired together.
