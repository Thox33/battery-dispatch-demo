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
| `POST /prices/import` | Load prices for a time range | planned |
| `GET /prices` | Query prices for a time range | planned |
| `POST /dispatch/optimize` | Compute schedule and expected revenue | planned |

If time permits: a comparison with a simple threshold strategy and a small chart of the
schedule.

Deliberately left out: user management, multi-tenancy, forecasting, connection to trading
venues.

## Optimisation

Battery arbitrage against a known price curve is a linear program:

- decision variables per time step for charging and discharging
- constraints for power limits, state-of-charge balance and state-of-charge limits
- objective: revenue from discharging minus cost of charging
- efficiency appears in the balance equation

With negative prices, a pure LP may charge and discharge at the same time, because
destroying energy through efficiency losses then earns money. How this is ruled out is
recorded in a separate architecture decision.

## Data source

SMARD by the German Federal Network Agency, open, no API key.

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

To be added once price import and optimisation are in place.
