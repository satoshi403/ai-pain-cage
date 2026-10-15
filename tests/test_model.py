import http.client
import json
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pain_model as pm  # noqa: E402
import jaula_dolor as jd  # noqa: E402


class TestModel(unittest.TestCase):
    def test_rates(self):
        self.assertEqual(pm.delivery_rate(16, 1.0), 16)
        self.assertEqual(pm.delivery_rate(128, 0.1), 1280)

    def test_paper_scenarios(self):
        S, n, m, t = 3760, 3, 6, 82.2
        cases = {"A": (128, 0.1, 60, 9.0, 502.2),
                 "B": (16, 1.0, 60, 180.0, 673.2),
                 "C": (16, 1.0, 300, 705.0, 1198.2)}
        for name, (c, d, B, cage, total) in cases.items():
            tf = pm.fetch_time(S, c, d, B, 300)
            tc = pm.cage_time([tf] * n)
            self.assertAlmostEqual(tc, cage, places=6, msg=name)
            self.assertAlmostEqual(pm.total_time(tc, m, t), total, places=6, msg=name)

    def test_eta_run3(self):
        self.assertAlmostEqual(pm.eta(8.9, 502.3), 0.0177, places=3)

    def test_bytes_never_exceed_page(self):
        self.assertLessEqual(pm.bytes_delivered(3760, 128, 0.1, 3.0), 3760)

    def test_erlang_b(self):
        self.assertAlmostEqual(pm.erlang_b(1.0, 1), 0.5)
        self.assertAlmostEqual(pm.erlang_b(0.0, 10), 0.0)
        self.assertGreater(pm.erlang_b(47, 50), pm.erlang_b(40, 50))
        self.assertAlmostEqual(pm.offered_load(12, 235), 47.0)


class TestPages(unittest.TestCase):
    def setUp(self):
        jd.CFG.clear()
        jd.CFG.update(sal="test-salt")

    def test_deterministic_per_path(self):
        self.assertEqual(jd.generar_pagina("/jaula/inicio"), jd.generar_pagina("/jaula/inicio"))
        self.assertNotEqual(jd.generar_pagina("/jaula/a"), jd.generar_pagina("/jaula/b"))

    def test_structure(self):
        page = jd.generar_pagina("/jaula/inicio")
        self.assertTrue(4 <= page.count("<p>") <= 8)
        self.assertTrue(8 <= page.count("<li>") <= 16)

    def test_start_page_size_matches_run2(self):
        # Run 2 in the paper received 3,936 bytes from /jaula/inicio.
        self.assertEqual(len(jd.generar_pagina("/jaula/inicio").encode()), 3936)

    def test_canary_is_salted(self):
        page = jd.generar_pagina("/jaula/x")
        m = re.search(r"<!-- id:([0-9a-f]{16}) -->", page)
        self.assertIsNotNone(m)
        self.assertIn(m.group(1), page.split("<h1>")[1])
        jd.CFG["sal"] = "another-salt"
        self.assertNotIn(m.group(1), jd.generar_pagina("/jaula/x"))

    def test_ai_user_agent_pattern(self):
        self.assertTrue(jd.AI_UA.search("python-requests/test-agent"))
        self.assertTrue(jd.AI_UA.search("Mozilla/5.0 (compatible; GPTBot/1.0)"))
        self.assertFalse(jd.AI_UA.search("Mozilla/5.0 (X11; Linux x86_64) Firefox/120.0"))


class TestServer(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
        tmp.close()
        self.logpath = tmp.name
        self.addCleanup(os.unlink, self.logpath)
        jd.CFG.clear()
        jd.CFG.update(delay=0.001, chunk=64, max_seg=10, log=self.logpath, sal="test-salt")
        jd.SLOTS = threading.Semaphore(2)
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), jd.Handler)
        self.srv.daemon_threads = True
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self._stop)
        self.port = self.srv.server_address[1]

    def _stop(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.thread.join(timeout=3)

    def _get(self, path, ua="Mozilla/5.0"):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        c.request("GET", path, headers={"User-Agent": ua})
        r = c.getresponse()
        body = r.read()
        status, headers = r.status, dict(r.getheaders())
        c.close()
        return status, headers, body

    def _log_entries(self, n=1, timeout=3.0):
        end, entries = time.time() + timeout, []
        while time.time() < end:
            try:
                with open(self.logpath, encoding="utf-8") as f:
                    entries = [json.loads(line) for line in f if line.strip()]
            except ValueError:
                entries = []
            if len(entries) >= n:
                break
            time.sleep(0.02)
        return entries

    def test_robots_disallows_maze(self):
        status, _, body = self._get("/robots.txt")
        self.assertEqual(status, 200)
        self.assertIn(b"Disallow: /jaula/", body)

    def test_browser_gets_decoy_root_with_hidden_link(self):
        status, _, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b'href="/jaula/inicio"', body)
        self.assertNotIn(b"Referencia interna", body)

    def test_maze_is_streamed_complete_and_logged(self):
        status, headers, body = self._get("/jaula/inicio")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Transfer-Encoding"), "chunked")
        self.assertEqual(body, jd.generar_pagina("/jaula/inicio").encode())
        entry = self._log_entries()[0]
        self.assertEqual(entry["ruta"], "/jaula/inicio")
        self.assertEqual(entry["bytes"], len(body))

    def test_ai_user_agent_is_routed_to_maze_from_any_path(self):
        _, _, body = self._get("/", ua="python-requests/2.31")
        self.assertEqual(body, jd.generar_pagina("/jaula/inicio").encode())

    def test_503_when_no_slots(self):
        jd.SLOTS = threading.Semaphore(0)
        status, _, _ = self._get("/jaula/inicio")
        self.assertEqual(status, 503)

    def test_max_seg_cuts_the_stream(self):
        jd.CFG.update(delay=0.05, max_seg=0.1)
        _, _, body = self._get("/jaula/inicio")
        self.assertLess(len(body), len(jd.generar_pagina("/jaula/inicio").encode()))


if __name__ == "__main__":
    unittest.main()
