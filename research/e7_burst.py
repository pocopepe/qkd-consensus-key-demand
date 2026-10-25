#!/usr/bin/env python3
"""E7 -- is TTL intrinsically beneficial, or does its effect depend on burstiness?

E6 found TTL=8 dominant on a stationary workload with a shared pool. E1 found
the opposite -- long leases harmful -- under flash crowds. E7 puts both
workloads on the identical E6 pool so that workload dynamics is the only thing
that differs.

WORKLOADS

  W1 stationary   the E6 hub-union generator unchanged; demand multiplier 1.0
                  every view.
  W2 bursty       the same hub-union support, with the per-view demand
                  multiplier drawn from E1's BurstyWorkload generator
                  (simulator/engine.py), unchanged: 8.67% of views carry a 6x
                  multiplier, mean multiplier 1.4336. The SUPPORT is identical
                  to W1; only the magnitude per pair varies.

  W2n bursty,     a DIAGNOSTIC arm, not part of the specified matrix. W2 carries
      mean-       1.4336x the mean load of W1, so any TTL reversal in W2 could be
      matched     caused by higher mean load rather than by burstiness. W2n
                  divides the multiplier by its mean so the mean load matches W1
                  exactly and only the variance differs. It exists to separate
                  those two explanations and is reported separately.

Everything else -- pool capacity, refill rate, predictors, n, seeds -- is held
identical across workloads, per the methodological rule.
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research.e4_operational import TAG_BITS, T_FAST, T_SLOW, demand_of, hub_sequence, pi_theory
from simulator.engine import BurstyWorkload

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
REFILL_RATIO = 1.5
CAPACITIES = {"ample": 10.0, "scarce": 0.75}
CONFIGS = [(2, 0), (2, 1), (4, 3), (2, 2)]
TTLS = [1, 2, 4, 8]
PREDICTORS = ["carry", "structural"]
WORKLOADS = ["stationary", "bursty"]
BURST_MEAN = 1.4336            # measured over 200k draws of the E1 generator


def mean_demand(n, m):
    return m * (n - 1) * TAG_BITS


def run(n, m, k, predictor, ttl, capacity_factor, workload,
        views=600, warm=80, seed=0):
    rng = np.random.default_rng(seed)
    seq = hub_sequence(n, m, k, views + 2, rng)
    D = mean_demand(n, m)
    cap = capacity_factor * D
    refill = REFILL_RATIO * D
    pool = cap * 0.5
    bw = BurstyWorkload(n=n) if workload != "stationary" else None

    reserved = {}
    fresh = stale = pred_miss = cont_miss = starved = 0
    consumed = expired = demanded = 0.0
    occ, lat = [], []
    per_req, per_fast = {}, {}
    prev_demand = {}
    burst_views = 0

    for t in range(views):
        if bw is None:
            mult = 1.0
        else:
            mult, _, in_b = bw.step(rng)
            if workload == "bursty_matched":
                mult /= BURST_MEAN
            burst_views += int(in_b)

        pool = min(cap, pool + refill)
        for p, r in list(reserved.items()):
            if t >= r[1]:
                pool = min(cap, pool + r[0])
                expired += r[0]
                del reserved[p]

        base = demand_of(n, seq[t])
        d = {p: b * mult for p, b in base.items()}
        K = len(d)

        want = dict(d) if predictor == "structural" else dict(prev_demand)
        arm_list = list(want)
        rng.shuffle(arm_list)
        failed = set()
        for p in arm_list[:K]:
            if p in reserved:
                continue
            b = want[p]
            if pool >= b:
                pool -= b
                reserved[p] = [b, t + ttl, t]
            else:
                failed.add(p)

        if t >= warm:
            occ.append(len(reserved))

        order = list(d)
        rng.shuffle(order)
        for p in order:
            bits = d[p]
            demanded += bits
            per_req[p] = per_req.get(p, 0) + 1
            r = reserved.get(p)
            if r and r[0] >= bits:
                if r[2] == t:
                    fresh += 1
                else:
                    stale += 1
                per_fast[p] = per_fast.get(p, 0) + 1
                r[0] -= bits
                if r[0] <= 1e-9:
                    del reserved[p]
                consumed += bits
                if t >= warm:
                    lat.append(T_FAST)
            elif pool >= bits:
                pool -= bits
                consumed += bits
                if p in failed:
                    cont_miss += 1
                else:
                    pred_miss += 1
                if t >= warm:
                    lat.append(T_SLOW)
            else:
                starved += 1
                if t >= warm:
                    lat.append(T_SLOW * 4)
        prev_demand = d

    tot = fresh + stale + pred_miss + cont_miss + starved
    rates = [per_fast.get(p, 0) / v for p, v in per_req.items() if v > 0]
    la = np.array(lat) if lat else np.array([0.0])
    return {"fresh": fresh / max(tot, 1), "stale": stale / max(tot, 1),
            "total_hit": (fresh + stale) / max(tot, 1),
            "pred_miss": pred_miss / max(tot, 1),
            "cont_miss": cont_miss / max(tot, 1),
            "starve": starved / max(tot, 1),
            "waste": expired / max(demanded, 1.0),
            "key_per_demand": (consumed + expired) / max(demanded, 1.0),
            "peak_occ": float(max(occ)) if occ else 0.0,
            "unfairness": (max(rates) - min(rates)) if rates else 0.0,
            "lat_mean_ms": float(la.mean() * 1e3),
            "lat_p95_ms": float(np.percentile(la, 95) * 1e3),
            "burst_frac": burst_views / views}


def main():
    n = 16
    SEEDS = list(range(10))
    rows = []
    arms = WORKLOADS + ["bursty_matched"]

    print("=" * 122)
    print("E7  Burstiness x TTL x shared capacity")
    print("=" * 122)
    print(f"  pool: refill {REFILL_RATIO}xD/view; capacity C x D, "
          f"C = {CAPACITIES};  burst = E1 generator (8.67% of views at 6x, "
          f"mean {BURST_MEAN})")
    print(f"  'bursty_matched' is a DIAGNOSTIC arm with the multiplier divided "
          f"by {BURST_MEAN} so mean load equals stationary.\n")

    for wl in arms:
        for capname, cfac in CAPACITIES.items():
            print(f"  --- workload={wl}  capacity={capname} (C={cfac}) ---")
            print(f"  {'pi':>8}{'TTL':>5}{'fresh':>8}{'total':>8}{'starve':>8}"
                  f"{'waste':>8}{'lat ms':>9}{'p95 ms':>9}{'occ':>7}{'unfair':>8}")
            for (m, k) in CONFIGS:
                pi = pi_theory(n, m, k)
                for ttl in TTLS:
                    rr = [run(n, m, k, "carry", ttl, cfac, wl, seed=s) for s in SEEDS]
                    agg = {key: statistics.mean([x[key] for x in rr]) for key in rr[0]}
                    agg.update(pi=pi, m=m, k=k, workload=wl, capacity=capname,
                               cfac=cfac, ttl=ttl, predictor="carry",
                               ci95_starve=(1.96 * statistics.stdev(
                                   [x["starve"] for x in rr]) / math.sqrt(len(rr))
                                   if len(rr) > 1 else 0.0))
                    rows.append(agg)
                    if pi in (0.13333333333333333, 0.5666666666666667):
                        print(f"  {pi:>8.4f}{ttl:>5}{agg['fresh']:>8.4f}"
                              f"{agg['total_hit']:>8.4f}{agg['starve']:>8.4f}"
                              f"{agg['waste']:>8.4f}{agg['lat_mean_ms']:>9.4f}"
                              f"{agg['lat_p95_ms']:>9.4f}{agg['peak_occ']:>7.0f}"
                              f"{agg['unfairness']:>8.4f}")
                    # structural reference
                    rs = [run(n, m, k, "structural", ttl, cfac, wl, seed=s) for s in SEEDS]
                    ags = {key: statistics.mean([x[key] for x in rs]) for key in rs[0]}
                    ags.update(pi=pi, m=m, k=k, workload=wl, capacity=capname,
                               cfac=cfac, ttl=ttl, predictor="structural")
                    rows.append(ags)
            print()

    rec = {"experiment_id": "E7-burst-001",
           "utc": datetime.now(timezone.utc).isoformat(),
           "n": n, "refill_ratio": REFILL_RATIO, "capacities": CAPACITIES,
           "ttls": TTLS, "seeds": len(SEEDS), "burst_mean": BURST_MEAN,
           "rows": rows}
    os.makedirs(RESULTS, exist_ok=True)
    json.dump(rec, open(os.path.join(RESULTS, "E7-burst-001.json"), "w"), indent=2)
    print(f"wrote {RESULTS}/E7-burst-001.json")


if __name__ == "__main__":
    main()
