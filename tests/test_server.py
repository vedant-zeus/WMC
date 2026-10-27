"""Unit tests for serve.py HTTP server and API endpoints."""
import unittest
import json
import threading
import time
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from serve import Handler


class TestServerAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Bind on an ephemeral free port
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _request(self, method, path, body=None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Content-Type": "application/json"} if body else {}
        data = json.dumps(body) if body else None
        conn.request(method, path, body=data, headers=headers)
        res = conn.getresponse()
        raw = res.read().decode("utf-8")
        conn.close()
        return res.status, json.loads(raw) if "application/json" in res.getheader("Content-Type", "") else raw

    def test_get_schemes(self):
        status, data = self._request("GET", "/api/schemes")
        self.assertEqual(status, 200)
        self.assertIn("schemes", data)
        scheme_ids = [s["id"] for s in data["schemes"]]
        self.assertListEqual(scheme_ids, ["rr", "maxci", "pf", "mlwdf", "pulse"])

    def test_get_summary(self):
        status, data = self._request("GET", "/api/summary")
        self.assertEqual(status, 200)
        self.assertIn("summary", data)

    def test_post_simulate(self):
        body = {
            "config": {
                "scheduler": "pf",
                "load_scale": 0.5,
                "n_tti": 60,
                "seed": 99
            }
        }
        status, data = self._request("POST", "/api/simulate", body)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("ok"))
        self.assertIn("metrics", data)
        self.assertIn("cell_tput_mbps", data["metrics"])

    def test_post_compare(self):
        body = {
            "schedulers": ["rr", "pf", "pulse"],
            "config": {
                "load_scale": 0.6,
                "n_tti": 50,
                "seed": 10
            }
        }
        status, data = self._request("POST", "/api/compare", body)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("ok"))
        self.assertIn("results", data)
        for s in ["rr", "pf", "pulse"]:
            self.assertIn(s, data["results"])
            self.assertIn("cell_tput_mbps", data["results"][s])


if __name__ == "__main__":
    unittest.main()
