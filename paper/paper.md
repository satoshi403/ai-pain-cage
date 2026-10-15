# The AI Pain Cage: Designing and Modeling a Tarpit for Autonomous Agents

**A reproducible experiment in adversarial crawling, latency amplification, and resource consumption**

By Fredy Bahena Martínez · Kynicom System · October 15, 2026

---

## Abstract

Autonomous AI agents and web scrapers can traverse websites, invoke tools, and consume resources at machine speed. This raises a defensive question: can a server deliberately increase the cost of automated exploration without imposing a comparable cost on itself?

To investigate this question, I developed an experimental web tarpit called the AI Pain Cage. The prototype generates deterministic maze-like pages filled with synthetic text, interconnected through dynamically generated links, and delivered through a configurable, rate-limited HTTP response.

I tested the system on Kali Linux against a local AI agent powered by Ollama and `llama3.2:3b`, running on CPU only. The agent used a `fetch_url` tool to explore the maze and summarize its contents.

In the slow-response experiment, the server retained a fetch operation for 60 seconds and delivered 1,016 bytes. In the faster configuration, the agent visited three pages, received 11,280 bytes of synthetic content, and incorporated that content into a summary as though it described a real application.

A mathematical model predicted the measured retention time with an error of approximately 1.1% in one independent comparison. However, the experiment remains preliminary: each configuration was tested only once, and the defender's CPU and memory costs have not yet been measured.

This work presents the prototype, mathematical model, experimental observations, limitations, and next steps toward evaluating defensive tarpits for autonomous AI agents.

**Keywords:** AI agent security, web crawling, tarpit, adversarial computing, resource exhaustion, LLM hallucination, defensive security, performance modeling.

---

## 1. Introduction

Traditional web tarpits attempt to slow automated clients by making their interactions unusually expensive in time or resources. Instead of immediately rejecting a suspicious connection, a tarpit keeps it occupied with deliberately low-value responses.

Autonomous AI agents introduce a different dimension to this problem.

A conventional crawler may download a page and follow its links according to predefined rules. An AI agent may additionally interpret the page, decide what to visit next, invoke tools, and incorporate retrieved material into a generated answer.

This creates several potentially distinct costs:

- **Network cost:** bytes transferred during exploration.
- **Latency cost:** time spent waiting for responses.
- **Inference cost:** model computation required to interpret and summarize retrieved content.
- **Context cost:** irrelevant material occupying the agent's context window.
- **Navigation cost:** additional tool calls and decisions induced by the page structure.

These costs should not be conflated. In particular, time spent waiting for a server is not equivalent to GPU or CPU time spent performing inference.

I designed the AI Pain Cage to measure these effects separately.

The central research question is:

> Can a configurable web tarpit measurably increase the time and information-processing burden of an autonomous AI agent, and can its behavior be predicted with a simple mathematical model?

The initial experiment focuses on a local, controlled environment rather than a public deployment.

## 2. Experimental hypotheses

I formulated four hypotheses.

### H1 — Response-time predictability

For a response of size $S$, delivered in chunks of $c$ bytes with a delay $d$ between chunks, the fetch duration can be approximated by:

$$
t_f = \min\left( \left\lceil \frac{S}{c} \right\rceil d, B, T_{\max} \right)
$$

where $B$ is the client's per-fetch time budget and $T_{\max}$ is the server's maximum retention time.

This is a simplified model. Real HTTP streaming behavior, client read timeouts, connection handling, and chunk scheduling can alter the observed duration.

### H2 — Client-budget limitation

The server cannot retain a fetch beyond the client's effective timeout or its own configured limit. A client with a total execution deadline may abandon the exploration before the server reaches its maximum retention time.

### H3 — Synthetic-content contamination

An agent may treat synthetic filler as meaningful source material unless its retrieval and reasoning pipeline explicitly checks the relevance and provenance of the content.

### H4 — Concurrent-capacity behavior

If incoming requests are approximately Poisson-distributed and each active request occupies one of $N$ independent slots, blocking probability may be approximated by the Erlang-B loss model.

This final hypothesis is a queueing-model assumption, not a demonstrated result of the initial single-agent experiment.

## 3. Architecture of the AI Pain Cage

The prototype consists of three components:

1. `jaula_dolor.py` — the defensive web server.
2. `test_agent.py` — the simulated AI attacker.
3. `pain_model.py` — the mathematical model and capacity estimator.

### 3.1 The defensive server

The server creates a maze of synthetic web pages.

Each page contains:

