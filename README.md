# battery-dispatch-demo

Dispatch planning for a battery storage system against day-ahead electricity prices. The
application fetches wholesale prices for Germany from the open SMARD API of the German
Federal Network Agency, stores them in TimescaleDB and computes a revenue-maximising
charge and discharge schedule.

A small demonstration project, not a product. Status: price import and optimisation
work; a comparison with a simple strategy and a chart of the schedule are open.

## Quick start

Requires Docker with docker compose.

```bash
cp .env.example .env
docker compose up --build
```

The API answers at <http://localhost:8000/health>, the OpenAPI description is at
<http://localhost:8000/docs>. To load one day of prices:

```bash
curl -X POST localhost:8000/prices/import -H 'content-type: application/json' \
  -d '{"start": "2026-10-25T00:00:00+02:00", "end": "2026-10-26T00:00:00+01:00"}'
```

To compute the schedule of a 1 MWh, 500 kW battery for that day:

```bash
curl -X POST localhost:8000/dispatch/optimize -H 'content-type: application/json' \
  -d '{"start": "2026-10-25T00:00:00+02:00", "end": "2026-10-26T00:00:00+01:00",
       "battery": {"capacity_kwh": 1000, "max_charge_kw": 500, "max_discharge_kw": 500,
                   "charge_efficiency": 0.95, "discharge_efficiency": 0.95,
                   "soc_min": 0.1, "soc_max": 0.9, "soc_initial": 0.5}}'
```

The response holds the schedule per quarter hour and the expected revenue. The model and
its limitations are described in [docs/problem.md](docs/problem.md).

## Documentation

- [Problem and background](docs/problem.md)
- [API: time ranges, endpoints, errors](docs/api.md)
- [Development: structure, tooling, branches](docs/development.md)
- [Architecture decisions](docs/decisions/)
- [Workflow: planner, builder, reviewer](docs/workflow.md) and [plans](docs/plans/)

## License

MIT, see [LICENSE](LICENSE).
