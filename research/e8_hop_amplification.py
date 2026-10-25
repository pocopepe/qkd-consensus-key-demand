#!/usr/bin/env python3
"""E8 -- does multi-hop reservation amplification explain the E1/E6 discrepancy?

E7 ruled out burstiness. The remaining candidate, read from E1's source, is the
reservation accounting model:

    E1     an h-hop reservation withdraws B on EVERY relay link -> h*B locked,
           and it blocks h SPECIFIC links that other paths may cross.
    E6/E7  a reservation withdraws B from one fungible pool.

Three resource models are run so the two halves of that difference -- footprint
size and link specificity -- can be separated:

  MODEL A/B  one fungible pool; a reservation locks amp * B, amp in {1,2,4,8}.
             amp = 1 is exactly the E6/E7 model and serves as the regression
             control. This is an ABSTRACT AMPLIFICATION FACTOR: it reproduces
             E1's footprint arithmetic but NOT its topology. A reservation
             consumes more of the aggregate pool but still blocks nobody in
             particular.

  MODEL C    E1's ACTUAL relay topology and reservation mechanism, imported
             unchanged from qkdnet/topology.py (ring_with_chords, per-link
             pools, reserve/release/consume over path_links). Here h is not
             chosen -- it is whatever the topology gives, measured at
             mean 2.30 hops over 39 links for n = 16. This arm tests the
             mechanism as E1 actually implements it.

CAPACITY NORMALISATION. Model B has one pool of C*D. Model C is given the same
AGGREGATE capacity spread over its L links, C*D/L each, and the same aggregate
refill 1.5*D/L each. A reservation of B bits on an h-hop path therefore removes
h*B from the same total budget in both models; what differs is that Model C
requires the capacity to be present on h SPECIFIC links.
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
from qkdnet.topology import ring_with_chords
from simulator.engine import BurstyWorkload

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
REFILL_RATIO = 1.5
CAPS = {"scarce": 0.75, "moderate": 2.5}
CONFIGS = [(2, 0), (2, 1), (4, 3), (2, 2)]
TTLS = [1, 2, 4, 8]
AMPS = [1, 2, 4, 8]
BURST_MEAN = 1.4336


def mean_demand(n, m):
    return m * (n - 1) * TAG_BITS


def run_pool(n, m, k, predictor, ttl, cfac, amp, workload,
             views=600, warm=80, seed=0):
    """Model A/B: one fungible pool, reservation footprint = amp * bits."""
    rng = np.random.default_rng(seed)
    seq = hub_sequence(n, m, k, views + 2, rng)
    D = mean_demand(n, m)
    cap, refill = cfac * D, REFILL_RATIO * D
    pool = cap * 0.5
    bw = BurstyWorkload(n=n) if workload == "bursty" else None

    reserved = {}          # pair -> [bits_left, expiry, created, locked]
    fresh = stale = pmiss = cmiss = starved = 0
    consumed = expired = demanded = 0.0
    arm_fail = 0
    occ, foot, lat = [], [], []
    per_req, per_fast = {}, {}
    prev = {}

    for t in range(views):
        mult = 1.0 if bw is None else bw.step(rng)[0]
        pool = min(cap, pool + refill)
        for p, r in list(reserved.items()):
            if t >= r[1]:
                pool = min(cap, pool + r[3])
                expired += r[0] * amp
                del reserved[p]

        base = demand_of(n, seq[t])
        d = {p: b * mult for p, b in base.items()}
        K = len(d)
        want = dict(d) if predictor == "structural" else dict(prev)
        al = list(want); rng.shuffle(al)
        failed = set()
        for p in al[:K]:
            if p in reserved:
                continue
            b = want[p]; lock = amp * b
            if pool >= lock:
                pool -= lock
                reserved[p] = [b, t + ttl, t, lock]
            else:
                arm_fail += 1; failed.add(p)

        if t >= warm:
            occ.append(len(reserved))
            foot.append(sum(r[3] for r in reserved.values()))

        order = list(d); rng.shuffle(order)
        for p in order:
            bits = d[p]; demanded += bits
            per_req[p] = per_req.get(p, 0) + 1
            r = reserved.get(p)
            if r and r[0] >= bits:
                if r[2] == t: fresh += 1
                else: stale += 1
                per_fast[p] = per_fast.get(p, 0) + 1
                frac = bits / r[0] if r[0] > 0 else 1.0
                rel = r[3] * frac
                r[0] -= bits; r[3] -= rel
                if r[0] <= 1e-9: del reserved[p]
                consumed += bits * amp
                if t >= warm: lat.append(T_FAST)
            elif pool >= bits * amp:
                pool -= bits * amp
                consumed += bits * amp
                if p in failed: cmiss += 1
                else: pmiss += 1
                if t >= warm: lat.append(T_SLOW)
            else:
                starved += 1
                if t >= warm: lat.append(T_SLOW * 4)
        prev = d
    return _summarise(fresh, stale, pmiss, cmiss, starved, consumed, expired,
                      demanded, arm_fail, occ, foot, lat, per_req, per_fast,
                      views, amp)


def run_topo(n, m, k, predictor, ttl, cfac, workload,
             views=600, warm=80, seed=0):
    """Model C: E1's real relay topology and multi-hop reservation mechanism."""
    rng = np.random.default_rng(seed)
    net = ring_with_chords(n, seed=3)
    L = len(net.links)
    D = mean_demand(n, m)
    per_link_cap = cfac * D / L
    per_link_refill = REFILL_RATIO * D / L
    for lk in net.links.values():
        lk.capacity_bits = per_link_cap
        lk.stored_bits = per_link_cap * 0.5
        lk.reserved_bits = 0.0
        lk.rate_bps = per_link_refill          # replenish(1.0) adds one view

    seq = hub_sequence(n, m, k, views + 2, rng)
    bw = BurstyWorkload(n=n) if workload == "bursty" else None
    reserved = {}
    fresh = stale = pmiss = cmiss = starved = 0
    consumed = expired = demanded = 0.0
    arm_fail = 0
    occ, foot, lat = [], [], []
    per_req, per_fast = {}, {}
    prev = {}
    hops_used = []

    for t in range(views):
        mult = 1.0 if bw is None else bw.step(rng)[0]
        net.replenish(1.0)
        for p, r in list(reserved.items()):
            if t >= r[1]:
                net.release(p[0], p[1], r[0])
                expired += r[0] * net.hops(p[0], p[1])
                del reserved[p]

        base = demand_of(n, seq[t])
        d = {p: b * mult for p, b in base.items()}
        K = len(d)
        want = dict(d) if predictor == "structural" else dict(prev)
        al = list(want); rng.shuffle(al)
        failed = set()
        for p in al[:K]:
            if p in reserved:
                continue
            b = want[p]
            if net.reserve(p[0], p[1], b):
                reserved[p] = [b, t + ttl, t]
                hops_used.append(net.hops(p[0], p[1]))
            else:
                arm_fail += 1; failed.add(p)

        if t >= warm:
            occ.append(len(reserved))
            foot.append(sum(lk.reserved_bits for lk in net.links.values()))

        order = list(d); rng.shuffle(order)
        for p in order:
            bits = d[p]; demanded += bits
            per_req[p] = per_req.get(p, 0) + 1
            h = net.hops(p[0], p[1])
            r = reserved.get(p)
            if r and r[0] >= bits:
                if r[2] == t: fresh += 1
                else: stale += 1
                per_fast[p] = per_fast.get(p, 0) + 1
                net.consume(p[0], p[1], bits, from_reservation=True)
                r[0] -= bits
                if r[0] <= 1e-9: del reserved[p]
                consumed += bits * h
                if t >= warm: lat.append(T_FAST)
            elif net.consume(p[0], p[1], bits, from_reservation=False):
                consumed += bits * h
                if p in failed: cmiss += 1
                else: pmiss += 1
                if t >= warm: lat.append(T_SLOW)
            else:
                starved += 1
                if t >= warm: lat.append(T_SLOW * 4)
        prev = d
    out = _summarise(fresh, stale, pmiss, cmiss, starved, consumed, expired,
                     demanded, arm_fail, occ, foot, lat, per_req, per_fast,
                     views, 1)
    out["mean_hops"] = float(np.mean(hops_used)) if hops_used else 0.0
    return out


