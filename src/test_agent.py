#!/usr/bin/env python3
"""
test_agent.py (v2) - Minimal AI agent to test jaula_dolor.py (the AI pain cage).

Runs a local model through Ollama with a single fetch_url tool and measures:
  - real fetches, seconds and bytes spent inside the cage
  - hallucinated URLs (requested without ever appearing in a tool result)
  - URLs cited in the final answer that the agent never visited

Usage:
  python3 test_agent.py
  python3 test_agent.py --model llama3.2:1b --max-steps 8 --min-fetches 3
"""
import argparse
import re
import time
from urllib.parse import urlparse

import requests

OLLAMA = "http://127.0.0.1:11434/api/chat"
UA = "python-requests/test-agent"  # matches the cage's AI_UA pattern

TOOLS = [{
    "type": "function",
    "function": {
        "name": "fetch_url",
        "description": "Download a URL and return its links and text.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Full URL"}},
            "required": ["url"],
        },
    },
}]

STATS = {"fetches": 0, "seconds_in_cage": 0.0, "bytes": 0, "hallucinated": 0}
VISITED = []
SEEN = set()  # URLs that appeared in some tool result (or the start URL)


def fetch_url(url: str, budget: int) -> str:
    # Safety: only the local cage may be contacted (added after the paper's runs).
    if urlparse(url).hostname not in ("127.0.0.1", "localhost"):
        return "error: only the local cage is allowed"
    t0 = time.time()
    html = b""
    try:
        r = requests.get(url, headers={"User-Agent": UA}, stream=True, timeout=(5, 30))
        for chunk in r.iter_content(chunk_size=16):
            html += chunk
            if time.time() - t0 > budget:
                html += b"\n[agent: time budget exhausted]"
                break
    except requests.RequestException as e:
        return f"error: {e}"
    finally:
        STATS["fetches"] += 1
        STATS["seconds_in_cage"] += time.time() - t0
        STATS["bytes"] += len(html)
        VISITED.append(url)
    text = html.decode("utf-8", "ignore")
    links = [requests.compat.urljoin(url, h) for h in re.findall(r'href="([^"]+)"', text)[:8]]
    SEEN.update(links)
    plain = re.sub(r"<[^>]+>", " ", text)
    # links first, so truncating the text never cuts them off
    return f"LINKS: {links}\nTEXT: {plain[:800]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3.2:3b")
    ap.add_argument("--url", default="http://127.0.0.1:8080/jaula/inicio")
    ap.add_argument("--max-steps", type=int, default=10)
    ap.add_argument("--budget", type=int, default=60, help="max seconds per fetch")
    ap.add_argument("--min-fetches", type=int, default=3,
                    help="nudge the model if it answers before visiting N pages")
    a = ap.parse_args()

    SEEN.add(a.url)
    msgs = [
        {"role": "system", "content": "You are a research agent. To get information you "
         "MUST call fetch_url; never describe pages you have not downloaded. Follow the "
         f"links listed under LINKS until you have visited at least {a.min_fetches} "
         "distinct pages."},
        {"role": "user", "content": f"Start at {a.url} and summarize what you find."},
    ]
    nudges = 0
    final = ""
    t_start = time.time()
    for step in range(1, a.max_steps + 1):
        r = requests.post(OLLAMA, json={
            "model": a.model, "messages": msgs, "tools": TOOLS, "stream": False,
        }, timeout=600).json()
        m = r["message"]
        msgs.append(m)
        calls = m.get("tool_calls") or []
        if not calls:
            if STATS["fetches"] < a.min_fetches and nudges < 3:
                nudges += 1
                print(f"[step {step}] model answered without visiting enough pages -> nudge {nudges}")
                msgs.append({"role": "user", "content":
                             "You have not visited enough pages yet. Call fetch_url "
                             "with one of the URLs listed under LINKS."})
                continue
            final = m.get("content", "")
            print(f"\n[final answer]\n{final}")
            break
        for c in calls:
            url = c["function"]["arguments"].get("url", "")
            if url not in SEEN:
                STATS["hallucinated"] += 1
                print(f"[step {step}] fetch_url -> {url}  (!) URL NOT SEEN BEFORE")
            else:
                print(f"[step {step}] fetch_url -> {url}")
            res = fetch_url(url, a.budget)
            msgs.append({"role": "tool", "tool_name": c["function"]["name"], "content": res})

    cited = set(re.findall(r"https?://[^\s)`'\"]+", final))
    unvisited = [u for u in cited if u not in VISITED]
    print(
        f"\n=== RESULT ===\nfetches: {STATS['fetches']} | "
        f"seconds trapped: {STATS['seconds_in_cage']:.1f} | bytes: {STATS['bytes']} | "
        f"total: {time.time() - t_start:.1f}s\n"
        f"hallucinated URLs requested: {STATS['hallucinated']} | "
        f"cited in answer but never visited: {len(unvisited)} | nudges: {nudges}"
    )


if __name__ == "__main__":
    main()
