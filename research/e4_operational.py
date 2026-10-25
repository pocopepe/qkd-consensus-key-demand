#!/usr/bin/env python3
"""E4 -- does the theoretical quantity change an engineering decision?

Theorem A gives pi in closed form; Theorem B says a carry-forward predictor
attains exactly pi and no more. Both are statements about *prediction accuracy*.
Neither, on its own, says anything about key material, latency, or cost. This
experiment asks whether pi translates into an operational requirement, and it is
designed so that "no" is a reportable outcome.

Two operational questions, deliberately separated:

  Q1  Is pi a hard ceiling on fast-path hit rate, or can it be bought past with
      more key? If more key-generation rate lifts a carry-forward predictor
      above pi, then pi is an accuracy curiosity and not an operational limit.

  Q2  Below that ceiling, how much extra key-generation rate does a
      carry-forward predictor need to reach the same hit rate as a
      schedule-aware one, and does that requirement track 1 - pi?

Model. n validators, hub-union workload with configurable (m, k) so pi is known
exactly from Theorem A. Each pair has its own key pool refilled at R bits per
view; this isolates the predictor's effect from relay topology, which is not
what E4 is about. Pre-arming reserves from the pool and expires after a TTL, so
a wrong pre-arm is wasted key. A miss falls back to drawing from the pool
directly, which still consumes key but costs the slow path.
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

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
TAG_BITS = 256.0
T_FAST, T_SLOW = 14.2e-6, 1.042e-3      # both measured, E1/E2 and kme_bench


def pi_theory(n, m, k):
    return (k * (n - 1) + m * (m - k)) / (m * (n - 1))


def star(n, c):
    return {(min(c, j), max(c, j)) for j in range(n) if j != c}


def hub_sequence(n, m, k, views, rng):
    """Hub sets with exact overlap k between consecutive views."""
    hubs = sorted(rng.choice(n, size=m, replace=False))
    out = [list(hubs)]
    for _ in range(views):
        keep = list(rng.permutation(hubs))[:k]
        pool = [v for v in range(n) if v not in set(hubs)]
        new = list(rng.choice(pool, size=m - k, replace=False)) if m > k else []
        hubs = sorted(int(x) for x in list(keep) + list(new))
        out.append(list(hubs))
    return out


def demand_of(n, hubs):
    d = {}
    for h in hubs:
        for p in star(n, h):
            d[p] = d.get(p, 0.0) + TAG_BITS
    return d


def run(n, m, k, R, predictor, views=600, warm=60, seed=0, ttl=1,
        pool_cap_views=40.0):
    """One configuration. R is bits generated per pair per view."""
    rng = np.random.default_rng(seed)
    seq = hub_sequence(n, m, k, views + 2, rng)
    pairs = list(itertools.combinations(range(n), 2))
    cap = R * pool_cap_views
    pool = {p: cap * 0.5 for p in pairs}
    reserved = {}          # pair -> (bits, expiry_view)

    hits = misses = starved = 0
    demanded = wasted = consumed = 0.0
    lat = []
    prev_support, prev_demand = set(), {}

    for t in range(views):
        for p in pairs:
            pool[p] = min(cap, pool[p] + R)
        for p, (b, exp) in list(reserved.items()):
            if t >= exp:
                pool[p] = min(cap, pool[p] + b)   # roll back unused reservation
                wasted += b
                del reserved[p]

        d = demand_of(n, seq[t])
        S = set(d)
        K = len(S)

        # Each predictor arms the demand IT predicts, per pair. Arming a flat
        # per-pair amount instead would over-arm single-hub pairs and charge the
        # structural predictor for waste that is an artefact of the sizing rule,
        # not of prediction error.
        if predictor == "structural":
            want = dict(d)                      # knows the hub set: coverage 1
        elif predictor == "carry":
            want = dict(prev_demand)            # last-observation: attains pi
        else:
            want = {}

        for p in list(want)[:K]:
            if p in reserved:
                continue
            b = want[p]
            if pool[p] >= b:
                pool[p] -= b
                reserved[p] = (b, t + ttl)

        worst = 0.0
        for p, bits in d.items():
            demanded += bits
            r = reserved.get(p)
            if r and r[0] >= bits:
                nb = r[0] - bits
                reserved[p] = (nb, r[1]) if nb > 0 else None
                if nb <= 0:
                    del reserved[p]
                else:
                    reserved[p] = (nb, r[1])
                hits += 1
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
        prev_support, prev_demand = S, d

    tot = hits + misses + starved
    return {"hit_rate": hits / max(tot, 1),
            "starve_rate": starved / max(tot, 1),
            "waste_frac": wasted / max(demanded, 1.0),
            "key_per_demand": (consumed + wasted) / max(demanded, 1.0),
            "p50_ms": float(np.percentile(lat, 50) * 1e3) if lat else 0.0}


def min_rate_for(n, m, k, predictor, target, seed, lo=64.0, hi=200000.0):
    """Smallest R reaching `target` hit rate; None if unreachable at hi."""
    if run(n, m, k, hi, predictor, views=300, warm=40, seed=seed)["hit_rate"] < target:
        return None
    for _ in range(22):
        mid = math.sqrt(lo * hi)
        if run(n, m, k, mid, predictor, views=300, warm=40, seed=seed)["hit_rate"] >= target:
            hi = mid
        else:
            lo = mid
    return hi


def main():
    n = 16
    CONFIGS = [(2, 0), (4, 1), (2, 1), (4, 2), (4, 3), (2, 2)]
    SEEDS = list(range(20))

    print("=" * 96)
    print("Q1  Is pi a ceiling on hit rate, or can more key buy past it?")
    print("=" * 96)
    print("  Sweeping key-generation rate over three orders of magnitude.\n")
    print(f"  {'m':>3}{'k':>3}{'pi':>8}   " +
          "".join(f"{'R=' + str(r):>11}" for r in (256, 1024, 4096, 16384, 65536)) +
          f"{'ceiling':>10}")
    q1 = []
    for (m, k) in CONFIGS:
        pi = pi_theory(n, m, k)
        row = f"  {m:>3}{k:>3}{pi:>8.4f}   "
        vals = []
        for R in (256, 1024, 4096, 16384, 65536):
            hs = [run(n, m, k, R, "carry", views=300, warm=40, seed=s)["hit_rate"]
                  for s in SEEDS[:6]]
            vals.append(statistics.mean(hs))
            row += f"{statistics.mean(hs):>11.4f}"
        row += f"{max(vals):>10.4f}"
        print(row)
        q1.append({"m": m, "k": k, "pi": pi, "hit_by_R": vals, "ceiling": max(vals)})

    errs = [abs(r["ceiling"] - r["pi"]) for r in q1]
    print(f"\n  max |ceiling - pi| = {max(errs):.4f}")
    print("  If the ceiling tracks pi and does not rise with R, then pi is an")
    print("  operational limit and not merely an accuracy statistic.")

    print()
    print("=" * 96)
    print("Q2  Over-provisioning: extra key-rate a carry-forward predictor needs")
    print("=" * 96)
    TARGET = 0.45          # below the lowest ceiling tested, so reachable by both
    print(f"  Target hit rate = {TARGET}; 20 seeds; binary search on R.\n")
    print(f"  {'m':>3}{'k':>3}{'pi':>8}{'1-pi':>8}"
          f"{'R* structural':>15}{'R* carry':>12}{'ratio':>9}{'95% CI':>9}")
    q2 = []
    for (m, k) in CONFIGS:
        pi = pi_theory(n, m, k)
        if pi < TARGET + 0.02:
            print(f"  {m:>3}{k:>3}{pi:>8.4f}{1-pi:>8.4f}"
                  f"{'--':>15}{'unreachable':>12}{'--':>9}{'--':>9}")
            q2.append({"m": m, "k": k, "pi": pi, "ratio": None,
                       "reason": "target above pi ceiling"})
            continue
        rs, rc = [], []
        for s in SEEDS:
            a = min_rate_for(n, m, k, "structural", TARGET, s)
            b = min_rate_for(n, m, k, "carry", TARGET, s)
            if a and b:
                rs.append(a); rc.append(b)
        if not rs:
            continue
        ratios = [b / a for a, b in zip(rs, rc)]
        mr = statistics.mean(ratios)
        ci = 1.96 * statistics.stdev(ratios) / math.sqrt(len(ratios)) if len(ratios) > 1 else 0.0
        q2.append({"m": m, "k": k, "pi": pi, "R_struct": statistics.mean(rs),
                   "R_carry": statistics.mean(rc), "ratio": mr, "ci95": ci,
                   "n_seeds": len(ratios)})
        print(f"  {m:>3}{k:>3}{pi:>8.4f}{1-pi:>8.4f}"
              f"{statistics.mean(rs):>15.0f}{statistics.mean(rc):>12.0f}"
              f"{mr:>9.3f}{ci:>9.3f}")

    print()
    print("=" * 96)
    print("Q3  Wasted key and total key per unit demand")
    print("=" * 96)
    print(f"  {'m':>3}{'k':>3}{'pi':>8}{'predictor':>13}{'hit':>8}"
          f"{'waste/demand':>14}{'key/demand':>12}{'p50 ms':>9}")
    q3 = []
    for (m, k) in CONFIGS:
        pi = pi_theory(n, m, k)
        for pr in ("structural", "carry", "none"):
            rr = [run(n, m, k, 8192.0, pr, views=400, warm=60, seed=s) for s in SEEDS[:10]]
            row = {"m": m, "k": k, "pi": pi, "predictor": pr,
                   "hit": statistics.mean([x["hit_rate"] for x in rr]),
                   "waste": statistics.mean([x["waste_frac"] for x in rr]),
                   "key_per_demand": statistics.mean([x["key_per_demand"] for x in rr]),
                   "p50_ms": statistics.mean([x["p50_ms"] for x in rr])}
            q3.append(row)
            print(f"  {m:>3}{k:>3}{pi:>8.4f}{pr:>13}{row['hit']:>8.4f}"
                  f"{row['waste']:>14.4f}{row['key_per_demand']:>12.4f}"
                  f"{row['p50_ms']:>9.4f}")

    rec = {"experiment_id": "E4-operational-001",
           "utc": datetime.now(timezone.utc).isoformat(),
           "n": n, "target_hit_rate": TARGET, "seeds": len(SEEDS),
           "q1_ceiling": q1, "q2_overprovision": q2, "q3_waste": q3}
    os.makedirs(RESULTS, exist_ok=True)
    json.dump(rec, open(os.path.join(RESULTS, "E4-operational-001.json"), "w"),
              indent=2)
    print(f"\nwrote {RESULTS}/E4-operational-001.json")


if __name__ == "__main__":
    main()
