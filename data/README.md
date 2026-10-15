# Data

- `observed_runs.csv` — the four exploratory runs reported in the paper (one run per configuration; not a statistical benchmark).

## Server log schema (`jaula.log`, JSON Lines)

One line per cage visit (requests to `robots.txt`, the decoy root page, and HTTP 503 responses are not logged). Keys are in Spanish, as emitted by the server.

| Field | Meaning |
|---|---|
| `ts` | local timestamp (`%Y-%m-%dT%H:%M:%S`) |
| `ip` | client IP |
| `ua` | client `User-Agent` |
| `ruta` | requested path |
| `segundos` | seconds the connection was held |
| `bytes` | bytes delivered |