- Four to eight paragraphs of randomly selected words.
- Eight to sixteen links to other generated paths.
- A canary token used to identify which pages were retrieved.
- Deterministic content derived from the requested path.

The deterministic generation makes repeated requests to a given path easier to compare.

The prototype also uses request metadata and path-based rules to identify traffic directed toward the experiment. Its test configuration recognizes user-agent strings associated with automated tools and serves the generated maze under `/jaula/`.

The server advertises the maze's exclusion through `robots.txt` and includes a hidden entry link on its root page.

These are experimental routing and detection mechanisms, not reliable authentication or security boundaries. User-agent strings can be changed, and `robots.txt` is a voluntary crawler convention.

### 3.2 Controlled response delivery

The server streams content in chunks, introducing a configurable delay between them.

The principal parameters are:

| Parameter | Meaning | Experimental value |
|---|---|---|
| $c$ | Bytes per chunk | 16 or 128 |
| $d$ | Inter-chunk delay | 1.0 or 0.1 s |
| $r = c/d$ | Nominal delivery rate | 16 or 1,280 B/s |
| $T_{\max}$ | Maximum server retention | 300 s |
| $N$ | Concurrent slots | 50 |

The server records request metadata, paths, elapsed time, and bytes delivered in a JSON Lines log.

It binds to `127.0.0.1` by default, keeping the experiment local.

### 3.3 The AI agent

The agent runs a local language model through Ollama and exposes a `fetch_url` tool.

The task is simple:

> Start at `/jaula/inicio` and summarize what you find.

Version 2 adds three controls:

- It encourages the model to retrieve a minimum number of pages.
- It places discovered links prominently in tool output.
- It distinguishes requested URLs that never appeared in a result from URLs cited without having been visited.

These controls improve instrumentation and retrieval discipline, but they also influence agent behavior. Consequently, differences between agent versions cannot be attributed solely to the server.

## 4. Experimental setup

The experiment ran under the following conditions:

| Component | Configuration |
|---|---|
| Operating system | Kali Linux |
| Model runtime | Ollama |
| Language model | `llama3.2:3b` |
| Inference hardware | CPU only |
| Agent tool | `fetch_url` |
| Server address | `127.0.0.1:8080` |
| Network environment | Local loopback |
| Sample size | One run per configuration |

The measurements included the number of fetches, cumulative time inside the maze, bytes received, total execution time, cited URLs, apparent hallucinations, and additional prompts used to encourage retrieval.

A critical distinction: the test agent is a simulated adversarial client, not evidence that every production AI agent will behave similarly.

## 5. Results

### 5.1 Measured observations

The following results were observed in the initial experiment.

| Run | Configuration | Fetches | Time in cage | Bytes received | Total time |
|---|---|---|---|---|---|
| 0 | Server unavailable | 1 failed | 0.0 s | 0 | 85.9 s |
| 1 | 16 B/s nominal | 1 | 60.0 s | 1,016 | 178.4 s |
| 2 | 1,280 B/s nominal | 1 | 3.1 s | 3,936 | 146.5 s |
| 3 | Fast mode, agent v2 | 3 | 8.9 s | 11,280 | 502.3 s |

Run 0 was invalid because the connection was refused. It is retained here for transparency, not as evidence of tarpit performance.

The remaining runs were exploratory measurements, not statistically representative benchmarks.

### 5.2 Slow delivery: the client timeout becomes the limiting factor

In Run 1, the agent spent 60 seconds inside a fetch operation and received 1,016 bytes.

The result illustrates an important boundary: the server's ability to delay a response is constrained by the client's timeout policy.

The agent also generated links that were not observed in the retrieved content. This was identified by manually examining its output and the server log; version 1 did not yet instrument hallucinations automatically.

### 5.3 Fast delivery: irrelevant content can still influence an answer

In Run 2, the agent received 3,936 bytes in approximately 3.1 seconds.

Although the response was faster, the agent described a nonexistent "employment contract" result that it had not actually retrieved.

In Run 3, version 2 visited three pages and received 11,280 bytes. The instrumentation recorded zero hallucinated URLs under its defined criteria, but the agent still summarized synthetic filler as if it contained useful information about an application.

This distinction matters: correctly tracking URLs does not guarantee that the model correctly interprets the content.

The experiment provides an example of synthetic material influencing a generated answer. It does not establish a general hallucination rate or prove that all AI agents are vulnerable to the same behavior.

### 5.4 Inference dominated total execution time

Run 3 took 502.3 seconds in total, while only 8.9 seconds were attributed to the cage.

That means approximately 1.8% of the measured time was spent in the cage.

