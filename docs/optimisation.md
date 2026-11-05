# Optimisation

This document answers what is computed and why the result can be trusted. The choice of model
and solver is explained in [ADR 0003](decisions/0003-milp-for-battery-dispatch.md).

## Model

Given a known price per quarter hour, find the charge and discharge power per quarter hour that
earns the most. The model is a mixed-integer linear program (MILP): a linear program in which
some variables may only take whole numbers.

| Symbol | Unit | Meaning |
| --- | --- | --- |
| `dt` | h | Length of a step, 0.25 |
| `p_t` | EUR/MWh | Day-ahead price of step `t`, may be negative |
| `k` | EUR/MWh | Optional degradation cost per discharged MWh, default 0 |
| `c_t`, `d_t` | kW | Charge and discharge power at the grid connection |
| `e_t` | kWh | Stored energy at the end of step `t` |
| `u_t` | 0 or 1 | 1 allows charging, 0 allows discharging |

The state of charge is the stored energy as a fraction of the capacity. `soc_min`, `soc_max`
and `soc_initial` are given in this form.

Bounds per step:

```text
0 <= c_t <= max_charge_kw
0 <= d_t <= max_discharge_kw
soc_min * capacity_kwh <= e_t <= soc_max * capacity_kwh
```

Constraints:

```text
balance:      e_t = e_(t-1) + charge_efficiency * c_t * dt - d_t * dt / discharge_efficiency
              with e_0 = soc_initial * capacity_kwh
exclusivity:  c_t <= max_charge_kw * u_t
              d_t <= max_discharge_kw * (1 - u_t)
final energy: e_T >= e_0, where T is the last step
```

Objective in EUR. The factor 1000 converts kWh to MWh:

```text
maximise sum_t (p_t * (d_t - c_t) - k * d_t) * dt / 1000
```

The binary `u_t` is needed because of negative prices. Without it, charging and discharging in
the same step earns money: the market pays for the energy taken, and the efficiency losses
destroy part of it, so less has to be sold back. No battery can run such a schedule.

The final energy constraint keeps a schedule from earning money by emptying the battery.

A small example: 100 kWh and 100 kW, efficiencies 0.9, limits 0 and 1, start at 0.5, prices 0
and 100 EUR/MWh. The first step charges 25 kWh for free, of which 22.5 kWh are stored. The
second step takes those 22.5 kWh back out, which ends at the initial 50 kWh and delivers
20.25 kWh to the grid at 81 kW. Revenue: 2.025 EUR.

## Why it is well posed

- **Doing nothing is always feasible.** With `c_t = d_t = 0` the energy stays at `e_0`. This
  meets the bounds because the API enforces `soc_min <= soc_initial <= soc_max`, and it meets
  the final energy constraint. It earns 0 EUR, so the best objective is never negative.
- **An optimum exists.** All variables are bounded. For each of the finitely many choices of
  `u_t`, what remains is a linear program over a closed, bounded set. The problem is therefore
  never unbounded and never without a solution. What can fail is the proof within the time
  limit, see below.
- **The exclusivity constraint uses the real limits.** Such a constraint often uses an arbitrary
  large constant, which weakens the bound the solver works with. Here the constant is the real
  power limit: `u_t = 1` takes nothing away from charging, `u_t = 0` forces it to zero. The bound
  stays weak all the same: while searching, the solver also considers fractions of `u_t`, and at
  `u_t = 0.5` a step may charge and discharge at half power. That is why long runs of identical
  negative prices are hard to prove, see the residual case in
  [ADR 0003](decisions/0003-milp-for-battery-dispatch.md#consequences).
- **Optima need not be unique.** Two schedules can earn the same, for example when two quarter
  hours have the same price. Another solver or solver version may return another schedule with
  the same revenue. Most tests therefore check properties and not whole schedules.

## Implementation

`optimize` in `optimization/milp_optimizer.py` takes prices and battery parameters and returns
a `Schedule`. It keeps no state and touches neither the database nor HTTP, so it can be tested
with a list of numbers. The only outside effect is the solver subprocess.

`DispatchPlanner` is the layer around it: it loads the prices, refuses incomplete ones and runs
`optimize` in a worker thread. See [architecture.md](architecture.md#optimising-a-schedule).

**Expressions from coefficient lists.** PuLP models are usually written with overloaded
operators, as in `problem += e[t] == e[t-1] + eta * c[t] * dt`. PuLP has no type information,
so strict type checking cannot follow such expressions. The code instead passes explicit lists
of `(variable, coefficient)` to `LpAffineExpression` and `LpConstraint`, which stay typed. The
equations are harder to read this way, so the module docstring writes them out.

**The gap.** CBC stops once the objective of the best schedule found is proven to be at most
`optimization.mip_gap_rel` below the best possible value. The default is `5e-3`, which is
0.5 %. Finding a good schedule is usually quick; proving exact optimality can take far longer.
The measured runtimes are in [ADR 0003](decisions/0003-milp-for-battery-dispatch.md).

**The solver status.** CBC reports a run stopped at the time limit with a usable schedule as
status "Optimal". The code therefore reads the solution status, `sol_status`, and accepts only
`LpSolutionOptimal`. Anything else raises `OptimizationError`, and the API answers 500. The
time limit is `optimization.solver_time_limit_s`, 30 s by default. Status `optimal` in the
response means optimal within the gap; PuLP does not report whether the gap or a full proof
ended the search.

**Key figures.** Revenue and energy come from the cleaned schedule, not from the objective
value of the solver. `revenue_eur` does not include the degradation cost, which is reported
separately as `degradation_cost_eur`.

## How it is checked

The tests recompute the balance, check the limits and work through small cases by hand. See
[testing.md](testing.md).

## Possible extensions

These are ideas, not plans.

- **Self-discharge:** a factor on `e_(t-1)` in the balance.
- **Cycle limit:** a bound on the sum of `d_t` over the range.
- **Value of the final energy:** a price on `e_T` in the objective, instead of requiring
  `e_T >= e_0`. Consecutive days could then be chained.
- **Limits depending on the state of charge:** lower power near full and empty, as extra linear
  constraints between `c_t`, `d_t` and `e_t`.
- **Depth-dependent ageing:** a cost by depth of discharge, approximated piecewise. This adds
  binaries and solve time.
- **Co-located generation:** a solar or wind profile and a shared grid connection limit.
- **Reserve markets:** capacity held back per step, with its own revenue.
- **Forecasts with a rolling horizon:** the model is solved again as prices become known. The
  result is then no longer an upper bound but an estimate of real operation.
