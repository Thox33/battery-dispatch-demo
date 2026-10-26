# ADR 0003: Mixed-integer model for battery dispatch

Status: accepted, 2026-10-26

## Context

Battery arbitrage against a known price curve is usually written as a linear program:
charge and discharge power per quarter hour, an energy balance with efficiency losses,
power and state-of-charge limits, revenue as the objective.

With negative prices this linear program has a flaw. Charging and discharging in the same
quarter hour then earns money: the market pays for the energy taken from the grid, and the
efficiency losses destroy part of it, so less has to be sold back. The optimum of the
linear program is a schedule that no battery can run. Day-ahead prices in Germany are
negative on many hours a year, so this is not a corner case.

## Decision

- **One binary per quarter hour.** `u_t = 1` allows charging, `u_t = 0` allows
  discharging: `c_t <= max_charge_kw * u_t` and `d_t <= max_discharge_kw * (1 - u_t)`.
  This makes the model a small mixed-integer linear program.
- **Separate charge and discharge efficiency** in the energy balance, power measured at
  the grid connection.
- **Final energy at least the initial energy**, so a schedule cannot earn money by emptying
  the battery.
- **Optional degradation cost** per discharged MWh, default 0.
- **PuLP 3 with its bundled CBC solver**, pinned to `pulp>=3.3,<4`. The solver runs as a
  subprocess with a configurable time limit (`optimization.solver_time_limit_s`, 30 s).
- **Optimal within a relative gap of 0.5 %** (`optimization.mip_gap_rel`, `5e-3`). CBC
  stops once the objective of the best schedule found is proven to be at most 0.5 % below
  the best possible one. Proving exact optimality can take far longer than finding the
  schedule: on real prices of March 2026, a week did not finish within 30 s without a gap.
  Long runs of identical negative prices are the hardest case: burning energy through
  efficiency losses then pays, many alternating schedules earn almost the same, and the
  proof needs exponentially many branches. Status `optimal` in the response means optimal
  within this gap. Any other result, in particular a schedule found but not proven when
  the time limit is reached, is an error.

Alternatives considered:

| Alternative | Why not |
| --- | --- |
| Plain LP, reject results with simultaneous charging and discharging | Gives no answer exactly on the days with negative prices, which are the interesting ones |
| Plain LP with a small penalty on charge plus discharge | Works only if the penalty outweighs the most negative price; the right size depends on the data and it distorts the revenue |
| `scipy.optimize.milp` with HiGHS | Solves the same model well, but the matrix formulation is harder to read and review than named variables and constraints |
| PuLP 4 | No longer bundles a solver and changed the modelling API; PuLP 3 needs no extra installation |
| Relative gap of 0.01 % | In synthetic tests with the example battery, 28 or more equal quarter hours at a negative price did not finish within 30 s; real calendar months took up to 6.2 s instead of 3.3 s |
| HiGHS via `highspy` | Proved the synthetic one-day cases within 0.01 % in at most 6.2 s, but adds a dependency; with a gap of 0.5 % CBC is fast enough on real prices. Remains the fallback if the residual case below matters |

## Consequences

- The schedule is physically valid for any price curve, including negative prices.
- One day has 92 to 100 binaries and solves in well under a second. The API limits a
  request to 31 days and one hour, so every calendar month in Europe/Berlin fits, at most
  2,980 binaries. Measured on real prices with the example battery from `api.md`: the
  calendar months March to July and September 2026 took 1.7 to 3.3 s of solver time, the
  week of 22 March 2026 0.5 s. Synthetic runs of 48 quarter hours at -500 or -10 EUR/MWh,
  and a whole day at -500 EUR/MWh, solve in about 0.2 s.
- Compared with a gap of 0.01 %, the monthly revenue was at most 1.42 EUR (0.03 %) lower
  on these months, well inside the guaranteed 0.5 %.
- Residual case: runs of identical or near-identical negative prices lasting several days
  can still exceed the time limit and answer 500. Measured with the example battery and
  the default configuration: about one week at -500 EUR/MWh took 27 s; two weeks at
  -500 EUR/MWh, and a whole month at -500, at -0.01 or at -100 +/- 0.5 EUR/MWh, stopped
  at the 30 s limit. None of this occurs in the measured real months. A slower host has
  less headroom. If such price curves matter, HiGHS via `highspy` is the fallback.
- Starting CBC as a subprocess costs some milliseconds per request. The solve is
  synchronous and runs in a worker thread.
- PuLP has no type information; the optimiser builds its expressions from explicit
  coefficient lists so that type checking still covers the model code.
- PuLP 3 warns about deprecations in favour of PuLP 4. The warnings are filtered in the
  tests. Moving to PuLP 4 or HiGHS later only touches the optimiser module.
- The bundled CBC binary exists for Linux, macOS and Windows on x86_64 and for Linux on
  ARM64. On other platforms HiGHS via `highspy` would be the fallback.