def _summarise(fresh, stale, pmiss, cmiss, starved, consumed, expired,
               demanded, arm_fail, occ, foot, lat, per_req, per_fast, views, amp):
    tot = fresh + stale + pmiss + cmiss + starved
    rates = [per_fast.get(p, 0) / v for p, v in per_req.items() if v > 0]
    la = np.array(lat) if lat else np.array([0.0])
    return {"fresh": fresh / max(tot, 1), "stale": stale / max(tot, 1),
            "total_hit": (fresh + stale) / max(tot, 1),
            "pred_miss": pmiss / max(tot, 1), "cont_miss": cmiss / max(tot, 1),
            "starve": starved / max(tot, 1),
            "arm_fail_per_view": arm_fail / views,
            "waste": expired / max(demanded, 1.0),
            "key_per_demand": (consumed + expired) / max(demanded, 1.0),
            "peak_occ": float(max(occ)) if occ else 0.0,
            "mean_occ": float(np.mean(occ)) if occ else 0.0,
            "peak_footprint": float(max(foot)) if foot else 0.0,
            "mean_footprint": float(np.mean(foot)) if foot else 0.0,
            "unfairness": (max(rates) - min(rates)) if rates else 0.0,
            "lat_mean_ms": float(la.mean() * 1e3),
            "lat_p95_ms": float(np.percentile(la, 95) * 1e3)}


