# API

The interactive OpenAPI description is served at `/docs` while the application runs.
This page covers the rules that apply across endpoints.

## Time ranges

- All ranges are half-open: `[start, end)`. A price belongs to the range if the quarter
  hour starts at or after `start` and before `end`.
- `start` and `end` must carry a timezone offset, for example `2026-10-26T00:00:00+01:00`
  or `2026-10-25T23:00:00Z`. Times without an offset are rejected with 422.
- Responses always use UTC.
- One calendar day in Europe/Berlin is `T00:00:00+01:00` (or `+02:00` in summer) to the
  next midnight. On the days of the daylight saving time change this gives 92 or 100
  quarter hours.

## `POST /prices/import`

Loads day-ahead prices for Germany/Luxembourg from SMARD and stores them.

```bash
curl -X POST localhost:8000/prices/import \
  -H 'content-type: application/json' \
  -d '{"start": "2026-10-25T00:00:00+02:00", "end": "2026-10-26T00:00:00+01:00"}'
```

```json
{"start": "2026-10-24T22:00:00Z", "end": "2026-10-25T23:00:00Z", "fetched": 100, "written": 100}
```

- `fetched`: prices SMARD published for the range. Quarter hours without a published value
  are left out.
- `written`: rows inserted or changed. Repeating an import returns `written: 0`.
- The range may span at most 92 days, since every week is one request to SMARD.
- 502 if SMARD is unreachable or returns data in an unexpected shape.

## `GET /prices`

Returns stored prices, ordered by time. Ranges up to 366 days.

```bash
curl 'localhost:8000/prices?start=2026-10-25T22:00:00Z&end=2026-10-25T22:30:00Z'
```

```json
{
  "bidding_zone": "DE-LU",
  "unit": "EUR/MWh",
  "prices": [
    {"time": "2026-10-25T22:00:00Z", "price_eur_per_mwh": 20.1},
    {"time": "2026-10-25T22:15:00Z", "price_eur_per_mwh": 14.92}
  ]
}
```

Quarter hours that were not imported are missing from the list; the endpoint does not
fill gaps.

## `POST /dispatch/optimize`

Computes the revenue-maximising charge and discharge schedule for a battery from the
stored prices of the range. The model is described in [problem.md](problem.md#optimisation).

```bash
curl -X POST localhost:8000/dispatch/optimize \
  -H 'content-type: application/json' \
  -d '{
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
  }'
```

Response, schedule shortened:

```json
{
  "start": "2026-10-24T22:00:00Z",
  "end": "2026-10-25T23:00:00Z",
  "bidding_zone": "DE-LU",
  "revenue_eur": 50.92209521175,
  "degradation_cost_eur": 0.0,
  "charged_kwh": 2553.67036,
  "discharged_kwh": 2304.6875,
  "equivalent_full_cycles": 2.880859375,
  "solver": {"status": "optimal", "runtime_ms": 23},
  "schedule": [
    {"time": "2026-10-24T22:00:00Z", "price_eur_per_mwh": 9.67,
     "charge_kw": 0.0, "discharge_kw": 500.0, "soc_kwh": 368.42105},
    {"time": "2026-10-24T22:15:00Z", "price_eur_per_mwh": 9.52,
     "charge_kw": 0.0, "discharge_kw": 500.0, "soc_kwh": 236.84211}
  ]
}
```

Request:

- `start` and `end` follow the time range rules above, lie on quarter-hour boundaries and
  span at most 31 days and one hour, so that every calendar month in Europe/Berlin fits,
  including October with the end of summer time.
- `capacity_kwh`, `max_charge_kw` and `max_discharge_kw` lie between 0.1 and 10,000,000.
  Power is measured at the grid connection.
- `charge_efficiency` and `discharge_efficiency` lie between 0.5 and 1.
- `soc_min`, `soc_max` and `soc_initial` are fractions of the capacity with
  `0 <= soc_min < soc_max <= 1` and `soc_min <= soc_initial <= soc_max`.
- `degradation_cost_eur_per_mwh` is optional, between 0 and 10,000, default 0. It is
  charged on discharged energy.
- All numbers must be finite; `Infinity` and `NaN` are rejected.

Response:

- `revenue_eur`: income from discharging minus the cost of charging. The degradation cost
  is reported separately in `degradation_cost_eur` and not deducted.
- `charged_kwh`, `discharged_kwh`: energy at the grid connection.
- `equivalent_full_cycles`: discharged energy divided by the energy between `soc_min` and
  `soc_max`.
- `schedule`: one entry per quarter hour. `soc_kwh` is the stored energy at the end of
  the quarter hour.
- `solver.status`: `optimal` means optimal within a relative gap of 0.5 %: the revenue
  minus degradation cost is proven to be at most 0.5 % below the best possible value.
  The gap is set by `optimization.mip_gap_rel` in the configuration.
- `solver.runtime_ms`: time spent in the solver.

Every quarter hour of the range needs a stored price. If one is missing, the endpoint
answers 409 and names the first gap; import the range first:

```json
{"detail": {"message": "prices for the range are incomplete, import them first",
            "expected": 96, "found": 0, "first_missing": "2026-11-10T00:00:00Z"}}
```

## Errors

| Status | Meaning |
|---|---|
| 409 | Prices for the requested range are incomplete |
| 422 | Invalid request, for example a reversed or too long range |
| 500 | The solver did not prove a solution optimal within the gap before the time limit |
| 502 | SMARD failed during an import |
| 503 | Database unavailable; `/health` reports which component is down |
