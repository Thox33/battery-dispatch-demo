# WP1: Dispatch optimisation

- Status: done
- Branch: `feature-wp1-dispatch-optimization`
- Sources: [ADR 0001](../decisions/0001-controller-and-components.md),
  [ADR 0002](../decisions/0002-timescaledb-and-sqlalchemy.md), [api.md](../api.md),
  [problem.md](../problem.md)

## Objective

Compute a revenue-maximising charge and discharge schedule for a battery from the stored
day-ahead prices of a time range, and expose it as `POST /dispatch/optimize`. The model
must stay physically valid with negative prices, which a plain linear program does not
guarantee.

## Requirements

| ID | Requirement | Covered by |
| --- | --- | --- |
| R1 | Schedule and expected revenue for a range of stored prices | steps 4, 7; `test_dispatch_routes.py`, live check |
| R2 | Energy balance with separate charge and discharge efficiency holds in every step | step 3; `test_balance_holds_in_every_step` |
| R3 | Power and state-of-charge limits hold; final energy is at least the initial energy | step 3; `test_limits_hold`, `test_final_energy_not_below_initial` |
| R4 | Never charge and discharge in the same quarter hour, also with negative prices | step 3; `test_no_simultaneous_charge_and_discharge` |
| R5 | Negative prices are used: charging while being paid | step 3; `test_negative_prices_are_used` |
| R6 | Missing prices in the range are reported, never filled in | step 4; `test_incomplete_prices_raise`, route test for 409 |
| R7 | The modelling decision is recorded | step 8; ADR 0003 |
| R8 | Docs describe endpoint, model and known limitations | step 9 |

## Scope

- Optimisation model, solver integration, planner that loads prices and runs the model.
- `POST /dispatch/optimize` with request validation and error mapping.
- Optional degradation cost per discharged MWh (default 0).
- ADR 0003, updates to `api.md`, `problem.md`, `development.md`, README.

## Non-scope

- Threshold strategy and comparison of strategies.
- Any visualisation or UI (WP2).
- Grid fees, taxes, forecasting, market impact of own bids, intraday markets.
- Persisting computed schedules.

## Design

### Model

Time steps `t = 1..T` are the quarter hours of `[start, end)`, `Δt = 0.25 h`. Inputs per
step: price `p_t` in EUR/MWh. Battery parameters: capacity `E` (kWh), maximum charge and
discharge power `P_ch`, `P_dis` (kW), efficiencies `η_ch`, `η_dis`, state-of-charge
limits `soc_min`, `soc_max` and `soc_initial` as fractions of `E`, degradation cost `k`
(EUR/MWh discharged).

Variables per step:

- `c_t ∈ [0, P_ch]`: charge power in kW, measured at the grid connection
- `d_t ∈ [0, P_dis]`: discharge power in kW, measured at the grid connection
- `e_t ∈ [soc_min·E, soc_max·E]`: stored energy in kWh at the end of step `t`
- `u_t ∈ {0, 1}`: 1 if charging is allowed in step `t`

Constraints:

- balance: `e_t = e_{t-1} + η_ch · c_t · Δt − d_t · Δt / η_dis`, with `e_0 = soc_initial·E`
- exclusivity: `c_t ≤ P_ch · u_t` and `d_t ≤ P_dis · (1 − u_t)`
- final energy: `e_T ≥ e_0`, so the schedule cannot earn money by emptying the battery

Objective, in EUR: maximise `Σ_t (p_t · (d_t − c_t) − k · d_t) · Δt / 1000`.

The binary `u_t` makes this a small mixed-integer program (one binary per quarter hour).
Without it, negative prices make simultaneous charging and discharging profitable, because
the efficiency losses then destroy energy that the market pays to take.

### Solver

PuLP 3.x with its bundled CBC (`PULP_CBC_CMD(msg=False, timeLimit=...)`). PuLP 4 is not
used: it no longer bundles a solver and changed the modelling API (variables are created
through the problem, `LpStatus` is gone). The dependency is pinned to `pulp>=3.3,<4` and
Dependabot ignores major updates for it.

The solver call is synchronous and CPU-bound; the planner runs it with
`asyncio.to_thread`. Any status other than optimal raises `OptimizationError`.

### Code structure

- `optimization/battery.py`: `BatteryParameters`, frozen dataclass, the model's input.
- `optimization/schedule.py`: `ScheduleStep` (time, price, charge_kw, discharge_kw,
  soc_kwh) and `Schedule` (steps plus `revenue_eur`, `degradation_cost_eur`,
  `charged_kwh`, `discharged_kwh`, `equivalent_full_cycles`, `solver_status`,
  `runtime_ms`).
- `optimization/milp_optimizer.py`: `optimize(prices: Sequence[PricePoint], battery,
  time_limit_s) -> Schedule`. Pure function, no I/O apart from the solver process.
  Solver values with an absolute value below `1e-6` are set to 0. Revenue and energy
  figures are computed from the cleaned schedule, not taken from the solver objective.
  `equivalent_full_cycles = discharged_kwh / ((soc_max − soc_min) · E)`.
