#!/usr/bin/env python3
"""E6 -- does the structural result survive a finite SHARED QKD key pool?

E4 and E4-TTL used independent per-pair pools, chosen to isolate the predictor.
Under that model holding key for one pair costs another nothing, and longer
leases looked uniformly good. E1 measured the opposite sign under shared relay
pools: pre-arming raised starvation up to 33% and shortening the lease fixed it.
This experiment puts the E4 workload and predictors on a shared pool so the two
findings can be reconciled on one substrate.

POOL MODEL, stated in full before any result:

  * ONE pool shared by every validator pair -- a QKD relay bottleneck.
  * Capacity  cap = C * D, where D is mean demand per view. C defines the
    contention regime (see below).
  * Refill    R = 1.5 * D bits per view, clipped at cap. Held fixed across
    regimes so that CAPACITY, not supply rate, is the contention mechanism.
  * Reservations consume pool capacity IMMEDIATELY when armed.
  * An expired (unused) reservation RETURNS its capacity to the pool and is
    counted as waste.
  * A consumed reservation does not return capacity.
  * Slow-path service draws from the pool directly.
  * SCHEDULING: serving follows a per-view RANDOM permutation of the demanding
    pairs, seeded from the run seed, so service order carries no priority.
    ARMING order is a parameter, because the first version of this experiment
    left it deterministic (the predictor's emission order) and that turned out
    to be a hidden priority rule: under scarcity the same pairs were armed every
    view and the structural predictor showed pair-level unfairness of exactly
    1.0. Both orders are therefore measured:
        arm_order = "fifo"    predictor emission order (deterministic)
        arm_order = "random"  per-view random permutation of the wanted set
    Pair-level unfairness is reported for both.

CONTENTION REGIMES, derived from the outstanding-reservation requirement rather
than chosen to produce an outcome:

  A reservation lives TTL views, and roughly one view of demand is armed per
  view, so outstanding reservations approach T * D at TTL = T. Hence:

    low       C = 10.0  exceeds the TTL=8 requirement; contention impossible
    moderate  C =  2.5  sufficient for TTL <= 2, insufficient for TTL >= 4
    high      C =  0.75 insufficient even for a single view's arming

  FIRST ATTEMPT, RECORDED RATHER THAN DELETED. The regimes were initially
  defined on the refill rate (rho = 3.0 / 1.5 / 1.0) and produced ZERO
  contention in all 48 cells: starvation and contention-miss were 0.0000
  everywhere and all three regimes gave identical numbers. The reason is in the
  model above -- an expired reservation RETURNS its capacity, so waste is a
  temporary hold rather than a permanent drain, and steady-state consumption
  equals actual demand regardless of how much is mis-armed. Refill is therefore
  the wrong knob; instantaneous capacity is the right one. The axis was changed
  for that reason, not after inspecting which axis gave a preferred result.

THREE FAILURE MODES, kept separate:

    prediction miss    the pair was not predicted
    contention miss    the pair WAS predicted, but the pool could not supply the
                       reservation -- the prediction was right and the resource
                       was not there
    starvation         no key available at service time by any route
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
from research.e4_operational import TAG_BITS, T_FAST, T_SLOW, demand_of, hub_sequence, pi_theory

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
REFILL_RATIO = 1.5
REGIMES = {"low": 10.0, "moderate": 2.5, "high": 0.75}
CONFIGS = [(2, 0), (2, 1), (4, 3), (2, 2)]      # pi = .1333 .5667 .8167 1.0
ARM_ORDER = os.environ.get("ARM_ORDER", "random")
TTLS = [1, 2, 4, 8]
PREDICTORS = ["reactive", "carry", "structural"]


def mean_demand(n, m):
    return m * (n - 1) * TAG_BITS


def run(n, m, k, predictor, ttl, capacity_factor, views=500, warm=60, seed=0,
        arm_order="random"):
    rng = np.random.default_rng(seed)
    seq = hub_sequence(n, m, k, views + 2, rng)
    D = mean_demand(n, m)
    cap = capacity_factor * D
    refill = REFILL_RATIO * D
    pool = cap * 0.5

    reserved = {}                 # pair -> [bits, expiry_view, created_view]
    fresh = stale = pred_miss = cont_miss = starved = 0
    reserved_key = consumed = expired = 0.0
    demanded = 0.0
    arm_fail = 0
    occ, lat = [], []
    per_pair_req, per_pair_fast = {}, {}
    prev_demand = {}

    for t in range(views):
        pool = min(cap, pool + refill)
        for p, r in list(reserved.items()):
            if t >= r[1]:
                pool = min(cap, pool + r[0])
                expired += r[0]
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

        wanted = set()
        failed = set()
        arm_list = list(want)
        if arm_order == "random":
            rng.shuffle(arm_list)
        for p in arm_list[:K]:
            wanted.add(p)
            if p in reserved:
                continue
            b = want[p]
            if pool >= b:
                pool -= b
                reserved[p] = [b, t + ttl, t]
                reserved_key += b
            else:
                arm_fail += 1
                failed.add(p)

        if t >= warm:
            occ.append(len(reserved))

        order = list(d)
        rng.shuffle(order)
        worst = 0.0
        for p in order:
            bits = d[p]
            demanded += bits
            per_pair_req[p] = per_pair_req.get(p, 0) + 1
            r = reserved.get(p)
            if r and r[0] >= bits:
                if r[2] == t:
                    fresh += 1
                else:
                    stale += 1
                per_pair_fast[p] = per_pair_fast.get(p, 0) + 1
                r[0] -= bits
                if r[0] <= 1e-9:
                    del reserved[p]
                consumed += bits
                worst = max(worst, T_FAST)
                if t >= warm:
                    lat.append(T_FAST)
            elif pool >= bits:
                pool -= bits
                consumed += bits
                if p in failed:
                    cont_miss += 1
                else:
                    pred_miss += 1
                worst = max(worst, T_SLOW)
                if t >= warm:
                    lat.append(T_SLOW)
            else:
                starved += 1
                worst = max(worst, T_SLOW * 4)
                if t >= warm:
                    lat.append(T_SLOW * 4)

        prev_demand = d

    tot = fresh + stale + pred_miss + cont_miss + starved
    rates = [per_pair_fast.get(p, 0) / v for p, v in per_pair_req.items() if v > 0]
    la = np.array(lat) if lat else np.array([0.0])
    return {
        "fresh": fresh / max(tot, 1), "stale": stale / max(tot, 1),
        "total_hit": (fresh + stale) / max(tot, 1),
        "pred_miss": pred_miss / max(tot, 1),
        "cont_miss": cont_miss / max(tot, 1),
        "starve": starved / max(tot, 1),
        "arm_fail_per_view": arm_fail / views,
        "reserved_key": reserved_key / max(demanded, 1.0),
        "waste": expired / max(demanded, 1.0),
        "key_per_demand": (consumed + expired) / max(demanded, 1.0),
        "peak_occ": float(max(occ)) if occ else 0.0,
        "mean_occ": float(np.mean(occ)) if occ else 0.0,
        "unfairness": (max(rates) - min(rates)) if rates else 0.0,
        "lat_mean_ms": float(la.mean() * 1e3),
        "lat_p99_ms": float(np.percentile(la, 99) * 1e3),
    }


def main():
    n = 16
    SEEDS = list(range(10))
    rows = []
    print("=" * 118)
    print("E6  Shared finite QKD pool")
    print("=" * 118)
    print(f"  n={n}  refill = {REFILL_RATIO} x demand/view (fixed);  "
          f"capacity C x demand, regimes C = "
          + ", ".join(f"{k}:{v}" for k, v in REGIMES.items()))
    print()
    hdr = (f"  {'pi':>7}{'regime':>10}{'TTL':>4}{'pred':>11}{'fresh':>8}{'stale':>8}"
           f"{'total':>8}{'predMiss':>9}{'contMiss':>9}{'starve':>8}{'waste':>8}"
           f"{'peakOcc':>9}{'lat ms':>8}{'unfair':>8}")
    print(hdr)
    for (m, k) in CONFIGS:
        pi = pi_theory(n, m, k)
        for reg, cfac in REGIMES.items():
            for ttl in TTLS:
                for pred in PREDICTORS:
                    rr = [run(n, m, k, pred, ttl, cfac, seed=s,
                              arm_order=ARM_ORDER) for s in SEEDS]
                    agg = {key: statistics.mean([x[key] for x in rr]) for key in rr[0]}
                    agg.update(pi=pi, m=m, k=k, regime=reg, capacity=cfac, ttl=ttl,
                               predictor=pred,
                               ci95_fresh=(1.96 * statistics.stdev(
                                   [x["fresh"] for x in rr]) / math.sqrt(len(rr))
                                   if len(rr) > 1 else 0.0))
                    rows.append(agg)
                    if pred == "carry":
                        print(f"  {pi:>7.4f}{reg:>10}{ttl:>4}{pred:>11}"
                              f"{agg['fresh']:>8.4f}{agg['stale']:>8.4f}"
                              f"{agg['total_hit']:>8.4f}{agg['pred_miss']:>9.4f}"
                              f"{agg['cont_miss']:>9.4f}{agg['starve']:>8.4f}"
                              f"{agg['waste']:>8.4f}{agg['peak_occ']:>9.0f}"
                              f"{agg['lat_mean_ms']:>8.4f}{agg['unfairness']:>8.4f}")
            print()

    carry = [r for r in rows if r["predictor"] == "carry"]
    print("=" * 118)
    print("CEILING TEST: fresh-hit rate vs pi, under shared-pool contention")
    print("=" * 118)
    print(f"  {'regime':>10}{'TTL':>5}{'max(fresh - pi)':>18}{'violations':>13}")
    for reg in REGIMES:
        for ttl in TTLS:
            g = [r for r in carry if r["regime"] == reg and r["ttl"] == ttl]
            df = [r["fresh"] - r["pi"] for r in g]
            print(f"  {reg:>10}{ttl:>5}{max(df):>+18.4f}"
                  f"{sum(1 for x in df if x > 1e-3):>13}")
    allf = [r["fresh"] - r["pi"] for r in carry]
    print(f"\n  overall max(fresh - pi) = {max(allf):+.4f} over {len(carry)} cells")

    rec = {"experiment_id": "E6-sharedpool-001",
           "utc": datetime.now(timezone.utc).isoformat(),
           "n": n, "refill_ratio": REFILL_RATIO, "regimes": REGIMES,
           "arm_order": ARM_ORDER,
           "ttls": TTLS, "seeds": len(SEEDS), "rows": rows}
    os.makedirs(RESULTS, exist_ok=True)
    json.dump(rec, open(os.path.join(RESULTS, f"E6-sharedpool-{ARM_ORDER}.json"), "w"),
              indent=2)
    print(f"\nwrote {RESULTS}/E6-sharedpool-{ARM_ORDER}.json")


if __name__ == "__main__":
    main()