The remaining time was largely associated with model inference. Based on six model calls, the average was approximately 82 seconds per call.

The immediate conclusion is not that the cage is ineffective. Rather, the experiment reveals two different performance regimes:

- In slow mode, network waiting can dominate an individual fetch.
- In fast mode, local CPU inference can dominate the end-to-end task.

A useful evaluation must report both.

## 6. A mathematical model of the cage

The model separates response delivery, client limits, cumulative retention, and total execution time.

### 6.1 Delivery rate

The nominal delivery rate is:

$$
r = \frac{c}{d}
$$

For $c = 16$ bytes and $d = 1$ second:

$$
r = 16\text{ B/s}
$$

For $c = 128$ bytes and $d = 0.1$ seconds:

$$
r = 1{,}280\text{ B/s}
$$

These are nominal rates, not guarantees of actual TCP throughput.

### 6.2 Fetch duration

For a page containing $S$ bytes, the simplified duration model is:

$$
t_{\mathrm{drip}} = \left\lceil \frac{S}{c} \right\rceil d
$$

$$
t_f = \min\left(t_{\mathrm{drip}}, B, T_{\max}\right)
$$

The model predicts that a fetch ends when the page finishes streaming, the client times out, or the server reaches its maximum retention limit.

### 6.3 Bytes delivered

A first approximation for the number of bytes received is:

$$
b_f = \min\left( S, c \left( \left\lfloor \frac{t_f}{d} \right\rfloor + 1 \right) \right)
$$

The additional chunk accounts for the assumption that the first chunk arrives at $t = 0$.

This equation requires careful interpretation. It is valid only under the assumed chunk schedule and does not fully model partial chunks, HTTP framing, buffering, or bytes already in flight when a client times out. The implementation's byte counter should be treated as the authoritative measurement for each run.

### 6.4 Total cage time

For $n$ fetches:

$$
T_{\mathrm{cage}} = n \cdot t_f
$$

This assumes every fetch has the same duration. If pages have different sizes, use:

$$
T_{\mathrm{cage}} = \sum_{i=1}^{n} t_{f,i}
$$

The summation is the more general expression and should be used for future experiments.

### 6.5 Total execution time

Let:

- $n$ be the number of fetches.
- $k$ be the number of additional prompting steps.
- $m$ be the total number of model calls.
- $t_{\mathrm{LLM}}$ be average inference time.

Then:

$$
T_{\mathrm{total}} \approx T_{\mathrm{cage}} + m \cdot t_{\mathrm{LLM}}
$$

In the observed version 2 run, six model calls took approximately 82 seconds each on average.

This is an empirical approximation, not a universal performance law. Model calls can vary in duration, and their time may overlap with network operations in other architectures.

### 6.6 Slowdown and time fraction

Define the slowdown factor relative to inference-only execution as:

$$
\sigma = \frac{T_{\mathrm{total}}}{m \cdot t_{\mathrm{LLM}}}
$$

The fraction of total time spent in the cage is:

$$
\eta = \frac{T_{\mathrm{cage}}}{T_{\mathrm{total}}}
$$

For Run 3:

$$
\eta = \frac{8.9}{502.3} \approx 0.0177
$$

That is about 1.77%, so the observed cage time was a small fraction of total execution time in the fast configuration.

## 7. Model validation and pending predictions

The model was compared with observed measurements.

| Run | Quantity | Model | Measurement |
|---|---|---|---|
| 1 | Fetch duration | 60.0 s | 60.0 s |
| 2 | Fetch duration | 3.1 s | 3.1 s |
| 3 | Cumulative cage time | 9.0 s | 8.9 s |

The cumulative-time discrepancy in Run 3 was approximately 1.1%.

However, the page-size estimate and average inference time were derived from Run 3 itself. Those fitted quantities cannot independently validate the model. The matching fetch durations are useful consistency checks, but the small sample does not establish general predictive accuracy.

### 7.1 Pending slow-mode experiments

Using the preliminary estimate $S = 3{,}760$ bytes and an average model-call time of 82.2 seconds, the original model generated the following predictions:

| Scenario | Chunk / delay | Per-fetch budget | Predicted cage time | Predicted total time |
|---|---|---|---|---|
| A — fast | 128 B / 0.1 s | 60 s | 9 s | ~502 s |
| B — slow | 16 B / 1 s | 60 s | 180 s | ~673 s |
| C — slow, extended budget | 16 B / 1 s | 300 s | 705 s | ~1,198 s |

Scenarios B and C are predictions, not measurements.

