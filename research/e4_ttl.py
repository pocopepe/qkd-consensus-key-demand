#!/usr/bin/env python3
"""E4-TTL -- does the operational ceiling hit_rate <= pi survive TTL > 1?

E4 measured the ceiling with one-view reservations, where the set of live
reservations at view t is exactly what the predictor armed at view t. That is
the condition under which Theorem B's budget-K statement carries over to hit
rate. With a longer TTL, reservations accumulate across views, and the live set
is no longer the predictor's top-K choice for the current view.

So this experiment must separate two things that a naive hit counter conflates:

  fresh hit   served by a reservation created in the current view, i.e. an
              actual successful prediction
  stale hit   served by a reservation created in an earlier view that happens
              to still be alive and to match current demand

A stale hit is not a successful prediction. It is a larger effective budget.
Counting it as prediction would manufacture a ceiling violation out of
bookkeeping.

Workload, predictors, n, and the demand process are imported unchanged from
research/e4_operational.py. Only the reservation lifetime and the instrumentation
differ.
"""
from __future__ import annotations

import itertools
import json
import math
import os
import statistics
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research.e4_operational import (TAG_BITS, T_FAST, T_SLOW, demand_of,
                                     hub_sequence, pi_theory, star)

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
R_FIXED = 8192.0           # the E4 Q3 operating point; Q1 showed hit rate is
                           # flat from R=256 to R=65536, so R is not binding


def run(n, m, k, R, predictor, ttl, views=600, warm=60, seed=0,
        pool_cap_views=40.0):
    rng = np.random.default_rng(seed)
    seq = hub_sequence(n, m, k, views + 2, rng)
    pairs = list(itertools.combinations(range(n), 2))
    cap = R * pool_cap_views
    pool = {p: cap * 0.5 for p in pairs}
    reserved = {}                    # pair -> [bits, expiry_view, created_view]

    hits_fresh = hits_stale = misses = starved = 0
    demanded = wasted = consumed = 0.0
    occ, lat = [], []
    prev_demand = {}

    for t in range(views):
        for p in pairs:
            pool[p] = min(cap, pool[p] + R)
        for p, r in list(reserved.items()):
            if t >= r[1]:
                pool[p] = min(cap, pool[p] + r[0])
                wasted += r[0]
                del reserved[p]

        d = demand_of(n, seq[t])
        S = set(d)
        K = len(S)

        if predictor == "structural":
            want = dict(d)
        elif predictor == "carry":
            want = dict(prev_demand)
        else:
            want = {}

        for p in list(want)[:K]:
            if p in reserved:
                continue                 # already live; not re-armed
            b = want[p]
            if pool[p] >= b:
                pool[p] -= b
                reserved[p] = [b, t + ttl, t]

        if t >= warm:
            occ.append(len(reserved))

        worst = 0.0
        for p, bits in d.items():
            demanded += bits
            r = reserved.get(p)
            if r and r[0] >= bits:
                # fresh iff the reservation was created in THIS view
                if r[2] == t:
                    hits_fresh += 1
                else:
                    hits_stale += 1
                r[0] -= bits
                if r[0] <= 1e-9:
                    del reserved[p]
                consumed += bits
                worst = max(worst, T_FAST)
            elif pool[p] >= bits:
                pool[p] -= bits
                misses += 1
                consumed += bits
                worst = max(worst, T_SLOW)
            else:
                starved += 1
                worst = max(worst, T_SLOW * 4)
        if t >= warm:
            lat.append(worst)
        prev_demand = d

    tot = hits_fresh + hits_stale + misses + starved
    return {"hit_rate": (hits_fresh + hits_stale) / max(tot, 1),
            "hit_fresh": hits_fresh / max(tot, 1),
            "hit_stale": hits_stale / max(tot, 1),
            "starve_rate": starved / max(tot, 1),
            "waste_frac": wasted / max(demanded, 1.0),
            "key_per_demand": (consumed + wasted) / max(demanded, 1.0),
            "occupancy": float(np.mean(occ)) if occ else 0.0,
            "K": K,
            "p50_ms": float(np.percentile(lat, 50) * 1e3) if lat else 0.0}