- `optimization/dispatch_planner.py`: `DispatchPlanner(repository, config)` with
  `async plan(start, end, battery) -> Schedule`. Loads prices for DE-LU, checks that
  every quarter hour of the range is present, then runs `optimize` in a thread. Raises
  `PricesIncompleteError(expected, found, first_missing)` before solving if not.
- The controller creates the planner; it has no lifecycle and is not a component.

### API

`POST /dispatch/optimize`

```json
{
  "start": "2026-10-25T00:00:00+02:00",
  "end": "2026-10-26T00:00:00+01:00",
  "battery": {
    "capacity_kwh": 1000,
    "max_charge_kw": 500,
    "max_discharge_kw": 500,
    "charge_efficiency": 0.95,
    "discharge_efficiency": 0.95,
    "soc_min": 0.1,
    "soc_max": 0.9,
    "soc_initial": 0.5,
    "degradation_cost_eur_per_mwh": 0
  }
}
```

Response:

```json
{
  "start": "2026-10-24T22:00:00Z",
  "end": "2026-10-25T23:00:00Z",
  "bidding_zone": "DE-LU",
  "revenue_eur": 0.0,
  "degradation_cost_eur": 0.0,
  "charged_kwh": 0.0,
  "discharged_kwh": 0.0,
  "equivalent_full_cycles": 0.0,
  "solver": {"status": "optimal", "runtime_ms": 0},
  "schedule": [
    {"time": "2026-10-24T22:00:00Z", "price_eur_per_mwh": 0.0,
     "charge_kw": 0.0, "discharge_kw": 0.0, "soc_kwh": 0.0}
  ]
}
```

Validation (422):

- time range as in `api.md`, at most 31 days; `start` and `end` on quarter-hour boundaries
- `capacity_kwh`, `max_charge_kw`, `max_discharge_kw` > 0
- efficiencies in `(0, 1]`
- `0 ≤ soc_min < soc_max ≤ 1` and `soc_min ≤ soc_initial ≤ soc_max`
- `degradation_cost_eur_per_mwh ≥ 0`, default 0

Errors: 409 with expected and found counts and the first missing quarter hour when prices
are incomplete (the fix is to import them); 500 when the solver does not reach an optimal
solution; 503 for database errors as before.

### Configuration

New section `optimization` with `solver_time_limit_s` (default 30).

## Changes

| Path | Change |
| --- | --- |
| `pyproject.toml`, `uv.lock` | add `pulp>=3.3,<4` |
| `.github/dependabot.yml` | ignore major updates of `pulp` |
| `battery_dispatch/config/config_manager.py`, `config/default_config.yaml` | `OptimizationConfig` |
| `battery_dispatch/optimization/__init__.py` | create |
| `battery_dispatch/optimization/battery.py` | create |
| `battery_dispatch/optimization/schedule.py` | create |
| `battery_dispatch/optimization/milp_optimizer.py` | create |
| `battery_dispatch/optimization/dispatch_planner.py` | create |
| `battery_dispatch/core/controller.py` | create the planner |
| `battery_dispatch/communication/http/dependencies.py` | `get_dispatch_planner` |
| `battery_dispatch/communication/http/api/models.py` | dispatch request and response models |
| `battery_dispatch/communication/http/api/dispatch_routes.py` | create |
| `battery_dispatch/communication/http/server.py` | include the router |
| `tests/optimization/` | `test_milp_optimizer.py`, `test_dispatch_planner.py` |
| `tests/communication/http/api/test_dispatch_routes.py` | create |
| `tests/fakes.py` | fake planner |
| `docs/decisions/0003-milp-for-battery-dispatch.md` | create |
| `docs/api.md`, `docs/problem.md`, `docs/development.md`, `README.md` | update |
| `docs/plans/README.md`, this plan | status, implementation notes, handoff |

## Steps

- [x] 1. Create the branch from `develop`, set this plan to `in progress`.
- [x] 2. Add the dependency and the `optimization` configuration section.
- [x] 3. Implement `battery.py`, `schedule.py` and `milp_optimizer.py` with their unit tests (R2 to R5).
- [x] 4. Implement `dispatch_planner.py` with the completeness check and its tests (R6).
- [x] 5. Wire the planner into the controller and add the dependency.
- [x] 6. Add request and response models, the route and the error mapping.
- [x] 7. Add route tests: success, each validation rule, 409, solver failure.
- [x] 8. Write ADR 0003: mixed-integer model with a binary per step; alternatives considered (plain LP with a post-check, penalty term in the objective, `scipy.optimize.milp` with HiGHS, PuLP 4).
- [x] 9. Update `api.md` (endpoint, example, errors), `problem.md` (model, known limitations), `development.md` (structure), README (status and example).
- [x] 10. Run all checks, run the live check, complete the Handoff, set status to `review`.

## Verification

