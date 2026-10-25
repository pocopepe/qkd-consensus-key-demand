#!/usr/bin/env python3
"""Does the hybrid's solution quality survive a realistic planning budget?

Offline the hybrid attains the upper bound; in the live sweep at a 4 ms planning
budget it fell back to greedy-level latency. Planning happens off the deadline,
but not off the clock -- a 250 ms view that spends 40 ms searching has spent 16%
of itself on the control plane. This sweep varies the search budget and reports
what each buys, so the operating point is chosen rather than inherited.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from qkdnet.allocate import QuorumCoveragePolicy, DensityGreedyPolicy
from qkdnet.kernel import KernelBudget
from scripts.plot_svg import Series, line_chart, write
from scripts.run_experiment import FIG, OUT, agg, run_case
from simulator.hybrid import HybridSwapOptimizer

VIEWS = 500


def main():
    os.makedirs(FIG, exist_ok=True)
    budget = KernelBudget(max_entries=96, max_updates_per_round=24)
    grid = [(200, 0.002), (500, 0.004), (1200, 0.010), (2500, 0.025),
            (5000, 0.050)]
    rows = []
    print(f"{'budget_ms':>10}{'iters':>8}{'hit':>8}{'p50 ms':>9}{'starve':>9}"
          f"{'plan ms/view':>14}")
    for iters, tb in grid:
        pol = HybridSwapOptimizer(iters=iters, time_budget_s=tb)
        t0 = time.perf_counter()
        st = agg(run_case(pol, views=VIEWS, budget=budget))
        wall = (time.perf_counter() - t0) / VIEWS * 1e3
        rows.append({"budget_ms": tb * 1e3, "iters": iters, "plan_ms": wall, **st})
        print(f"{tb*1e3:>10.1f}{iters:>8}{st['hit_rate']:>8.3f}"
              f"{st['lat_p50_ms']:>9.3f}{st['starve_rate']:>9.4f}{wall:>14.2f}",
              flush=True)

    ref = {}
    for name, mk in (("quorum", QuorumCoveragePolicy), ("greedy", DensityGreedyPolicy)):
        t0 = time.perf_counter()
        st = agg(run_case(mk(), views=VIEWS, budget=budget))
        ref[name] = {"plan_ms": (time.perf_counter() - t0) / VIEWS * 1e3, **st}
        print(f"{name:>10}{'':>8}{st['hit_rate']:>8.3f}{st['lat_p50_ms']:>9.3f}"
              f"{st['starve_rate']:>9.4f}{ref[name]['plan_ms']:>14.2f}")

    with open(os.path.join(OUT, "exp_d_compute.json"), "w") as f:
        json.dump({"hybrid": rows, "reference": ref}, f, indent=2)

    write(os.path.join(FIG, "d_compute.svg"), line_chart(
        [Series("hybrid", [r["budget_ms"] for r in rows],
                [r["hit_rate"] for r in rows]),
         Series("quorum (fixed rule)", [rows[0]["budget_ms"], rows[-1]["budget_ms"]],
                [ref["quorum"]["hit_rate"]] * 2, dashed=True),
         Series("greedy (fixed rule)", [rows[0]["budget_ms"], rows[-1]["budget_ms"]],
                [ref["greedy"]["hit_rate"]] * 2, dashed=True)],
        "What a planning budget buys the hybrid optimiser",
        "search time budget per view (ms)", "fast-path hit rate",
        subtitle="Dashed lines are fixed rules, which cost microseconds. The hybrid must earn its compute.",
        y_fmt="{:.2f}"))
    print("\nfigure: results/figures/d_compute.svg")


if __name__ == "__main__":
    main()