def main():
    n = 16
    CONFIGS = [(2, 0), (4, 1), (2, 1), (4, 2), (4, 3), (2, 2)]
    TTLS = [1, 2, 4, 8]
    SEEDS = list(range(10))
    rows = []

    print("=" * 108)
    print("T1  Hit rate vs TTL, with fresh and stale hits separated")
    print("=" * 108)
    print(f"  R = {R_FIXED:.0f} bits/pair/view (E4 Q3 operating point; hit rate "
          f"was flat over R=256..65536)\n")
    print(f"  {'pi':>8}{'TTL':>5}{'pred':>12}{'hit':>9}{'fresh':>9}{'stale':>9}"
          f"{'vs pi':>9}{'occ':>7}{'K':>5}{'occ/K':>8}{'waste':>9}{'key/dem':>9}")
    for (m, k) in CONFIGS:
        pi = pi_theory(n, m, k)
        for ttl in TTLS:
            for pred in ("carry", "structural", "none"):
                rr = [run(n, m, k, R_FIXED, pred, ttl, seed=s) for s in SEEDS]
                agg = {key: statistics.mean([x[key] for x in rr]) for key in
                       ("hit_rate", "hit_fresh", "hit_stale", "waste_frac",
                        "key_per_demand", "occupancy", "starve_rate", "p50_ms")}
                agg.update(pi=pi, m=m, k=k, ttl=ttl, predictor=pred,
                           K=rr[0]["K"],
                           ci95_hit=(1.96 * statistics.stdev(
                               [x["hit_rate"] for x in rr]) / math.sqrt(len(rr))
                               if len(rr) > 1 else 0.0))
                rows.append(agg)
                if pred == "carry":
                    print(f"  {pi:>8.4f}{ttl:>5}{pred:>12}{agg['hit_rate']:>9.4f}"
                          f"{agg['hit_fresh']:>9.4f}{agg['hit_stale']:>9.4f}"
                          f"{agg['hit_rate']-pi:>+9.4f}{agg['occupancy']:>7.1f}"
                          f"{agg['K']:>5}{agg['occupancy']/agg['K']:>8.2f}"
                          f"{agg['waste_frac']:>9.4f}{agg['key_per_demand']:>9.4f}")
        print()

    carry = [r for r in rows if r["predictor"] == "carry"]

    print("=" * 108)
    print("T2  Ceiling test: is hit_rate <= pi at each TTL?")
    print("=" * 108)
    print(f"  {'TTL':>5}{'max(hit - pi)':>16}{'violations':>13}"
          f"{'max(fresh - pi)':>18}{'fresh violations':>18}")
    ceiling = []
    for ttl in TTLS:
        g = [r for r in carry if r["ttl"] == ttl]
        dh = [r["hit_rate"] - r["pi"] for r in g]
        df = [r["hit_fresh"] - r["pi"] for r in g]
        ceiling.append({"ttl": ttl, "max_excess_total": max(dh),
                        "viol_total": sum(1 for x in dh if x > 1e-3),
                        "max_excess_fresh": max(df),
                        "viol_fresh": sum(1 for x in df if x > 1e-3)})
        print(f"  {ttl:>5}{max(dh):>+16.4f}{sum(1 for x in dh if x > 1e-3):>13}"
              f"{max(df):>+18.4f}{sum(1 for x in df if x > 1e-3):>18}")

    print()
    print("=" * 108)
    print("T3  Waste vs 1 - pi at each TTL")
    print("=" * 108)
    print(f"  {'TTL':>5}{'corr(1-pi, waste)':>20}{'slope':>10}{'intercept':>12}"
          f"{'mean waste':>13}")
    waste = []
    for ttl in TTLS:
        g = [r for r in carry if r["ttl"] == ttl]
        x = np.array([1 - r["pi"] for r in g]); y = np.array([r["waste_frac"] for r in g])
        c = float(np.corrcoef(x, y)[0, 1]) if len(set(y)) > 1 else float("nan")
        sl, ic = (np.polyfit(x, y, 1) if len(set(y)) > 1 else (float("nan"),) * 2)
        waste.append({"ttl": ttl, "corr": c, "slope": float(sl),
                      "intercept": float(ic), "mean_waste": float(y.mean())})
        print(f"  {ttl:>5}{c:>20.4f}{sl:>10.4f}{ic:>+12.4f}{y.mean():>13.4f}")

    rec = {"experiment_id": "E4TTL-001",
           "utc": datetime.now(timezone.utc).isoformat(),
           "n": n, "R": R_FIXED, "ttls": TTLS, "seeds": len(SEEDS),
           "rows": rows, "ceiling": ceiling, "waste": waste}
    os.makedirs(RESULTS, exist_ok=True)
    json.dump(rec, open(os.path.join(RESULTS, "E4TTL-001.json"), "w"), indent=2)
    print(f"\nwrote {RESULTS}/E4TTL-001.json")


if __name__ == "__main__":
    main()
