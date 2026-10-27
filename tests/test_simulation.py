"""Comprehensive unit tests for PULSE-LTE simulation engine and schedulers."""
import unittest
import numpy as np

from pulse import SimConfig, LTESimulator
from pulse.phy import sinr_to_cqi, cqi_to_eff, bler, CQI_SINR_DB, CQI_EFF
from pulse.schedulers import schedule, allocate, VOIP, VIDEO, BE


class TestPhysicalLayer(unittest.TestCase):
    """Test 3GPP TS 36.213 physical layer mappings and models."""

    def test_sinr_to_cqi_range(self):
        # Very low SINR should give CQI 0 (out of range)
        self.assertEqual(sinr_to_cqi(-15.0), 0)
        # Very high SINR should cap at CQI 15
        self.assertEqual(sinr_to_cqi(30.0), 15)
        # Check monotonicity across range
        sinrs = np.linspace(-10, 25, 36)
        cqis = [sinr_to_cqi(s) for s in sinrs]
        for i in range(len(cqis) - 1):
            self.assertLessEqual(cqis[i], cqis[i + 1])

    def test_cqi_to_spectral_efficiency(self):
        self.assertEqual(cqi_to_eff(0), 0.0)
        for i in range(1, 15):
            self.assertGreater(cqi_to_eff(i + 1), cqi_to_eff(i))
        self.assertAlmostEqual(cqi_to_eff(15), 5.5547, places=3)

    def test_bler_curve(self):
        # Near CQI threshold, BLER should be approx 10% (0.10)
        for cqi in range(1, 16):
            thr = CQI_SINR_DB[cqi - 1]
            b = bler(thr, cqi)
            self.assertAlmostEqual(b, 0.10, places=2)
            # Higher SINR should give lower error rate
            self.assertLess(bler(thr + 5.0, cqi), b)
            # Lower SINR should give higher error rate
            self.assertGreater(bler(thr - 5.0, cqi), b)


class TestSchedulers(unittest.TestCase):
    """Verify LTE resource allocation constraints and scheduler algorithms."""

    def setUp(self):
        self.n_rb = 25
        self.n_users = 6
        self.users = np.arange(self.n_users)
        self.est_rate = np.full((self.n_users, self.n_rb), 1000.0)
        # Differing channel conditions across users
        for u in range(self.n_users):
            self.est_rate[u, :] = (u + 1) * 300.0

        self.ctx = {
            "buffer": np.array([5000.0, 5000.0, 5000.0, 5000.0, 5000.0, 5000.0]),
            "rbar": np.full(self.n_users, 1000.0),
            "hol": np.array([5.0, 25.0, 50.0, 75.0, 95.0, 10.0]),
            "cls": np.array([VOIP, VIDEO, BE, VOIP, VIDEO, BE]),
            "deadline": np.array([100.0, 300.0, 1e6, 100.0, 300.0, 1e6]),
            "last_served": np.zeros(self.n_users),
            "t": 100,
            "edge": np.array([False, False, True, False, True, False]),
            "edge_rb_mask": np.zeros(self.n_rb, dtype=bool)
        }
        self.ctx["edge_rb_mask"][:8] = True

    def test_prb_exclusive_allocation(self):
        """In LTE, each PRB in a cell must be assigned to at most one user (or left unused)."""
        for s in ["rr", "maxci", "pf", "mlwdf", "pulse"]:
            cfg = SimConfig(n_rb=self.n_rb, scheduler=s)
            alloc = schedule(cfg, self.ctx, self.users, self.est_rate)
            self.assertEqual(len(alloc), self.n_rb)
            for prb_val in alloc:
                # Must be -1 (idle) or a valid user index
                self.assertTrue(prb_val == -1 or prb_val in self.users)

    def test_max_ci_opportunism(self):
        """Max C/I should allocate PRBs to users with highest instantaneous channel rate."""
        cfg = SimConfig(n_rb=self.n_rb, scheduler="maxci")
        alloc = schedule(cfg, self.ctx, self.users, self.est_rate)
        # User 5 has highest est_rate ((5+1)*300 = 1800)
        # User 5 has 5000 bits backlog, so will take first few PRBs until backlog is met
        self.assertEqual(alloc[0], 5)

    def test_empty_buffer_returns_idle(self):
        empty_ctx = dict(self.ctx)
        empty_ctx["buffer"] = np.zeros(self.n_users)
        cfg = SimConfig(n_rb=self.n_rb, scheduler="pf")
        alloc = schedule(cfg, empty_ctx, self.users, self.est_rate)
        self.assertTrue((alloc == -1).all())

    def test_round_robin_cycles(self):
        cfg = SimConfig(n_rb=self.n_rb, scheduler="rr")
        # Give user 0 older last_served
        self.ctx["last_served"] = np.array([0.0, 10.0, 20.0, 30.0, 40.0, 50.0])
        alloc = schedule(cfg, self.ctx, self.users, self.est_rate)
        # User 0 was served longest ago, should get first PRB
        self.assertEqual(alloc[0], 0)


class TestSimulator(unittest.TestCase):
    """End-to-end multi-TTI simulation verification."""

    def test_simulation_runs_and_metrics_bounded(self):
        for s in ["rr", "maxci", "pf", "mlwdf", "pulse"]:
            cfg = SimConfig(n_cells=7, n_tti=100, scheduler=s, seed=42)
            sim = LTESimulator(cfg)
            res = sim.run()

            # Verify all metrics exist and respect domain physics
            self.assertGreater(res["cell_tput_mbps"], 0.0)
            self.assertGreater(res["spectral_eff"], 0.0)
            self.assertGreaterEqual(res["bler"], 0.0)
            self.assertLessEqual(res["bler"], 1.0)
            self.assertGreaterEqual(res["rb_util"], 0.0)
            self.assertLessEqual(res["rb_util"], 1.0)
            self.assertGreaterEqual(res["avg_power_w"], cfg.psleep_w)
            self.assertGreater(res["bits_per_joule"], 0.0)
            self.assertGreaterEqual(res["sleep_ratio"], 0.0)
            self.assertLessEqual(res["sleep_ratio"], 1.0)
            self.assertGreaterEqual(res["jain_fairness"], 0.0)
            self.assertLessEqual(res["jain_fairness"], 1.0)
            self.assertGreaterEqual(res["qos_satisfied_pct"], 0.0)
            self.assertLessEqual(res["qos_satisfied_pct"], 100.0)

    def test_pulse_ablation_combinations(self):
        """Test modular ablation toggles of PULSE."""
        configs = [
            {"olla": False, "ica": False, "sfr": False, "energy": False},
            {"olla": True, "ica": False, "sfr": False, "energy": False},
            {"olla": True, "ica": True, "sfr": False, "energy": False},
            {"olla": True, "ica": True, "sfr": True, "energy": False},
            {"olla": True, "ica": True, "sfr": True, "energy": True, "eco_batching": False},
            {"olla": True, "ica": True, "sfr": True, "energy": True, "eco_batching": True},
        ]
        for kw in configs:
            cfg = SimConfig(n_cells=7, n_tti=60, scheduler="pulse", seed=12, **kw)
            sim = LTESimulator(cfg)
            res = sim.run()
            self.assertIn("cell_tput_mbps", res)
            self.assertGreater(res["cell_tput_mbps"], 0.0)


if __name__ == "__main__":
    unittest.main()