- `uv run ruff check .` and `uv run ruff format --check .`
- `uv run pyright`
- `BATTERY_DISPATCH_REQUIRE_DB=1 uv run pytest` with `docker compose up -d db`
- Focused optimiser tests:
  - `test_balance_holds_in_every_step`: recompute the stored energy from the schedule
  - `test_limits_hold`: power and stored energy within bounds in every step
  - `test_final_energy_not_below_initial`
  - `test_no_simultaneous_charge_and_discharge`: with strongly negative prices
  - `test_negative_prices_are_used`: battery charges during negative prices, revenue > 0
  - `test_two_steps_by_hand`: prices 0 and 100 EUR/MWh, revenue checked against a hand
    calculation
  - `test_flat_prices_do_nothing`: losses make any cycle unprofitable
  - `test_degradation_cost_suppresses_small_spreads`
  - `test_daylight_saving_day`: 100 steps
- Live check with `docker compose up --build`: import 2026-10-25, optimise with the
  example battery, check that charging happens at low and discharging at high prices and
  that the revenue is positive and plausible. Record the figures in the Handoff.

## Assumptions, open questions, and risks

- Choices from the proposal, to be confirmed with the approval: PuLP with CBC, separate
  charge and discharge efficiency, degradation cost as an optional parameter.
- 409 for incomplete prices: the request is valid, but the stored data does not allow
  an answer yet. 422 would also be defensible.
- Perfect foresight: the model knows all prices of the range. Results are an upper bound
  for real trading. Stated in the known limitations.
- Degradation cost is charged on discharged energy only, which counts each full cycle
  once.
- The CBC binary bundled with PuLP 3 must run in the `python:3.12-slim` image on x86_64.
  On ARM hosts it may be missing; then HiGHS via `highspy` is the fallback. The live check
  covers x86_64 only.
- CBC runs as a subprocess; starting it takes a few hundred milliseconds per solve. This
  is acceptable for a demo.
- 31 days give at most 2,980 binaries. CBC solves a day in well under a second; a month
  is expected to take seconds. The time limit protects the API.

## Implementation notes

Deviations from the plan:

- `pyproject.toml` also gets a pytest `filterwarnings` entry. PuLP 3.3.2 emits a
  `DeprecationWarning` pointing to PuLP 4 for every `LpVariable` and every
  `PULP_CBC_CMD` (about 1,400 per test run). The filter matches only messages containing
  `PuLP 4.0`. The application itself does not show them, since Python hides
  `DeprecationWarning` outside `__main__`.
- PuLP has no stubs. Instead of operator overloading, which pyright strict sees as
  `Unknown`, expressions and constraints are built with `LpAffineExpression` and
  `LpConstraint` from coefficient lists. Targeted ignores remain on the `pulp` imports
  (`reportMissingTypeStubs`), on `problem.solve` and `problem.sol_status`
  (`reportUnknownMemberType`, `reportUnknownArgumentType`) and on `assignStatus` in one
  test.
- "Optimal" is checked on `problem.sol_status == LpSolutionOptimal`, not on
  `problem.status`: CBC reports a run stopped at the time limit with a feasible solution
  as status `Optimal` and solution status `Solution Found`. This implements "any status
  other than optimal raises" for that case.
- `BatteryRequest` sets `allow_inf_nan=False`, so `Infinity` and `NaN` (accepted by the
  Python JSON parser) never reach the solver. See attention points for the resulting
  status code.
- `optimize` raises `ValueError` for an empty price list. The planner never calls it with
  one, since an empty result is reported as incomplete.

Interpretations where the plan left details open:

- `revenue_eur` is the market result (income from discharging minus cost of charging);
  `degradation_cost_eur` is reported separately and not deducted. Documented in
  `schedule.py` and `api.md`.
- 409 body: `{"detail": {"message", "expected", "found", "first_missing"}}`, modelled as
  `PricesIncompleteResponse` for the OpenAPI description.
- `solver.runtime_ms` measures the `problem.solve` call (CBC subprocess including file
  I/O), not model building.
- Additional tests beyond the list: `test_degradation_cost_is_reported`,
  `test_empty_prices_are_rejected`, `test_solution_without_proof_of_optimality_raises`,
  `test_no_stored_prices_raise`, `test_degradation_cost_is_passed_on`,
  `test_database_error_returns_503`.
- ADR 0003 states at most 2,976 binaries (31 × 96) instead of the plan's 2,980, see
  attention points.

`README.md` and `docs/development.md` already contained uncommitted links to the workflow
documents before implementation started; they are part of the diff but not of this work
package.

### After review round 1

Decided by the user on 2026-10-26:

- Finding 3: requests may span 31 days and one hour, so every calendar month in
  Europe/Berlin fits, including October with the end of summer time (2,980 quarter
  hours). `DispatchRequest.max_span` is `timedelta(days=31, hours=1)`.
- Finding 5: battery bounds. `capacity_kwh`, `max_charge_kw`, `max_discharge_kw` from 0.1
  to 10,000,000 inclusive; `charge_efficiency`, `discharge_efficiency` from 0.5 to 1;
  `degradation_cost_eur_per_mwh` at most 10,000. Out of range gives 422. These replace
  the plan's "> 0" and "(0, 1]" rules.
