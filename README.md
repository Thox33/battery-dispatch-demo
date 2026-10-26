# battery-dispatch-demo

Dispatch planning for a battery storage system against day-ahead electricity prices. The
application fetches wholesale prices for Germany from the open SMARD API of the German
Federal Network Agency, stores them in TimescaleDB and computes a revenue-maximising
charge and discharge schedule.

A small demonstration project, not a product. Status: price import works, optimisation
is next.

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

## Documentation

- [Problem and background](docs/problem.md)
- [API: time ranges, endpoints, errors](docs/api.md)
- [Development: structure, tooling, branches](docs/development.md)
- [Architecture decisions](docs/decisions/)

## License

MIT, see [LICENSE](LICENSE).
