import os
import sys
import unittest

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
    def test_deterministic(self):
        self.assertEqual(jd.render_page("/jaula/inicio"), jd.render_page("/jaula/inicio"))
        self.assertNotEqual(jd.render_page("/jaula/a"), jd.render_page("/jaula/b"))

    def test_canary_present(self):
        self.assertIn(jd.canary_for("/jaula/x").encode(), jd.render_page("/jaula/x"))


if __name__ == "__main__":
    unittest.main()
