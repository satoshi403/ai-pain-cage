#!/usr/bin/env python3
"""
jaula_dolor.py - "Pain cage" prototype for AI agents / scrapers.

Original experiment source. Identifiers, log keys and CLI flags are in Spanish
and are kept as-is for reproducibility; comments and help texts are translated.

It is a tarpit: it traps automated clients that ignore robots.txt and makes
them pay "pain" in time and tokens:
  - Infinite maze of procedurally generated pages (deterministic per path).
  - Responses dripped in small chunks (ties up the client's connection and time).
  - Worthless filler text + canary tokens to trace leaks/usage.
  - JSONL log of every visit (IP, UA, time held).

Usage:  python3 jaula_dolor.py --port 8080
Test:   curl -N http://127.0.0.1:8080/jaula/inicio
For infrastructure you own only. Listens on 127.0.0.1 by default.
"""
import argparse
import hashlib
import json
import random
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AI_UA = re.compile(
    r"gptbot|chatgpt|claudebot|anthropic|ccbot|perplexity|bytespider|"
    r"amazonbot|cohere|python-requests|python-httpx|scrapy|playwright|headless|langchain",
    re.I,
)
PALABRAS = (
    "protocolo nodo bloque clave sistema red token oraculo contrato capa "
    "validador consenso firma estado cadena puente liquidez registro "
    "auditoria vector entrada salida memoria canal sesion interfaz"
).split()

CFG = {}
LOG_LOCK = threading.Lock()
SLOTS = None  # semaphore limiting concurrent cages


def log(evento: dict):
    evento["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    with LOG_LOCK, open(CFG["log"], "a", encoding="utf-8") as f:
        f.write(json.dumps(evento, ensure_ascii=False) + "\n")


def generar_pagina(ruta: str) -> str:
    semilla = int(hashlib.sha256(ruta.encode()).hexdigest(), 16)
    rnd = random.Random(semilla)
    canary = hashlib.sha1(f"{CFG['sal']}{ruta}".encode()).hexdigest()[:16]
    parrafos = []
    for _ in range(rnd.randint(4, 8)):
        frase = " ".join(rnd.choice(PALABRAS) for _ in range(rnd.randint(30, 70)))
        parrafos.append(f"<p>{frase.capitalize()}.</p>")
    enlaces = []
    for _ in range(rnd.randint(8, 16)):
        h = hashlib.md5(str(rnd.random()).encode()).hexdigest()[:10]
        enlaces.append(f'<li><a href="/jaula/{h}">{rnd.choice(PALABRAS)}-{h[:4]}</a></li>')
    return (
        f"<html><head><title>doc-{canary}</title></head><body>"
        f"<h1>Referencia interna {canary}</h1>"
        + "".join(parrafos)
        + f"<ul>{''.join(enlaces)}</ul>"
        + f"<!-- id:{canary} --></body></html>"
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "nginx/1.24.0"  # basic camouflage
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _normal(self, body: str, ctype="text/html"):
        data = body.encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        ua = self.headers.get("User-Agent", "")
        ip = self.client_address[0]
        ruta = self.path.split("?")[0]

        if ruta == "/robots.txt":
            return self._normal("User-agent: *\nDisallow: /jaula/\n", "text/plain")

        enjaular = ruta.startswith("/jaula/") or AI_UA.search(ua)
        if not enjaular:
            # "Normal" page with a hidden link: whoever follows it ignores robots.txt
            return self._normal(
                "<html><body><h1>Inicio</h1>"
                '<a href="/jaula/inicio" style="display:none">archivo</a>'
                "</body></html>"
            )
        self._jaula(ip, ua, ruta)

    def _jaula(self, ip, ua, ruta):
        if not SLOTS.acquire(blocking=False):
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        inicio = time.time()
        enviado = 0
        try:
            cuerpo = generar_pagina(ruta if ruta.startswith("/jaula/") else "/jaula/inicio").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            paso = CFG["chunk"]
            for i in range(0, len(cuerpo), paso):
                if time.time() - inicio > CFG["max_seg"]:
                    break
                trozo = cuerpo[i:i + paso]
                self.wfile.write(f"{len(trozo):x}\r\n".encode() + trozo + b"\r\n")
                self.wfile.flush()
                enviado += len(trozo)
                time.sleep(CFG["delay"])
            self.wfile.write(b"0\r\n\r\n")
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            SLOTS.release()
            log({
                "ip": ip, "ua": ua, "ruta": ruta,
                "segundos": round(time.time() - inicio, 2), "bytes": enviado,
            })


def main():
    global SLOTS
    p = argparse.ArgumentParser(description="AI pain cage (tarpit)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--delay", type=float, default=1.0, help="seconds between chunks")
    p.add_argument("--chunk", type=int, default=16, help="bytes per chunk")
    p.add_argument("--max-seg", type=int, default=300, help="max seconds per cage")
    p.add_argument("--max-jaulas", type=int, default=50)
    p.add_argument("--log", default="jaula.log")
    a = p.parse_args()

    CFG.update(
        delay=a.delay, chunk=a.chunk, max_seg=a.max_seg, log=a.log,
        sal=hashlib.sha1(str(time.time()).encode()).hexdigest(),
    )
    SLOTS = threading.Semaphore(a.max_jaulas)
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    srv.daemon_threads = True
    print(f"[+] Cage active at http://{a.host}:{a.port}  (log: {a.log})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[-] Stopped")


if __name__ == "__main__":
    main()
