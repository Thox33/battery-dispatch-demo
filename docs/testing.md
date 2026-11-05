# Testing

This document answers what the tests secure and what they do not. The commands are in
[development.md](development.md).

## Layout

`tests/` mirrors the package structure. Each layer is tested with the layer below replaced:

- **Optimiser:** the real `optimize` with the real CBC solver, without a database.
- **Planner:** the real planner and solver with a fake repository.
- **Routes:** the real FastAPI application through `TestClient`, with a fake planner, importer
  or repository. The fakes in `tests/fakes.py` are subclasses of the real classes, so type
  checking keeps them in line.
- **SMARD client:** the real client against a mock HTTP transport. No test calls SMARD.
- **Repository:** the real repository against a real TimescaleDB.

## Markers and the database

There is one marker, `integration`, on the tests in `tests/storage/test_price_repository.py`.
They need TimescaleDB, which `docker compose up -d db` provides, and the
[setup](development.md#setup) for its password. The fixture `database_config` in
`tests/storage/conftest.py` decides what happens:

- Database reachable: it applies the migrations once per run, and the tests run.
- Database not reachable: the tests are skipped.
- Database not reachable and `BATTERY_DISPATCH_REQUIRE_DB` set: the tests fail. CI sets it.

A skip therefore means the repository was not tested. These tests only touch rows of bidding
zones starting with `TEST-`, and delete them before and after each test.

The tests in `tests/storage/test_storage_manager.py` need no database. They use port 1 on
localhost to provoke connection failures.

## Risks and the tests that cover them

| Risk | Tests |
| --- | --- |
| Energy balance is wrong, for example efficiency applied the wrong way | `test_balance_holds_in_every_step`, `test_two_steps_by_hand` |
| Power or energy limits are exceeded | `test_limits_hold` |
| A schedule earns money by emptying the battery | `test_final_energy_not_below_initial` |
| Charging and discharging in the same step at negative prices | `test_no_simultaneous_charge_and_discharge`, `test_flat_negative_blocks_solve_quickly` |
| Negative prices are not used or not stored | `test_negative_prices_are_used`, `test_negative_prices_are_stored` |
| The solver reaches its time limit on flat negative prices | `test_flat_negative_blocks_solve_quickly` |
| A schedule without proof is returned as a result | `test_solution_without_proof_of_optimality_raises`, `test_solver_failure_returns_500` |
| A solver failure goes unnoticed | `test_solver_error_raises`, `test_missing_solver_value_raises` |
| Days with 100 quarter hours break | `test_daylight_saving_day`, `test_optimize_accepts_calendar_month_with_daylight_saving_change` |
| Missing prices are filled in or ignored | `test_incomplete_prices_raise`, `test_no_stored_prices_raise`, `test_incomplete_prices_return_409` |
| Repeated imports create duplicates or miss corrections | `test_repeated_upsert_writes_nothing`, `test_changed_price_is_updated` |
| Range ends are off by one | `test_range_end_is_exclusive`, `test_end_is_exclusive`, `test_returns_points_within_half_open_range` |
| SMARD fails or changes its format | `test_http_error_raises_smard_error`, `test_unexpected_format_raises_smard_error`, `test_import_smard_failure_returns_502` |
| Unpublished values are stored as prices | `test_skips_values_not_published_yet` |
| Invalid input reaches the solver or the database | `test_optimize_rejects_invalid_request`, `test_import_rejects_invalid_range`, `test_get_prices_rejects_naive_datetimes` |
| A database outage answers 500 instead of 503 | `test_unreachable_database_raises_storage_unavailable`, `test_unavailable_database_returns_503`, `test_import_with_unavailable_database_returns_503`, `test_get_prices_with_unavailable_database_returns_503` |
| A database outage stops the application or hides in `/health` | `test_unreachable_database_is_reported_not_raised`, `test_health_down_returns_503` |
| A failed start leaves components running | `test_failed_start_stops_already_started_components`, `test_starts_in_order_and_stops_in_reverse` |
| The database password shows up in the `repr` of the configuration | `test_password_is_not_shown_in_repr` |
| A typo in the configuration is silently ignored | `test_unknown_keys_are_rejected` |
| The web page loads files from other servers or is missing from the package | `test_page_loads_only_local_files`, `test_frontend_directory_is_part_of_the_package` |

Most optimiser tests check properties of the result, since optima need not be unique, see
[optimisation.md](optimisation.md#why-it-is-well-posed). Only small cases compare exact numbers.

## What the tests do not cover

- **Browser behaviour.** There are no automated browser tests. Charts, hover, drag zoom, error
  messages on the page and the light and dark themes were checked in one-off runs, by agents
  driving a browser. The route tests only check that the files are served.
- **The whole chain at once.** No test runs route, planner, solver and database together. Agents
  ran such requests one-off against the running stack; the results are in the
  [plans](plans/README.md).
- **Days with 92 quarter hours.** No test uses the day summer time starts. It was checked one-off
  during review.
- **SMARD itself.** The mock transport serves data in the format known today. A real change at
  SMARD shows up only at run time, as a 502.
- **The container.** CI builds the Python package but does not build the image or run
  `docker compose up`.
- **Runtimes on real prices.** The runtimes in
  [ADR 0003](decisions/0003-milp-for-battery-dispatch.md) were measured once. CI only runs the
  synthetic `test_flat_negative_blocks_solve_quickly`. The time limit failure is simulated by
  replacing the solver call, not provoked.
- **Optimality against a second solver.** Beyond the small cases by hand, no test compares a
  revenue with an independent result.

## Mutation checks

During review, constraints were changed on purpose to see whether the tests notice: without the
exclusivity constraints `test_no_simultaneous_charge_and_discharge` fails, without the final
energy constraint and with a wrong efficiency in the balance several tests fail. This was
one-off review work, recorded in the [plans](plans/README.md). It is not part of CI, and no
mutation testing tool is configured.

## CI

Every pull request into `develop` or `main` runs two workflows from `.github/workflows/`:

- `code-style.yml` runs pre-commit: Ruff, Pyright and general file checks.
- `tests.yml` builds the package and runs pytest against a TimescaleDB service, with
  `BATTERY_DISPATCH_REQUIRE_DB` set.
