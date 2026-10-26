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

## Errors

| Status | Meaning |
|---|---|
| 422 | Invalid request, for example a reversed or too long range |
| 502 | SMARD failed during an import |
| 503 | Database unavailable; `/health` reports which component is down |
