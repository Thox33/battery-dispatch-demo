# battery-dispatch-demo

Dispatch planning for a battery storage system against day-ahead electricity prices. The
application fetches wholesale prices for Germany from the open SMARD API of the German
Federal Network Agency, stores them in TimescaleDB and computes a revenue-maximising
charge and discharge schedule.

A small demonstration project, not a product. Status: price import, optimisation and a
web page with the schedule work; a comparison with a simple strategy is open.

![Schedule for 29 July 2026](docs/images/ui.png)

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

Then open <http://localhost:8000/>. The page computes today's schedule and loads missing
prices from SMARD on its own, see [docs/ui.md](docs/ui.md). The API is described at
<http://localhost:8000/docs> and in [docs/api.md](docs/api.md), with examples.

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
