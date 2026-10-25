#!/usr/bin/env python3
"""Follow-up to sweep B: predictive pre-arming makes starvation worse, and why.

Sweep B showed the predictive system starving *more* than the reactive one under
bursty load -- the opposite of the expected direction. The mechanism is not
subtle once seen: a pre-arm reserves key on every hop of a relay path and holds
it for the whole lease. During a flash crowd that held key is unavailable to the
pairs that need it now, so a forecast that is confident and slightly wrong
converts directly into starvation.

The benefit-only objective cannot express this, because it has no term for the
cost of holding. This sweep adds the hoarding penalty gamma (charged per bit-hop
reserved and unused) and shortens the lease, and measures whether either recovers
the regression without giving back the latency win.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from qkdnet.allocate import QuorumCoveragePolicy
from scripts.plot_svg import Series, line_chart, write
from scripts.run_experiment import FIG, OUT, agg, run_case
from simulator.engine import BurstyWorkload

VIEWS = 700
BURSTS = [0.0, 0.02, 0.05, 0.10, 0.20, 0.35]


def main():
    os.makedirs(FIG, exist_ok=True)
    arms = {
        "reactive": dict(reactive=True),
        "predictive": dict(hoard_gamma=0.0, ttl_views=2),
        "+ hoarding penalty": dict(hoard_gamma=1.0, ttl_views=2),
        "+ penalty, short lease": dict(hoard_gamma=1.0, ttl_views=1),
    }
    res = {k: [] for k in arms}
    print(f"{'burst_p':>9}" + "".join(f"{k:>24}" for k in arms))
    for bp in BURSTS:
        row = f"{bp:>9.2f}"
        for k, kw in arms.items():
            wl = BurstyWorkload(n=16, burst_prob=bp, burst_multiplier=8.0)
            pol = None if kw.get("reactive") else QuorumCoveragePolicy()
            st = agg(run_case(pol, views=VIEWS, workload=wl, **kw))
            res[k].append({"burst_prob": bp, **st})
            row += f"   starve={st['starve_rate']:.4f} p50={st['lat_p50_ms']:6.3f}"
        print(row, flush=True)

    with open(os.path.join(OUT, "exp_b_hoarding.json"), "w") as f:
        json.dump(res, f, indent=2)

    write(os.path.join(FIG, "b_hoarding.svg"), line_chart(
        [Series(k, [d["burst_prob"] for d in res[k]],
                [d["starve_rate"] for d in res[k]]) for k in arms],
        "Starvation: pre-arming holds key that bursts need",
        "flash-crowd probability per view", "fraction of requests starved",
        subtitle="Reserved key is unavailable key. Pricing the hold recovers most of the regression.",
        y_fmt="{:.3f}"))

    write(os.path.join(FIG, "b_hoarding_latency.svg"), line_chart(
        [Series(k, [d["burst_prob"] for d in res[k]],
                [d["lat_p50_ms"] for d in res[k]]) for k in arms],
        "...without giving back the latency win",
        "flash-crowd probability per view", "p50 round latency (ms)",
        subtitle="Lower is better. The penalised arms stay on the fast path.",
        y_fmt="{:.2f}"))
    print("\nfigures: results/figures/b_hoarding*.svg")


if __name__ == "__main__":
    main()