- Finding 1: keep CBC and set the default `optimization.mip_gap_rel` to `5e-3`
  (optimal within 0.5 %), option (a) of the first round 1 handoff. Options (b), HiGHS,
  and (c), keeping `1e-4`, were not chosen.

Further changes and deviations:

- `optimize` takes `time_limit_s` and the new `mip_gap_rel` as keyword-only arguments;
  the plan's signature had only `time_limit_s`.
- New setting `optimization.mip_gap_rel`, default `5e-3`, validated as `0 <= x < 1`, passed
  to CBC as `gapRel`. PuLP 3.3.2 maps both "Optimal" and "Optimal (within gap tolerance)"
  from the CBC solution file to `LpSolutionOptimal`; a run stopped at the time limit stays
  `Solution Found` and still raises. The response status `optimal` therefore means
  optimal within the gap; this is documented in `api.md`, `problem.md` and ADR 0003. PuLP
  does not expose whether the gap or a full proof ended the search, so the response
  cannot tell the two apart.
- Binaries only where `p_t < 0` were not introduced. With the gap, the real-data cases
  of the review solve in 0.5 to 3.3 s, and the restriction does not help flat negative
  blocks (all steps of such a block are negative).
- The optimiser unit tests use the production default gap instead of a test-specific
  value.
- `server.py` registers a handler for `RequestValidationError`. It returns the same body
  as the FastAPI default, with non-finite floats in the error entries replaced by strings
  (`"inf"`, `"nan"`).
- The invalid-request route test now posts raw JSON strings, so that `Infinity`, `NaN`
  and `1e400` can be sent.
- Regression test `test_flat_negative_blocks_solve_quickly`: 48 × -500 and 48 × -10
  EUR/MWh between positive prices and a day at -500 EUR/MWh must solve with status
  `optimal` in under 10 s of solver time.

## Handoff

- Branch: `feature-wp1-dispatch-optimization`
- Base: `develop` at `8ac7ae5`
- Diff to review: `git diff develop` plus the untracked files from `git status --short`:
  `battery_dispatch/communication/http/api/dispatch_routes.py`,
  `battery_dispatch/optimization/` (`__init__.py`, `battery.py`, `schedule.py`,
  `milp_optimizer.py`, `dispatch_planner.py`),
  `docs/decisions/0003-milp-for-battery-dispatch.md`,
  `tests/communication/http/api/test_dispatch_routes.py`,
  `tests/optimization/` (`__init__.py`, `test_milp_optimizer.py`,
  `test_dispatch_planner.py`), and the process files `docs/workflow.md` and `docs/plans/`.
  Nothing is committed.
- First handed over: 2026-10-26. Updated after review round 1 and the user decisions,
  and after review round 2: 2026-10-26.

Checks after the round 2 fixes (code and docs only; the live check below is from the
round 1 fixes, with `mip_gap_rel = 5e-3`, and was not repeated):

| Check | Result |
| --- | --- |
| `uv run ruff check .` | passed |
| `uv run ruff format --check .` | passed, 72 files already formatted |
| `uv run pyright` | passed, 0 errors |
| `uv lock --check` | passed |
| `docker compose up -d db`, then `BATTERY_DISPATCH_REQUIRE_DB=1 uv run pytest` | passed, 107 tests, none skipped, 7.2 s; then `docker compose stop db` |
| `uv run pre-commit run --all-files` | passed (covers tracked files only) |
| `uv run pre-commit run --files <untracked files>` | passed |
| Live: `docker compose up --build -d`, `GET /health` | 200, storage and smard ok |
| Live: CBC in `python:3.12-slim` (x86_64, user `app`) | executable, solves |
| Live: `POST /prices/import` 2026-10-25 | 200, `fetched: 100`, `written: 0` (already stored) |
| Live: `POST /dispatch/optimize` 2026-10-25, example battery | 200, 100 steps, revenue 50.92 EUR, 2.88 cycles, solver `optimal` in 136 ms (first request after start), schedule identical to the first round, no simultaneous charge and discharge, final energy 500 kWh |
| Live: calendar month March 2026 | 200, 2,972 steps, revenue 5,188.60 EUR, 97.3 cycles, solver 2,625 ms (was 500 after 30 s in the review) |
| `docker compose down` | done, volume `db-data` kept |

Earlier live results with `1e-4` (same session, before the user decision): week of
2026-03-22 612 ms, September 2026 2,854 ms, 2026-09-25T00:00+02:00 to
2026-10-26T00:00+01:00 (31 days and one hour, 2,980 steps) 1,488 ms, `Infinity` and
`1e400` as battery values 422 with the inputs reported as `"inf"`.

Runtimes on the host (Windows, `optimize` called directly, example battery, prices from
SMARD held in memory). Revenue is the market revenue; without degradation cost it equals
the objective.

