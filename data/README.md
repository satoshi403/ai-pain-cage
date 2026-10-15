# Data

- `observed_runs.csv` — the four exploratory runs reported in the paper (one run per configuration; not a statistical benchmark).

## Server log schema (`jaula.log`, JSON Lines)

| Field | Meaning |
|---|---|
| `ts` | UTC timestamp |
| `client` | client IP |
| `path` | requested path |
| `ua` / `ua_automated` | user-agent and a weak automated-client hint |
| `status` | `ok`, `max_hold`, `client_abort`, `busy_503`, `robots`, `root`, `not_found` |
| `bytes_delivered` / `body_size` | bytes sent vs full page size |
| `elapsed_s` | time the slot was held |
| `completed` | whether the full page was streamed |

