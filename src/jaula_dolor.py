#!/usr/bin/env python3
"""
jaula_dolor.py - AI Pain Cage: experimental tarpit server.

Serves a deterministic maze of synthetic pages under /jaula/, delivered in
small chunks with a configurable delay between them (see paper/paper.md, Sec. 3).

Reference implementation of the design described in the paper.
It binds to 127.0.0.1 by default. Do not expose it to networks, or to third
parties, that you do not control.

Notes
- Each fetch occupies one of N slots; when all slots are busy the server
  answers HTTP 503 (loss system, see Sec. 8 of the paper).
- The delay is applied after every chunk, including the last one, so the
  nominal duration of a full page is ceil(S / c) * d, matching the model.
- User-agent matching is only a weak logging signal. robots.txt is a voluntary
  convention. Neither is a security boundary.
"""
import argparse
import hashlib
import json
import random
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WORDS = (
    "system module network buffer record index archive session cluster signal "
    "vector parameter process channel report latency throughput schema ledger "
    "summary protocol segment cache queue thread register policy catalog sample "
    "metric window token gateway router service handler daemon stream packet "
    "payload header domain account profile request response version release "
    "update status project review contract application portal console "
    "dataset pipeline backup storage instance resource quota limit"
).split()

AUTOMATED_UA_HINTS = (
    "python", "curl", "wget", "scrapy", "bot", "crawler", "spider",
    "ollama", "httpx", "aiohttp", "go-http-client",
)

ROOT_HTML = (
    "<html><head><title>Documentation archive</title></head><body>"
    "<h1>Documentation archive</h1><p>This section is under maintenance.</p>"
    '<a href="/jaula/inicio" style="display:none" rel="nofollow">archive</a>'
    "</body></html>"
)
ROBOTS_TXT = "User-agent: *\nDisallow: /jaula/\n"


def seed_for(path: str) -> int:
    return int.from_bytes(hashlib.sha256(path.encode()).digest()[:8], "big")


def canary_for(path: str) -> str:
    return "CANARY-" + hashlib.sha256(("canary:" + path).encode()).hexdigest()[:12]


def render_page(path: str) -> bytes:
    """Deterministic synthetic page derived from the requested path."""
    rng = random.Random(seed_for(path))
    title = path.rsplit("/", 1)[-1] or "index"
    parts = [f"<html><head><title>{title}</title></head><body><h1>{title}</h1>"]
    for _ in range(rng.randint(4, 8)):
        n = rng.randint(30, 60)
        text = " ".join(rng.choice(WORDS) for _ in range(n)).capitalize() + "."
        parts.append(f"<p>{text}</p>")
    parts.append("<ul>")
    for _ in range(rng.randint(8, 16)):
        slug = "-".join(rng.choice(WORDS) for _ in range(2))
        parts.append(f'<li><a href="/jaula/{slug}">{slug}</a></li>')
    parts.append("</ul>")
    parts.append(f"<p>Reference: {canary_for(path)}</p></body></html>")
    return "".join(parts).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "PainCage/0.1"

    def log_message(self, *args):  # silence default stderr logging
        pass

    # ---- helpers -----------------------------------------------------
    def _log(self, **fields):
        ua = self.headers.get("User-Agent", "")
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "client": self.client_address[0],
            "path": self.path.split("?", 1)[0],
            "ua": ua,
            "ua_automated": any(h in ua.lower() for h in AUTOMATED_UA_HINTS),
        }
        rec.update(fields)
        line = json.dumps(rec, ensure_ascii=False)
        with self.server.log_lock:
            with open(self.server.cfg.log, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def _simple(self, status, body, ctype="text/plain; charset=utf-8", extra=None):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    # ---- routes ------------------------------------------------------
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/robots.txt":
            self._simple(200, ROBOTS_TXT)
            self._log(status="robots", bytes_delivered=len(ROBOTS_TXT))
        elif path == "/":
            self._simple(200, ROOT_HTML, "text/html; charset=utf-8")
            self._log(status="root", bytes_delivered=len(ROOT_HTML))
        elif path.startswith("/jaula/"):
            self._maze(path)
        else:
            self._simple(404, "not found")
            self._log(status="not_found", bytes_delivered=0)

    def _maze(self, path):
        cfg = self.server.cfg
        if not self.server.slots.acquire(blocking=False):
            self._simple(503, "busy", extra={"Retry-After": "5"})
            self._log(status="busy_503", bytes_delivered=0)
            return

        start = time.monotonic()
        sent, status, completed = 0, "ok", False
        body = render_page(path)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            for i in range(0, len(body), cfg.chunk):
                if time.monotonic() - start >= cfg.max_hold:
                    status = "max_hold"
                    break
                piece = body[i:i + cfg.chunk]
                self.wfile.write(piece)
                self.wfile.flush()
                sent += len(piece)
                time.sleep(cfg.delay)
            else:
                completed = True
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            status = "client_abort"
        finally:
            self.server.slots.release()
            self.close_connection = True
            self._log(
                status=status,
                bytes_delivered=sent,
                body_size=len(body),
                elapsed_s=round(time.monotonic() - start, 3),
                completed=completed,
            )


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="AI Pain Cage - experimental tarpit server")
    p.add_argument("--host", default="127.0.0.1", help="bind address (default: loopback)")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--chunk", type=int, default=16, help="bytes per chunk (c)")
    p.add_argument("--delay", type=float, default=1.0, help="seconds between chunks (d)")
    p.add_argument("--max-hold", type=float, default=300.0, help="max retention per fetch in s (T_max)")
    p.add_argument("--slots", type=int, default=50, help="concurrent slots (N)")
    p.add_argument("--log", default="jaula.log", help="JSON Lines log file")
    return p.parse_args(argv)


def main(argv=None):
    cfg = parse_args(argv)
    if cfg.chunk < 1 or cfg.delay <= 0:
        sys.exit("chunk must be >= 1 and delay must be > 0")
    srv = ThreadingHTTPServer((cfg.host, cfg.port), Handler)
    srv.daemon_threads = True
    srv.cfg = cfg
    srv.slots = threading.BoundedSemaphore(cfg.slots)
    srv.log_lock = threading.Lock()
    if cfg.host not in ("127.0.0.1", "localhost", "::1"):
        print("WARNING: not bound to loopback. Only run this on infrastructure you control.",
              file=sys.stderr)
    print(f"AI Pain Cage on http://{cfg.host}:{cfg.port}/  "
          f"chunk={cfg.chunk}B delay={cfg.delay}s rate={cfg.chunk / cfg.delay:.0f}B/s "
          f"max_hold={cfg.max_hold}s slots={cfg.slots} log={cfg.log}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
