"""Run the full evaluation: baselines vs PULSE, ablation, and a load sweep.

Usage: python experiments.py [--tti 3000] [--seeds 3]
Outputs: results/raw_results.csv, results/summary.csv, results/*.png
"""
import argparse
import os
from multiprocessing import Pool

import numpy as np
import pandas as pd

from pulse import SimConfig, LTESimulator

SCHEMES = {
    "rr": dict(scheduler="rr"),
    "maxci": dict(scheduler="maxci"),
    "pf": dict(scheduler="pf"),
    "mlwdf": dict(scheduler="mlwdf"),
    "pulse": dict(scheduler="pulse"),
    "pulse_olla": dict(scheduler="pulse", olla=True),
    "pulse_ica": dict(scheduler="pulse", ica=True),
    "pulse_ica_olla": dict(scheduler="pulse", ica=True, olla=True),
    "pulse_ica_sfr": dict(scheduler="pulse", ica=True, olla=True, sfr=True),
    "pulse_dtx": dict(scheduler="pulse", ica=True, olla=True, sfr=True, energy=True, eco_batching=False),
    "pulse_full": dict(scheduler="pulse", ica=True, olla=True, sfr=True, energy=True),
}
LOADS = [0.3, 0.6, 0.9, 1.2, 1.5]


def _run(args):
    key, load, seed, tti = args
    m = LTESimulator(SimConfig(n_tti=tti, load_scale=load, seed=seed, **SCHEMES[key])).run()
    m["key"] = key
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tti", type=int, default=3000)
    ap.add_argument("--seeds", type=int, default=3)
    a = ap.parse_args()
    os.makedirs("results", exist_ok=True)
    jobs = [(k, l, s, a.tti) for s in range(1, a.seeds + 1) for l in LOADS for k in SCHEMES]
    workers = max(1, min(os.cpu_count() or 1, 4))
    with Pool(processes=workers) as p:
        rows = p.map(_run, jobs, chunksize=1)
    df = pd.DataFrame(rows)
    df.to_csv("results/raw_results.csv", index=False)
    summary = df.drop(columns=["seed"]).groupby(["key", "scheme", "load"], sort=False).mean(numeric_only=True)
    summary.reset_index().to_csv("results/summary.csv", index=False)
    print("Saved results/raw_results.csv and results/summary.csv")


if __name__ == "__main__":
    main()