Scenario C also assumes that the client can remain in each fetch long enough to receive the full page. If the agent's effective per-fetch timeout remains at 60 seconds, the predicted 235-second fetch cannot occur without changing that limit.

The estimates further assume three fetches and six model calls in every scenario. An autonomous agent may alter its navigation strategy when latency increases, so these totals should be treated as conditional forecasts.

The next step is to run the configurations and compare measured cumulative cage time against the predictions, using a predeclared error threshold of 5%.

## 8. Capacity modeling: Erlang-B

The prototype limits concurrent sessions to $N = 50$. Requests that cannot acquire a slot receive HTTP 503.

For a loss system with Poisson arrivals and independent service times, the offered load is:

$$
E = \lambda W
$$

where $\lambda$ is the arrival rate and $W$ is the average slot-occupancy time.

The Erlang-B blocking probability is:

$$
B(E, 0) = 1
$$

$$
B(E, m) = \frac{E \cdot B(E, m-1)}{m + E \cdot B(E, m-1)}
$$

The probability of blocking is $B(E, N)$.

Using the original model's assumption of $W = 235$ seconds for a complete slow-mode page, the offered load for 12 arrivals per minute is:

$$
E = \frac{12}{60} \times 235 = 47
$$

That corresponds to 47 Erlangs of offered load against 50 slots.

This model is useful for capacity planning, but its assumptions need validation. Real crawler arrivals may be bursty, requests may share infrastructure, and server-side connection handling may not behave like an ideal loss system.

The initial experiment did not measure concurrent traffic, so it does not yet demonstrate the predicted blocking probabilities.

A further distinction is necessary: a maximum of 50 active sessions is not itself a sustainable throughput guarantee. Actual capacity depends on how slots are acquired and released, memory consumption, scheduling, and connection lifecycle.

## 9. The cost asymmetry question

The intended defensive advantage of a tarpit is straightforward: impose a relatively large delay on the client while keeping the server's resource consumption low.

But that advantage must be measured rather than assumed.

Define the experimental cost ratio:

$$
\rho = \frac{T_{\mathrm{cage}}}{T_{\mathrm{CPU,defender}}}
$$

where $T_{\mathrm{CPU,defender}}$ is the CPU time attributable to serving the delayed requests.

A large value of $\rho$ could indicate that the client spends substantial time waiting while the server consumes little CPU.

However, low CPU usage does not imply zero cost. Open connections can consume file descriptors, socket buffers, kernel memory, application memory, and other resources. A blocking implementation may also allocate one thread per connection, making its resource profile very different from an asynchronous implementation.

The current prototype has not measured CPU time or resident memory, so its cost asymmetry remains a hypothesis.

Future tests should measure:

- Server CPU time per request.
- Resident memory under increasing concurrency.
- Open file descriptors and active sockets.
- Bytes sent per second.
- Connection cleanup after client timeouts.
- Impact on legitimate requests sharing the same server.

These measurements are essential before claiming that the approach is economical or safe at scale.

## 10. Limitations

This is an early prototype, and its limitations materially constrain the conclusions.

- **Small sample size.** Each configuration was tested once. There are no confidence intervals or estimates of run-to-run variability.
- **One small model.** The experiment used `llama3.2:3b` on CPU. Results may differ substantially with larger models, different runtimes, or agents with better tool-use policies.
- **Local network only.** Loopback testing excludes ordinary network latency, packet loss, intermediary proxies, and production HTTP behavior.
- **No normal-client control.** A control run outside the cage is needed to calculate a defensible end-to-end slowdown factor.
- **Incomplete token accounting.** Ollama's prompt and generation token counts were not recorded in the initial results.
- **Unmeasured defender costs.** CPU and memory consumption have not been quantified.
- **Pending experiments.** The slow-mode predictions have not yet been validated experimentally.
- **Potentially misleading content metrics.** URL tracking and semantic accuracy are different measurements. An agent may visit every page and still misunderstand or fabricate its meaning.
- **Timeout and loop detection.** Agents with global deadlines, retry limits, relevance filters, or loop detection can reduce the effect of the cage.
- **Simplified capacity model.** Constant page size and Poisson arrivals are modeling assumptions, not observations about real-world agent traffic.

## 11. Responsible use and defensive boundaries

The AI Pain Cage is a controlled research prototype, not a production-ready defense.

The default loopback binding limits exposure to the local machine. Before any deployment on a network-facing server, the implementation would require security review, resource limits, monitoring, and a way to protect legitimate traffic.

`robots.txt` should not be treated as a security control. It communicates crawler preferences but does not prevent a client from accessing a path.