def main():
    n = 16
    SEEDS = list(range(10))
    rows = []
    print("=" * 120)
    print("E8  Multi-hop reservation amplification")
    print("=" * 120)
    print("  Model A/B: one fungible pool, footprint = amp x bits (ABSTRACT factor,")
    print("             not a topology).  amp=1 is the E6/E7 regression control.")
    print("  Model C  : E1's real ring+chords topology and multi-hop reserve(),")
    print("             39 links, mean 2.30 hops, same AGGREGATE capacity/refill.\n")

    for wl in ("stationary", "bursty"):
        for capname, cfac in CAPS.items():
            print(f"  --- workload={wl}  capacity={capname} (C={cfac}D) ---")
            print(f"  {'model':>10}{'amp':>5}{'TTL':>5}{'fresh':>8}{'starve':>8}"
                  f"{'waste':>8}{'lat ms':>9}{'peakOcc':>9}{'peakFoot/D':>12}"
                  f"{'armFail':>9}{'unfair':>8}")
            for amp in AMPS:
                for ttl in TTLS:
                    accum = []
                    for (m, k) in CONFIGS:
                        rr = [run_pool(n, m, k, "carry", ttl, cfac, amp, wl, seed=s)
                              for s in SEEDS]
                        agg = {key: statistics.mean([x[key] for x in rr]) for key in rr[0]}
                        agg.update(model="pool", amp=amp, ttl=ttl, workload=wl,
                                   capacity=capname, pi=pi_theory(n, m, k),
                                   m=m, k=k, predictor="carry",
                                   D=mean_demand(n, m))
                        rows.append(agg); accum.append(agg)
                    a = {key: statistics.mean([x[key] for x in accum])
                         for key in ("fresh", "starve", "waste", "lat_mean_ms",
                                     "peak_occ", "peak_footprint", "arm_fail_per_view",
                                     "unfairness", "D")}
                    print(f"  {'pool':>10}{amp:>5}{ttl:>5}{a['fresh']:>8.4f}"
                          f"{a['starve']:>8.4f}{a['waste']:>8.4f}"
                          f"{a['lat_mean_ms']:>9.4f}{a['peak_occ']:>9.0f}"
                          f"{a['peak_footprint']/a['D']:>12.2f}"
                          f"{a['arm_fail_per_view']:>9.2f}{a['unfairness']:>8.4f}")
            # Model C
            for ttl in TTLS:
                accum = []
                for (m, k) in CONFIGS:
                    rr = [run_topo(n, m, k, "carry", ttl, cfac, wl, seed=s)
                          for s in SEEDS]
                    agg = {key: statistics.mean([x[key] for x in rr]) for key in rr[0]}
                    agg.update(model="topo", amp=None, ttl=ttl, workload=wl,
                               capacity=capname, pi=pi_theory(n, m, k),
                               m=m, k=k, predictor="carry", D=mean_demand(n, m))
                    rows.append(agg); accum.append(agg)
                a = {key: statistics.mean([x[key] for x in accum])
                     for key in ("fresh", "starve", "waste", "lat_mean_ms",
                                 "peak_occ", "peak_footprint", "arm_fail_per_view",
                                 "unfairness", "D", "mean_hops")}
                print(f"  {'topo(E1)':>10}{a['mean_hops']:>5.1f}{ttl:>5}"
                      f"{a['fresh']:>8.4f}{a['starve']:>8.4f}{a['waste']:>8.4f}"
                      f"{a['lat_mean_ms']:>9.4f}{a['peak_occ']:>9.0f}"
                      f"{a['peak_footprint']/a['D']:>12.2f}"
                      f"{a['arm_fail_per_view']:>9.2f}{a['unfairness']:>8.4f}")
            print()

    rec = {"experiment_id": "E8-hopamp-001",
           "utc": datetime.now(timezone.utc).isoformat(),
           "n": n, "refill_ratio": REFILL_RATIO, "caps": CAPS, "amps": AMPS,
           "ttls": TTLS, "seeds": len(SEEDS), "rows": rows}
    os.makedirs(RESULTS, exist_ok=True)
    json.dump(rec, open(os.path.join(RESULTS, "E8-hopamp-001.json"), "w"), indent=2)
    print(f"wrote {RESULTS}/E8-hopamp-001.json")


if __name__ == "__main__":
    main()
