# Problem

A battery storage system buys electricity when it is cheap and sells it when it is
expensive. With a known price curve, the revenue-maximising schedule can be computed
exactly. This project implements that as a small, complete backend service.

## Scope

1. **Fetch prices.** Retrieve day-ahead wholesale prices for the Germany/Luxembourg
   bidding zone from SMARD and store them as a time series. Repeated imports do not create
   duplicates.
2. **Compute the schedule.** From a price curve and battery parameters (capacity in kWh,
   charge and discharge power in kW, efficiency, state-of-charge limits), determine a
   schedule that maximises revenue.
3. **Expose it through an API.**

| Endpoint | Purpose | Status |
|---|---|---|
| `GET /health` | State of the application and the database | available |
| `POST /prices/import` | Load prices for a time range | available |
| `GET /prices` | Query prices for a time range | available |
| `POST /dispatch/optimize` | Compute schedule and expected revenue | available |

Details in [api.md](api.md). A web page at `/ui/` shows the schedule in two charts, see
[ui.md](ui.md).

If time permits: a comparison with a simple threshold strategy.

Deliberately left out: user management, multi-tenancy, forecasting, connection to trading
venues.

## Optimisation

Battery arbitrage against a known price curve is almost a linear program. Time steps are
the quarter hours of the range, `dt = 0.25 h`, with price `p_t` in EUR/MWh.

Variables per step:

- `c_t`, `d_t`: charge and discharge power in kW at the grid connection, between 0 and the
  maximum power
- `e_t`: stored energy in kWh at the end of the step, between `soc_min` and `soc_max`
  times the capacity
- `u_t`: binary, 1 allows charging, 0 allows discharging

Constraints:

- balance: `e_t = e_(t-1) + charge_efficiency * c_t * dt - d_t * dt / discharge_efficiency`,
  starting from `soc_initial` times the capacity
- exclusivity: `c_t <= max_charge_kw * u_t` and `d_t <= max_discharge_kw * (1 - u_t)`
- final energy: the battery ends with at least the energy it started with

Objective: maximise `sum_t (p_t * (d_t - c_t) - k * d_t) * dt / 1000` in EUR, where `k`
is the optional degradation cost in EUR per discharged MWh.

With negative prices, a pure LP without `u_t` charges and discharges at the same time,
because destroying energy through efficiency losses then earns money. The binary rules
this out and makes the model a small mixed-integer program, solved with CBC through
PuLP to optimality within a relative gap of 0.5 %. See
[ADR 0003](decisions/0003-milp-for-battery-dispatch.md).

## Data source

SMARD by the German Federal Network Agency, open, no API key. The data is published under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) and must be attributed as
"Bundesnetzagentur | SMARD.de"; the web page shows this line below its charts.

Index of available weekly packages, timestamps in milliseconds since epoch:

```
https://www.smard.de/app/chart_data/4169/DE/index_quarterhour.json
```

One weekly package:

```
https://www.smard.de/app/chart_data/4169/DE/4169_DE_quarterhour_<timestamp>.json
```

Response: `{"meta_data": {...}, "series": [[timestamp_ms, price], ...]}`. Filter `4169`
is the wholesale price for Germany/Luxembourg in EUR/MWh at quarter-hour resolution.
Negative prices are valid.

Points to keep in mind:

- Timestamps are UTC. A calendar day in Europe/Berlin has 92 or 100 quarter hours on the
  days of the daylight saving time change.
- Prices come in EUR/MWh, battery parameters in kW and kWh, one time step lasts 0.25 h.

## Known limitations

- **Perfect foresight.** The optimisation knows every price of the range in advance. Its
  revenue is an upper bound for what real trading on the day-ahead market could earn.
- **Price taker.** The schedule has no influence on prices; there are no bids, no
  auction and no market impact.
- **Wholesale prices only.** Grid fees, levies, taxes and trading costs are not included.
- **Simple battery model.** Constant efficiencies, no power limits depending on the state
  of charge, no auxiliary consumption, no ageing beyond the optional degradation cost.
- **Small spreads are used.** Without a degradation cost the battery cycles for any
  positive margin, even fractions of a cent. A degradation cost suppresses these cycles.
- **One range at a time.** Each request starts from `soc_initial` and must end with at
  least that energy. Consecutive days are not chained.
- **No gap filling.** Missing prices are reported, never interpolated.
- **Near-optimal results.** Schedules are optimal within a relative gap of 0.5 %, not
  exactly. If the solver cannot prove that within its time limit of 30 s, the request
  fails with 500. This did not happen on the measured real months, but it does happen
  for runs of identical or near-identical negative prices lasting several days, for
  example a week or more at -500 EUR/MWh or a whole month at -0.01 EUR/MWh. See
  [ADR 0003](decisions/0003-milp-for-battery-dispatch.md).
- **Day-ahead only.** No intraday or balancing markets, no forecasts.