| Range | Steps | Solver `5e-3` | Revenue `5e-3` | Solver `1e-4` | Revenue `1e-4` | Difference |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-03-22 to 2026-03-29 | 672 | 0.5 s | 1,074.13 EUR | 0.7 s | 1,074.13 EUR | 0.00 EUR |
| March 2026 | 2,972 | 2.0 s | 5,188.60 EUR | 3.0 s | 5,188.60 EUR | 0.01 EUR |
| April 2026 | 2,880 | 3.3 s | 5,122.47 EUR | 3.4 s | 5,122.47 EUR | 0.00 EUR |
| May 2026 | 2,976 | 2.0 s | 4,954.60 EUR | 6.2 s | 4,956.02 EUR | 1.42 EUR (0.03 %) |
| June 2026 | 2,880 | 2.3 s | 5,416.85 EUR | 3.4 s | 5,417.74 EUR | 0.89 EUR (0.02 %) |
| July 2026 | 2,976 | 2.1 s | 4,275.37 EUR | 3.2 s | 4,275.38 EUR | 0.02 EUR |
| September 2026 | 2,880 | 1.7 s | 6,377.90 EUR | 2.8 s | 6,377.98 EUR | 0.08 EUR |

Without a gap (review round 1): the March week and March 2026 failed with 500 after 30 s,
July 2026 took 25.1 s.

Flat negative blocks between 8 quarter hours at 50 EUR/MWh on each side, example battery,
time limit 30 s:

| Block | `1e-4` | `5e-3` |
| --- | --- | --- |
| 24 × -500 | 22.6 s | 0.2 s |
| 28 × -500 and longer | 500 after 30 s | |
| 48 × -500 (regression test) | 500 after 30 s | 0.2 s |
| 28 × -10 | 500 after 30 s | 0.2 s |
| 48 × -10 (regression test) | 500 after 30 s | 0.1 s |
| 96 × -500, no positive prices (regression test) | 500 after 30 s | 0.2 s |

Plausibility of the 2026-10-25 schedule (times in UTC; prices from -0.01 to
71.61 EUR/MWh), unchanged from the first round:

- No quarter hour with both charging and discharging. Stored energy recomputed from the
  schedule matches `soc_kwh` within 7.4e-6 kWh; it stays within 100 to 900 kWh and ends
  at 500 kWh, the initial value. Revenue recomputed from the schedule matches.
- Charging at an energy-weighted average of 5.76 EUR/MWh (range -0.01 to 22.59),
  discharging at 28.47 EUR/MWh (range 0.00 to 71.61).
- Main cycle: charging to 900 kWh from 12:45 to 14:15 at -0.01 to 0.00 EUR/MWh, the
  cheapest quarter hours of the day; discharging from 16:15 to 18:00 at 61.51 to
  71.61 EUR/MWh, the most expensive (peak 71.61 at 16:45).
- Without degradation cost the solver also runs small cycles at night around
  0 EUR/MWh, worth fractions of a cent; listed under known limitations.

The optimiser was also run at all 16 corner combinations of the new bounds (capacity and
both powers at 0.1 and 10,000,000, efficiencies 0.5 and 1) on three price curves, with
`1e-4`: no simultaneous charge and discharge, no bound violation, final energy not below
initial, relative balance error below 1e-5. Not repeated with `5e-3`; the gap only
changes when the search stops, not the constraints.

Attention points for the reviewer:

- The unit tests now use the production default gap (`OptimizationConfig().mip_gap_rel`).
  The hand-calculated cases still match exactly.
- The regression test `test_flat_negative_blocks_solve_quickly` asserts a solver time
  below 10 s; it takes about 0.2 s per case here. It fails with a gap of `1e-4` (all
  three cases hit the time limit).
- PuLP does not report whether CBC ended with a full proof or at the gap, so `optimal`
  always means "optimal within 0.5 %".
- Multi-day runs of identical or near-identical negative prices can still reach the 30 s
  limit (figures from review round 2); documented as a known limitation in `problem.md`
  and ADR 0003, not changed in code.
- CBC writes its solution with limited precision (for example `soc_kwh: 368.42105`), so
  the balance holds to about 1e-5 kWh. The unit tests use a tolerance of 1e-4.
- Output values are not rounded (for example `revenue_eur: 50.92209521175`).
- Each request starts a CBC subprocess from a worker thread; concurrent requests run
  concurrent CBC processes, limited only by the default thread pool. A request that hits
  the time limit would keep one core busy for 30 s.
- Only x86_64 was checked in Docker. PuLP 3.3.2 also ships a Linux ARM64 CBC binary,
  which was not tested.

## Review

### Round 1

- Reviewer: Claude Code (Claude Opus 5.5, `claude-opus-5-5`), fresh context, 2026-10-26
- Inputs: this plan including Implementation notes and Handoff; `git diff develop`
  (`develop` at `8ac7ae5`, 14 tracked files) plus all untracked files from
  `git status --short`, read in full; ADR 0001 to 0003, `api.md`, `problem.md`,
  `development.md`, `workflow.md`, `plans/README.md`, `plans/TEMPLATE.md`; PuLP 3.3.2
  CBC status handling in `.venv`; SMARD day-ahead prices (filter 4169, quarter hour)
  fetched into memory for experiments, nothing written to the database.