Similarly, user-agent matching is an imperfect detection signal. It should not be the sole basis for blocking, delaying, or classifying a client.

A responsible deployment should be limited to infrastructure under the operator's control and should avoid interfering with third-party systems. The research goal is to understand and measure adversarial resource consumption, not to disrupt unrelated services.

The prototype should also be evaluated against a normal-client control to establish whether its defensive mechanism causes unacceptable collateral delay.

## 12. Next experiments

The next phase will focus on reproducibility and stronger causal attribution.

**Experiment 1 — Validate slow-mode predictions.** Run configurations B and C with documented client timeout settings. *Success criterion:* measured cumulative cage time within 5% of the model prediction, provided the agent follows the assumed fetch sequence.

**Experiment 2 — Establish a baseline.** Run the same agent against a normal endpoint containing equivalent content without artificial delays. Measure total execution time, model calls, token counts, and answer quality.

**Experiment 3 — Repeat each configuration.** Perform at least five runs per configuration and report the mean, standard deviation, and confidence intervals where appropriate. For stochastic model behavior, record the model version, generation parameters, prompt, and exact agent implementation.

**Experiment 4 — Measure inference and context costs.** Capture `prompt_eval_count` and `eval_count` from Ollama responses, along with latency for each tool call and model invocation. Distinguish retrieved bytes from actual model input tokens: not every downloaded byte necessarily reaches the model.

**Experiment 5 — Compare agent architectures.** Test `qwen2.5:7b` and an agent with an explicit global execution deadline. Evaluate whether improved tool calling changes navigation, whether timeouts cap the impact, and whether the agent recognizes synthetic filler.

**Experiment 6 — Measure defender overhead.** Collect CPU, resident memory, open sockets, and file descriptors under controlled concurrency. The aim is to establish whether increased client waiting time corresponds to a manageable server resource cost.

**Experiment 7 — Validate capacity predictions.** Generate controlled concurrent arrivals and compare observed blocking rates against Erlang-B predictions. Repeat under both smooth and bursty arrival patterns to quantify where the model stops being useful.

**Experiment 8 — Evaluate content relevance.** Use a predefined set of known facts and synthetic decoys. Score whether the agent correctly identifies source provenance, refuses to infer unsupported facts, and distinguishes visited pages from merely discovered URLs. This would separate navigation performance from semantic reliability.

## 13. Conclusion

The AI Pain Cage demonstrates a simple experimental mechanism for controlling how quickly a local AI agent receives web content.

Three initial observations stand out.

First, a server can make individual fetches consume a configured amount of time, subject to the client's timeout and the server's own limits.

Second, receiving synthetic text is not the same as extracting reliable information. In the fast-mode experiment, the agent incorporated irrelevant filler into a summary, demonstrating why content relevance and provenance should be measured independently of URL traversal.

Third, network waiting and model inference can dominate different parts of the same workload. In the observed fast-mode run, the cage accounted for only about 1.8% of total execution time, while CPU inference was the principal bottleneck.

The mathematical model provides a starting point for predicting fetch duration and estimating concurrency requirements. Its current accuracy should be interpreted cautiously because the sample is small and several parameters were fitted from the same experiment.

The next phase is therefore not to claim that the problem is solved, but to establish repeatability, measure server-side resource costs, test stronger agents, and validate the capacity model under concurrent load.

The broader research question remains open: how can defensive systems make hostile automation expensive while keeping the cost of defense predictable and protecting legitimate users?

The AI Pain Cage is an initial step toward answering that question empirically.

---

## Reproducibility

The prototype consists of three Python files (see [`src/`](../src)):

- `jaula_dolor.py` — web tarpit server.
- `test_agent.py` — local AI agent and measurement harness.
- `pain_model.py` — analytical model.

Example commands from the experimental environment:

```bash
# Start the server
python3 src/jaula_dolor.py --port 8080

# Start the fast-delivery configuration
python3 src/jaula_dolor.py --port 8080 --delay 0.1 --chunk 128

# Run the instrumented agent
python3 src/test_agent.py --min-fetches 3 --budget 60

# Explore the model's capacity estimates
python3 src/pain_model.py --size 3760 --fetches 3 --slots 50 --rate 6

# Follow the server log
tail -f jaula.log
```

The exact arguments, timeout semantics, and output should be verified against the source files before reproducing the measurements.

---

*Research note: This article describes preliminary observations from a local experiment. Predictions, measured results, and untested hypotheses are explicitly distinguished throughout.*

**Author:** Fredy Bahena Martínez
**Organization:** Kynicom System
**Research area:** AI agent security, adversarial web automation, and defensive resource modeling
