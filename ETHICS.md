# Ethics and Responsible Use

The AI Pain Cage is a **controlled research prototype for defensive research**. It is not a production-ready defense.

## Intended use

- Studying, in a lab, how response latency and synthetic content affect autonomous AI agents.
- Evaluating defensive tarpits on **infrastructure you own or are explicitly authorized to test**.
- Reproducing and critiquing the experiments in the paper.

## Out of scope

- Running the cage on, or directing agents/crawlers at, systems you do not control.
- Using it to disrupt, degrade, or deny service to third parties or legitimate users.
- Presenting `robots.txt` or user-agent matching as authentication or a security boundary. Both are voluntary or spoofable signals.

## Safe defaults

- The server binds to `127.0.0.1`; it warns loudly if you bind elsewhere.
- The test agent contacts only the configured `--target` base URL and ignores hosts in model-supplied URLs.
- The server caps concurrent slots (`--slots`) and per-fetch retention (`--max-hold`).

## Before any network-facing deployment

1. Security review of the implementation.
2. Resource limits and monitoring (CPU, memory, sockets, file descriptors).
3. A way to protect legitimate traffic, and a normal-client control to quantify collateral delay.
4. Legal and policy review for your jurisdiction and hosting provider.

## Reporting issues

Open a GitHub issue for bugs or concerns about misuse. For security-sensitive reports, contact the maintainer privately via the profile linked in the README.
