# battery-dispatch-demo

Dispatch planning for a battery storage system against day-ahead electricity prices. The
application fetches wholesale prices for Germany from the open SMARD API of the German
Federal Network Agency, stores them in TimescaleDB and computes a revenue-maximising
charge and discharge schedule.

A small demonstration project, not a product. Status: price import, optimisation and a
web page with the schedule work; a comparison with a simple strategy is open.

![Schedule for 25 October 2026](docs/images/ui.png)

## Quick start

Requirements:

- Docker with docker compose, running (Docker Desktop on Windows and macOS).
- Internet access: the first start downloads about 700 MB of images and Python
  packages, and prices come from SMARD.
- Free ports 5432 and 8000, or other ports set as `DB_PORT` and `API_PORT` in `.env`.

```bash
cp .env.example .env
docker compose up --build
```

The commands here are for a POSIX shell such as bash, zsh or Git Bash. In Windows
PowerShell 5.1, `curl` is an alias of `Invoke-WebRequest` and the examples below do not
work as written; a PowerShell version of the import follows them.

The page at <http://localhost:8000/> optimises today's schedule and imports missing prices
on its own, see [docs/ui.md](docs/ui.md). The API answers at
<http://localhost:8000/health>, the OpenAPI description is at
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

The import in Windows PowerShell:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/prices/import `
  -ContentType 'application/json' `
  -Body '{"start": "2026-10-25T00:00:00+02:00", "end": "2026-10-26T00:00:00+01:00"}'
```

## Documentation

- [Problem and background](docs/problem.md)
- [API: time ranges, endpoints, errors](docs/api.md)
- [Web page: use, charts, mapping to the API](docs/ui.md)
- [Development: structure, tooling, branches](docs/development.md)
- [Architecture decisions](docs/decisions/)
- [Workflow: planner, builder, reviewer](docs/workflow.md) and [plans](docs/plans/)

## License

MIT, see [LICENSE](LICENSE). The bundled chart library uPlot is MIT licensed as well, see
`battery_dispatch/communication/http/frontend/vendor/LICENSE`.

Price data: Bundesnetzagentur | [SMARD.de](https://www.smard.de), licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
