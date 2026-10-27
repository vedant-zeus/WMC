import os
import sys
from multiprocessing import Pool

from pulse import SimConfig, LTESimulator
from experiments import SCHEMES

KEYS = ["cell_tput_mbps", "bler", "be_goodput_ratio", "sat_p5", "edge_satisfaction", "video_plr",
        "video_delay_p95_ms", "voip_delay_ms", "qos_satisfied_pct", "avg_power_w", "sleep_ratio",
        "bits_per_joule"]


def run(a):
    kw, load = a
    return LTESimulator(SimConfig(n_tti=int(sys.argv[1]) if len(sys.argv) > 1 else 3000,
                                  load_scale=load, **kw)).run()


if __name__ == "__main__":
    loads = (0.4, 1.3)
    workers = max(1, min(os.cpu_count() or 1, 4))
    with Pool(processes=workers) as p:
        res = p.map(run, [(s, l) for l in loads for s in SCHEMES.values()])

    print(f"{'scheme':22s} load " + " ".join(f"{k[:9]:>9s}" for k in KEYS))
    for r in res:
        print(f"{r['scheme']:22s} {r['load']:4} " + " ".join(f"{r[k]:9.3g}" for k in KEYS))