- Checks performed:
  - `uv run ruff check .`: passed. `uv run ruff format --check .`: passed, 72 files
    already formatted. `uv run pyright`: 0 errors, 0 warnings. `uv lock --check`: passed.
  - `docker compose up -d db` (healthy after about 6 s), then
    `BATTERY_DISPATCH_REQUIRE_DB=1 uv run pytest`: 81 passed, none skipped, 4.9 s.
    `docker compose stop db`: done.
  - `uv run pre-commit run --all-files`: all hooks passed; diff fingerprint unchanged
    afterwards. Untracked files checked by hand: no trailing whitespace, no CRLF, final
    newlines present, no em dashes, no process terms in code or product docs.
  - Mutation checks on the optimiser tests: dropping the exclusivity constraints fails
    `test_no_simultaneous_charge_and_discharge`; dropping the final-energy constraint
    fails 4 tests; multiplying instead of dividing by the discharge efficiency in the
    balance fails 3 tests. The tests guard R2 to R4.
  - Optimiser experiments (example battery unless stated): soc_initial at soc_min or
    soc_max, lossless, single step, prices of +/-1e6 EUR/MWh, asymmetric power, 31
    synthetic days (2,976 steps, 2.0 s): balance error at most 1.5e-5 kWh, no bound
    violation, never charge and discharge in one step, final energy never below initial.
    Units checked by hand: EUR/MWh / 1000 * kW * 0.25 h = EUR.
  - Solver status handling checked against PuLP 3.3.2 `COIN_CMD.get_status`: a run stopped
    at the time limit with an incumbent maps to `LpSolutionIntegerFeasible`, which the
    optimiser rejects as intended. Temporary files use `uuid4` names, so concurrent
    solves do not collide.
  - Real data, in memory: all 123 Europe/Berlin days of May to August 2026 solve in at
    most 0.4 s each (May 2026 includes a day with a minimum of -499.99 EUR/MWh).
    31-day windows from October 2025 to September 2026: see finding 1.
  - Route experiments with `TestClient`, the real `DispatchPlanner` and an in-memory
    repository: offset `+05:45` on a quarter-hour boundary accepted, `+05:30` off the
    boundary 422, date without time 422, `start == end` 422, a 15-minute range 200, a
    partially stored range 409 with the correct `expected`, `found` and `first_missing`.
    Unknown battery fields are ignored (200). See findings 2, 4 and 5 for the failures.

