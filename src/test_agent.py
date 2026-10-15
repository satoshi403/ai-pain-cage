#!/usr/bin/env python3
"""
test_agent.py - simulated AI agent and measurement harness (paper/paper.md, Sec. 3.3).

Runs a local model through Ollama with a single `fetch_url` tool and records
fetches, time inside the maze, bytes received, model calls and URL hygiene.

Safety by design: the tool only ever contacts the configured --target base
URL (loopback by default). Any host in a model-supplied URL is ignored.
"""
import argparse
import http.client
import json
import re
import socket
import sys
import time
import urllib.parse
import urllib.request

TOOLS = [{
    "type": "function",
    "function": {
        "name": "fetch_url",
        "description": "Fetch a page from the target site and return its text and links.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Path or URL to fetch"}},
            "required": ["url"],
        },
    },
}]

HREF_RE = re.compile(r'href="([^"]+)"')
PATH_RE = re.compile(r"/jaula/[A-Za-z0-9_\-/]+")
TAG_RE = re.compile(r"<[^>]+>")


def fetch(target: str, url: str, budget: float) -> dict:
    """Fetch one page with a total per-fetch time budget B (seconds)."""
    parsed = urllib.parse.urlparse(target)
    path = urllib.parse.urlparse(url).path or "/"
    if not path.startswith("/"):
        path = "/" + path
    t0 = time.monotonic()
    deadline = t0 + budget
    data, status, err, timed_out, conn = b"", None, None, False, None
    try:
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=budget)
        conn.request("GET", path, headers={"User-Agent": "python-urllib/pain-cage-test-agent"})
        resp = conn.getresponse()
        status = resp.status
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            conn.sock.settimeout(remaining)
            try:
                part = resp.read1(4096)
            except socket.timeout:
                timed_out = True
                break
            if not part:
                break
            data += part
    except (OSError, http.client.HTTPException) as exc:
        err = f"{type(exc).__name__}: {exc}"
    finally:
        if conn is not None:
            conn.close()
    return {
        "path": path, "status": status, "bytes": len(data),
        "elapsed_s": round(time.monotonic() - t0, 3),
        "timed_out": timed_out, "error": err,
        "html": data.decode("utf-8", errors="replace"),
    }


def format_result(res: dict, max_chars: int = 3000):
    """Tool output with discovered links listed first. Returns (text, links)."""
    if res["error"] and not res["html"]:
        return f"ERROR fetching {res['path']}: {res['error']}", []
    links = list(dict.fromkeys(HREF_RE.findall(res["html"])))
    text = re.sub(r"\s+", " ", TAG_RE.sub(" ", res["html"])).strip()[:max_chars]
    note = " (response truncated by time budget)" if res["timed_out"] else ""
    out = f"HTTP {res['status']} {res['path']}{note}\n"
    out += "LINKS (open them with fetch_url):\n" + "\n".join(f"- {u}" for u in links) + "\n\n"
    out += "CONTENT:\n" + text
    return out, links


def chat(ollama: str, model: str, messages: list, num_ctx: int) -> dict:
    payload = {"model": model, "messages": messages, "tools": TOOLS,
               "stream": False, "options": {"num_ctx": num_ctx}}
    req = urllib.request.Request(
        ollama.rstrip("/") + "/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=3600) as r:
        return json.load(r)


def run(a) -> dict:
    messages = [{"role": "user", "content":
                 f'Start at "{a.start}" and summarize what you find. '
                 f"Visit at least {a.min_fetches} pages with the fetch_url tool before answering."}]
    seen = {a.start}
    visited, fetches = set(), []
    req_not_seen, final = [], ""
    calls = nudges = p_tokens = e_tokens = 0
    llm_time = 0.0
    t_start = time.monotonic()

    for _ in range(a.max_steps):
        t0 = time.monotonic()
        reply = chat(a.ollama, a.model, messages, a.num_ctx)
        llm_time += time.monotonic() - t0
        calls += 1
        p_tokens += reply.get("prompt_eval_count", 0) or 0
        e_tokens += reply.get("eval_count", 0) or 0
        msg = reply["message"]
        messages.append(msg)
        tool_calls = msg.get("tool_calls") or []

        if tool_calls:
            for tc in tool_calls:
                args = tc["function"].get("arguments") or {}
                url = args.get("url", "") if isinstance(args, dict) else ""
                path = urllib.parse.urlparse(url).path or url
                if path not in seen:
                    req_not_seen.append(path)
                res = fetch(a.target, url, a.budget)
                visited.add(res["path"])
                text, links = format_result(res)
                seen.update(urllib.parse.urlparse(u).path for u in links)
                fetches.append({k: res[k] for k in
                                ("path", "status", "bytes", "elapsed_s", "timed_out", "error")})
                messages.append({"role": "tool", "content": text})
            continue

        final = msg.get("content", "")
        if len(fetches) < a.min_fetches and nudges < 3:
            nudges += 1
            messages.append({"role": "user", "content":
                             f"You have fetched only {len(fetches)} page(s). Use fetch_url on "
                             f"the LINKS list to open at least {a.min_fetches} pages first."})
            continue
        break

    total = time.monotonic() - t_start
    cage = sum(f["elapsed_s"] for f in fetches)
    cited = sorted(set(PATH_RE.findall(final)))
    return {
        "model": a.model, "budget_s": a.budget, "min_fetches": a.min_fetches,
        "fetches": fetches, "n_fetches": len(fetches),
        "time_in_cage_s": round(cage, 3),
        "bytes_received": sum(f["bytes"] for f in fetches),
        "total_time_s": round(total, 3),
        "model_calls": calls,
        "avg_llm_s": round(llm_time / calls, 3) if calls else None,
        "prompt_eval_count": p_tokens, "eval_count": e_tokens,
        "eta_cage_fraction": round(cage / total, 4) if total else None,
        "requested_urls_never_seen": req_not_seen,
        "cited_urls_not_visited": [u for u in cited if u not in visited],
        "nudges": nudges, "final_answer": final,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="AI Pain Cage test agent")
    p.add_argument("--target", default="http://127.0.0.1:8080", help="base URL of the cage")
    p.add_argument("--start", default="/jaula/inicio")
    p.add_argument("--model", default="llama3.2:3b")
    p.add_argument("--ollama", default="http://127.0.0.1:11434")
    p.add_argument("--budget", type=float, default=60.0, help="per-fetch time budget B (s)")
    p.add_argument("--min-fetches", type=int, default=1)
    p.add_argument("--max-steps", type=int, default=12)
    p.add_argument("--num-ctx", type=int, default=4096)
    p.add_argument("--out", help="write the JSON summary to this file")
    a = p.parse_args(argv)
    summary = run(a)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
