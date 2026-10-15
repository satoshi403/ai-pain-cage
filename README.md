# AI Pain Cage

**An experimental tarpit and performance model for studying the cost of autonomous AI agents crawling a web server.**

[![tests](https://github.com/satoshi403/ai-pain-cage/actions/workflows/tests.yml/badge.svg)](https://github.com/satoshi403/ai-pain-cage/actions/workflows/tests.yml)
[![license: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](LICENSE)
[![status: preliminary](https://img.shields.io/badge/status-preliminary-orange.svg)](#limitations)

By **Fredy Bahena Martínez** · [Kynicom System](https://github.com/satoshi403) · October 2026

> **Research prototype.** Results are preliminary (one run per configuration, local loopback, one small model).
> Read the [limitations](#limitations) and [ETHICS.md](ETHICS.md) before running or deploying anything.

## What is this?

Autonomous AI agents can traverse websites, call tools, and consume resources at machine speed. The AI Pain Cage asks a defensive question:

> Can a configurable web tarpit measurably increase the time and information-processing burden of an autonomous AI agent, and can its behavior be predicted with a simple mathematical model?

The server generates a deterministic maze of synthetic pages, linked together and streamed in small chunks with a configurable delay. A local agent (Ollama + `fetch_url` tool) explores it, and a small analytical model predicts fetch time, total runtime, and capacity.

Full write-up: **[paper/paper.md](paper/paper.md)** · Medium article: [I Built a Tarpit for AI Agents](https://medium.com/@fkap91/i-built-a-tarpit-for-ai-agents-heres-what-one-small-experiment-showed-b9e3ff728299)

## Key observations (preliminary)

| Run | Configuration | Fetches | Time in cage | Bytes received | Total time |
|---|---|---|---|---|---|
| 0 | Server unavailable (invalid) | 1 failed | 0.0 s | 0 | 85.9 s |
| 1 | 16 B/s nominal | 1 | 60.0 s | 1,016 | 178.4 s |
| 2 | 1,280 B/s nominal | 1 | 3.1 s | 3,936 | 146.5 s |
| 3 | Fast mode, agent v2 | 3 | 8.9 s | 11,280 | 502.3 s |

1. A server can hold an individual fetch for a configured time, **bounded by the client's timeout** and the server's own limit.
2. In fast mode the agent summarized synthetic filler as if it described a real application: **URL tracking is not semantic reliability.**
3. Two regimes: in slow mode network waiting dominates; in fast mode local CPU inference dominates (the cage was ~1.8% of Run 3's total time).

Predictions for slow-mode scenarios B and C and for the Erlang-B capacity model are **not yet validated** (see roadmap).

## Quick start

Requirements: Python 3.9+ (server and model: standard library only; agent: `requests`) and, for the agent, [Ollama](https://ollama.com) with a model pulled (`ollama pull llama3.2:3b`).

```bash
git clone https://github.com/satoshi403/ai-pain-cage.git
cd ai-pain-cage

# 1. Start the cage (slow mode: 16 B every 1 s). Binds to 127.0.0.1 by default.
python3 src/jaula_dolor.py --port 8080

#    ...or fast mode (128 B every 0.1 s)
python3 src/jaula_dolor.py --port 8080 --delay 0.1 --chunk 128

# 2. In another terminal, run the instrumented agent
python3 src/test_agent.py --min-fetches 3 --budget 60

# 3. Explore the analytical model (12 arrivals/min reproduces the 47-Erlang example in §8)
python3 src/pain_model.py --size 3760 --fetches 3 --slots 50 --rate 12

# 4. Follow the server's JSON Lines log
tail -f jaula.log

# 5. Run the unit tests
python3 -m unittest discover -s tests -v
```

### Server options

| Flag | Meaning | Default |
|---|---|---|
| `--chunk` | bytes per chunk (`c`) | 16 |
| `--delay` | seconds between chunks (`d`) | 1.0 |
| `--max-seg` | max seconds per cage, `T_max` | 300 |
| `--max-jaulas` | concurrent slots `N` (HTTP 503 when full) | 50 |
| `--host` / `--port` | bind address / port | `127.0.0.1` / 8080 |
| `--log` | JSON Lines log path | `jaula.log` |

### Server behavior notes

- A request is sent into the maze if its path starts with `/jaula/` **or** its `User-Agent` matches a list of known AI-crawler and scripting-client patterns (`AI_UA`). The latter receive the `/jaula/inicio` page whatever path they asked for. This also catches legitimate scripting clients such as `python-requests` or `python-httpx`.
- Page text is deterministic per path; the canary token is salted with a value generated at every server start.
- The server announces itself as `nginx/1.24.0` (basic camouflage).
- Only maze visits are logged (`ts`, `ip`, `ua`, `ruta`, `segundos`, `bytes`). `robots.txt`, the decoy root page, and HTTP 503 responses are not.
- Identifiers, log keys, and flags are in Spanish (`jaula` = cage, `max-seg` = max seconds, `max-jaulas` = max cages) and kept unchanged for reproducibility.

## The model in one minute

```
r      = c / d                                   nominal rate
t_f    = min( ceil(S / c) * d, B, T_max )        fetch duration
T_cage = sum_i t_f,i                             total time in the cage
T_tot  ≈ T_cage + m * t_LLM                      end-to-end time
eta    = T_cage / T_tot                          fraction spent in the cage
E      = lambda * W ;  B(E, N) via Erlang-B      blocking probability
```

Pending predictions (S = 3,760 B, t_LLM = 82.2 s, n = 3, m = 6) — **not measurements**:

| Scenario | Chunk / delay | Budget | Predicted cage time | Predicted total |
|---|---|---|---|---|
| A — fast | 128 B / 0.1 s | 60 s | 9 s | ~502 s |
| B — slow | 16 B / 1 s | 60 s | 180 s | ~673 s |
| C — slow, extended budget | 16 B / 1 s | 300 s | 705 s | ~1,198 s |

## Repository layout

```
ai-pain-cage/
├── src/
│   ├── jaula_dolor.py     # tarpit server (original experiment source)
│   ├── test_agent.py      # Ollama agent + harness (original v2 + local-only guard)
│   └── pain_model.py      # analytical model + Erlang-B (reference implementation)
├── tests/test_model.py    # unit tests (paper predictions, server behavior)
├── paper/paper.md         # full article
├── data/                  # observed runs + log schema
├── ETHICS.md              # intended use and boundaries
├── CITATION.cff
└── LICENSE
```

## Provenance of the code

- `src/jaula_dolor.py` is the server used in the experiments. Only comments, the module docstring, and CLI help/console messages were translated to English; behavior and generated pages are unchanged (the start page `/jaula/inicio` is 3,936 bytes, the size received in Run 2).
- `src/test_agent.py` is the v2 agent used in the experiments, plus one later addition: a guard that refuses to fetch any host other than `127.0.0.1`/`localhost`.
- `src/pain_model.py` is a reference implementation of the paper's equations, written after the experiments and checked against the paper's tables by the unit tests.

## Limitations

- **Tiny sample:** one run per configuration; no confidence intervals.
- **One small model** (`llama3.2:3b`, CPU only); stronger agents may behave very differently.
- **Loopback only:** no real network latency, proxies, or production HTTP behavior.
- **No normal-client baseline** yet, so no defensible end-to-end slowdown factor.
- **Defender cost not measured:** CPU, memory, sockets, and file descriptors are still unknown. The cost asymmetry is a hypothesis.
- **Fitted parameters:** page size and average inference time were derived from Run 3 itself.
- Global deadlines, loop detection, or relevance filters in real agents can cap the effect.

## Roadmap

- [ ] Exp. 1 — Validate slow-mode predictions (B, C) within 5%
- [ ] Exp. 2 — Baseline against a normal, undelayed endpoint
- [ ] Exp. 3 — ≥5 runs per configuration with mean, SD, and CIs
- [ ] Exp. 4 — Record `prompt_eval_count` / `eval_count` per call
- [ ] Exp. 5 — Compare agents (`qwen2.5:7b`, explicit global deadline)
- [ ] Exp. 6 — Measure defender CPU / RSS / sockets under concurrency
- [ ] Exp. 7 — Validate Erlang-B under smooth and bursty arrivals
- [ ] Exp. 8 — Content relevance and provenance scoring with decoys

## Responsible use

Run the cage only on infrastructure you control, never against third-party systems. `robots.txt` and user-agent matching are **not** security controls. See [ETHICS.md](ETHICS.md).

## Citation

See [CITATION.cff](CITATION.cff), or:

```
Bahena Martínez, F. (2026). The AI Pain Cage: Designing and Modeling a Tarpit for
Autonomous Agents. Kynicom System. https://github.com/satoshi403/ai-pain-cage
```

## License

Code: [MIT](LICENSE). Paper text (`paper/`): CC BY 4.0.