| # | Severity | Location | Finding and evidence | Suggested fix | Resolution |
| --- | --- | --- | --- | --- | --- |
| 1 | major | `battery_dispatch/optimization/milp_optimizer.py:147` | Valid requests on real data run into the 30 s time limit and fail with 500. Reproduced through `POST /dispatch/optimize` (real planner, prices from SMARD in memory, default configuration, example battery from README and `api.md`): `2026-03-22T00:00:00+01:00` to `2026-03-29T00:00:00+01:00` answers 500 `solver stopped without an optimal solution: Solution Found` after 30.1 s. The calendar month March 2026 (2,972 steps) fails the same way, July 2026 (31 days) needs 25.1 s of solver time on this machine, so it will fail on slower hardware such as a container or CI runner. The other monthly windows from October 2025 to September 2026 take 0.8 to 7.5 s. CBC log for a synthetic case (96 quarter hours at -500 EUR/MWh): incumbent 506.875 EUR against a bound of 507.227 after 86,000 nodes, so it is a proof-of-optimality problem of the big-M formulation, not a missing solution. Flat negative blocks fail reliably: 24 or more quarter hours at -500, or 28 quarter hours at -10 EUR/MWh between positive prices. With `gapRel=1e-4` the March month solves in 3.0 s and July in 3.2 s (CBC then reports `Optimal`); with `degradation_cost_eur_per_mwh: 10` the March week solves in 0.2 s. Restricting the binaries to steps with negative prices halves the July time (12.6 s) but does not fix the flat blocks. Each failing request also keeps one worker thread and one CPU core busy for the full time limit. | Pass a small relative MIP gap to CBC (for example `gapRel=1e-4`, optionally configurable) and state in ADR 0003 and `api.md` that the result is optimal within that gap; consider binaries only where `p_t < 0`. Add a regression test with a long flat negative block that must solve well within the time limit. | Fixed. New setting `optimization.mip_gap_rel` passed to CBC as `gapRel`, default `5e-3` as decided by the user (0.01 % still left flat negative blocks of 28 or more quarter hours at the time limit). Status `optimal` documented as optimal within 0.5 % in ADR 0003, `api.md` and `problem.md`. The week of 2026-03-22 solves in 0.5 s, March 2026 in 2.0 s (Docker: 2.6 s), July 2026 in 2.1 s; all measured months 1.7 to 3.3 s, at most 1.42 EUR (0.03 %) below the 0.01 % result. Regression test `test_flat_negative_blocks_solve_quickly` added (48 × -500, 48 × -10, 96 × -500; about 0.2 s each). Binaries only where `p_t < 0` not introduced. |
| 2 | minor | `docs/decisions/0003-milp-for-battery-dispatch.md:44` | The ADR says a 31-day request "took about two seconds in a test run". Real 31-day windows take 0.8 to 25 s and one fails at 30 s (finding 1), so the consequence as written is not accurate. | Update the runtime statement once finding 1 is fixed, with the measured range. | Fixed. ADR 0003 states the measured range with the default gap of `5e-3`: 1.7 to 3.3 s of solver time for the calendar months March to July and September 2026, 0.5 s for the week of 22 March 2026, about 0.2 s for the synthetic one-day blocks, and the residual case of multi-day negative runs (round 2 finding 1). |
| 3 | note | `battery_dispatch/communication/http/api/models.py:84` | As raised in the Handoff: the strict `timedelta(days=31)` rejects the Europe/Berlin calendar month October (31 days and 1 hour, 2,980 steps) with 422, while the plan's figure of 2,980 binaries suggests it was meant to fit. Reproduced: `2026-09-30T00:00:00+02:00` to `2026-10-31T00:00:00+01:00` gives 422. | User decision: keep 31 days, or allow 31 days plus 1 hour (or 2,980 quarter hours) and update `api.md`. | Fixed as decided by the user: `max_span` is 31 days and one hour; `api.md` updated; route tests accept 2026-09-30T00:00+02:00 to 2026-10-31T00:00+01:00 and reject one hour more. |
| 4 | minor | `battery_dispatch/communication/http/api/models.py:57` | Non-finite numbers in the battery parameters give 500 instead of 422, contrary to the plan's validation section. Reproduced with `TestClient`: `"capacity_kwh": Infinity`, `"soc_min": NaN` and `"degradation_cost_eur_per_mwh": 1e400` each answer 500 `Internal Server Error`; validation rejects them, but the default handler cannot serialise the offending input. No test covers it. | Register a `RequestValidationError` handler that serialises inputs safely (for example `jsonable_encoder` after replacing non-finite floats, or dropping `input`), and add the three cases to `test_optimize_rejects_invalid_request`. | Fixed. `RequestValidationError` handler in `server.py` replaces non-finite floats by strings; `Infinity`, `NaN` and `1e400` added to the invalid-request tests (422). |
| 5 | note | `battery_dispatch/communication/http/api/models.py:59` | No plausibility bounds on magnitudes. `capacity_kwh: 1e300` returns 500 `No Solution Exists` although doing nothing is always feasible; `1e20` returns `No Solution Found`. At `capacity_kwh: 1e-6` the absolute `ZERO_TOLERANCE` of 1e-6 sets stored energies to 0, below `soc_min` (1e-7 kWh), and the revenue to 0. Realistic sizes from 0.01 kWh to 1e15 kWh are unaffected. | Optionally add upper and lower bounds to the battery fields (and a lower bound on the efficiencies) so that 422 is returned instead of a misleading solver error. | Fixed as decided by the user: power and capacity 0.1 to 10,000,000, efficiencies 0.5 to 1, degradation cost at most 10,000; boundary values tested as accepted and just outside as rejected; documented in `api.md`. |
| 6 | note | `battery_dispatch/optimization/milp_optimizer.py:150` | The `PulpSolverError` path and the `_value` path for a missing solver value (line 164) are not exercised by any test; the route test for 500 uses a fake planner. | Optionally add a unit test that patches `LpProblem.solve` to raise `PulpSolverError`. | Fixed. `test_solver_error_raises` and `test_missing_solver_value_raises` patch `LpProblem.solve`. |
| 7 | note | `docs/api.md:65` | The curl example reads `optimize   -H ...   -d '{`, apparently line continuations lost in editing. It still works but differs from the formatting of the other examples. | Restore the `\` line continuations. | Fixed. Line continuations restored. |

Verdict: changes required

### Round 2

- Reviewer: Claude Code (Claude Opus 5.5, `claude-opus-5-5`), fresh context, 2026-10-26
- Inputs: this plan including Implementation notes (with the user decisions after round 1),
  Handoff and Round 1 with its Resolution column; `git diff develop` (`develop` at
  `8ac7ae5`, 14 tracked files) plus all untracked files from `git status --short`, read in
  full; ADR 0001 to 0003, `api.md`, `problem.md`, `development.md`, `workflow.md`,
  `plans/TEMPLATE.md`; PuLP 3.3.2 `COIN_CMD.getOptions` and `get_status` in `.venv`;
  SMARD day-ahead prices (filter 4169, quarter hour) for March to July 2026 fetched into
  memory, nothing written to the database.
- Checks performed:
  - `uv run ruff check .`: passed. `uv run ruff format --check .`: passed, 72 files
    already formatted. `uv run pyright`: 0 errors, 0 warnings. `uv lock --check`: passed.
  - `docker compose up -d db` (healthy after about 6 s), then
    `BATTERY_DISPATCH_REQUIRE_DB=1 uv run pytest`: 104 passed, none skipped, 6.4 s; the
    three `test_flat_negative_blocks_solve_quickly` cases take 0.1 to 0.2 s each.
    `docker compose stop db`: done.
  - `uv run pre-commit run --all-files`: all hooks passed.
    `uv run pre-commit run --files` on the 15 untracked files: all hooks passed. Diff and
    status fingerprints unchanged afterwards. No em dashes in code, tests or docs; no
    process terms in code or product docs.
  - Round 1 resolutions: finding 1, `gapRel` reaches CBC as `-ratio 0.005` (PuLP
    `getOptions`, also for `0.0`); a CBC solution line starting with `Optimal` maps to
    `LpSolutionOptimal`, `Stopped on time - objective value` still to
    `LpSolutionIntegerFeasible`, which raises. Real prices with the example battery and
    the default configuration: week of 2026-03-22 0.46 s, March 2026 1.9 s, April 3.7 s,
    May 2.5 s, June 2.8 s, July 2.2 s, revenues identical to the Handoff table. The
    regression case 48 x -10 EUR/MWh between 50 EUR/MWh fails with `1e-4` after 30 s, so
    the test guards the gap. Findings 3 and 4 reproduced as fixed with `TestClient`:
    31 days and one hour 200, 15 minutes more 422; `-Infinity`, `NaN` in two fields,
    `Infinity` as `start`, as the whole body, inside a list and as the `battery` object all
    give 422 with the inputs as `"inf"`, `"-inf"`, `"nan"`; `/prices` and
    `/prices/import` validation errors keep the default body. Finding 5: bounds match the
    user decision; corners of the bounds (capacity 0.1 with power 10,000,000 and the
    reverse, efficiency 0.5, 0.99 and 1) solve with gap `5e-3` without simultaneous
    charge and discharge, bound violation or final energy below initial, relative balance
    error below 2e-8. Findings 6 and 7: fixed as stated.
  - Synthetic stress cases with gap `5e-3`, see finding 1.

| # | Severity | Location | Finding and evidence | Suggested fix | Resolution |
| --- | --- | --- | --- | --- | --- |
| 1 | minor | `docs/problem.md:103` | The known limitation says a time-limit failure "has not happened on the measured real or synthetic price curves", and ADR 0003 (`docs/decisions/0003-milp-for-battery-dispatch.md:48`, `:57`) says CBC with 0.5 % is fast enough and cites only blocks up to one day. Longer runs of near-identical negative prices still reach the limit with the default configuration and the example battery (`optimize` called directly, time limit 30 s): 192 x -500 EUR/MWh 2.2 s, 384 x -500 12.6 s, 672 x -500 (one week) 27.3 s, 1,344 x -500 and 2,976 x -500 or -0.01 fail with `Solution Found` after 30 s; 384 x -10 between 50 EUR/MWh 3.3 s, 672 x -10 18.2 s; a 31-day month of -100 +/- 0.5 EUR/MWh fails; a 31-day month with a daily 6 h block at -50 and 80 EUR/MWh otherwise takes 9.6 s. None of this occurs in the measured real months, so the behaviour is acceptable, but the documented limit is narrower than stated and a slower host has less headroom. | Document the residual case: runs of near-identical negative prices longer than a few days can still exceed the time limit and answer 500; keep HiGHS as the named fallback in ADR 0003. No code change needed. | Fixed. `problem.md` (Near-optimal results) and ADR 0003 (new consequence "Residual case") describe multi-day runs of identical or near-identical negative prices that still reach the 30 s limit, with the measured figures from this round; HiGHS via `highspy` stays the named fallback in the alternatives table and the consequence. No code change. |
| 2 | minor | `battery_dispatch/communication/http/api/models.py:27` | The 422 message for a too long dispatch range says `time range must not exceed 31 days`, but `DispatchRequest.max_span` (`models.py:88`) is 31 days and one hour. Reproduced: `2026-09-30T00:00:00+02:00` to `2026-10-31T00:15:00+01:00` answers 422 `Value error, time range must not exceed 31 days`, while 31 days and one hour is accepted. The message formats only `max_span.days` and drops the hour. | Build the message from the full `timedelta` (for example "31 days and 1 hour", or `str(self.max_span)`), and assert the message in the route test for the too long range. | Fixed. `TimeRange` builds the message from the full `max_span` (`_describe` in `models.py`): "31 days and 1 hour" for dispatch, unchanged "92 days" and "366 days" for the price endpoints. New tests `test_too_long_range_names_the_limit` (dispatch) and `test_import_too_long_range_names_the_limit`, `test_get_prices_too_long_range_names_the_limit` (prices) assert the messages. |
| 3 | note | `docs/plans/wp1-dispatch-optimization.md:469` | The Round 1 Resolution of finding 2 says ADR 0003 states "3.0 to 6.0 s for the months March to July 2026", but the ADR (`0003-milp-for-battery-dispatch.md:56`) states 1.7 to 3.3 s, the figures with gap `5e-3`. The plan text is stale. | Update the Resolution text of round 1 finding 2. | Fixed. Resolution of round 1 finding 2 updated to the ADR's figures. |

Verdict: approve with minor findings
