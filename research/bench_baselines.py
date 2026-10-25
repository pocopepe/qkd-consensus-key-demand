#!/usr/bin/env python3
"""Structural+quorum against the published DT-VQKP scheme, like for like."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

from qkdnet.allocate import (DensityGreedyPolicy, QuorumCoveragePolicy,
                             UtilityModel, build_candidates)
from qkdnet.consensus import BFTConsensus, ConsensusConfig
from qkdnet.forecast import EWMAPairForecaster, StructuralForecaster
from qkdnet.kernel import KernelBudget, XDPMap
from qkdnet.topology import ring_with_chords
from research.baselines import DTVQKP, StaticThresholdVQKP

T_FAST, T_KME, T_HOP = 14.2e-6, 1.042e-3, 1.5e-3   # KME now measured, pooled mTLS


def run(kind, n=16, views=500, warm=25, M=192, U=48, seed=3):
    net = ring_with_chords(n, seed=seed)
    ccfg = ConsensusConfig(n=n, seed=seed, byzantine=(3, 11), timeout_prob=0.03)
    cons = BFTConsensus(ccfg)
    budget = KernelBudget(max_entries=M, max_updates_per_round=U)
    kmap = XDPMap(budget, net=net)
    um = UtilityModel(lambda_bit=(T_KME - T_FAST) / 256.0)

    if kind == "structural+quorum":
        fc, pol = StructuralForecaster(cons), QuorumCoveragePolicy()
    elif kind == "ewma+greedy":
        fc, pol = EWMAPairForecaster(0.3), DensityGreedyPolicy()
    elif kind == "DT-VQKP":
        fc, pol = EWMAPairForecaster(0.3), DTVQKP()
    elif kind == "static VQKP":
        fc, pol = EWMAPairForecaster(0.3), StaticThresholdVQKP()
    else:
        fc, pol = None, None

    lat, hits, miss, dem = [], 0, 0, 0
    armed = []
    for v in range(views):
        net.replenish(ccfg.view_period_s)
        kmap.expire(v)
        if pol is not None:
            groups = fc.groups(v) if isinstance(fc, StructuralForecaster) else None
            cands = build_candidates(fc.predict(v), net, um)
            resident = {p: e.bits for p, e in kmap.entries.items()}
            try:
                plan = pol.select(cands, budget, resident, net, groups=groups)
            except TypeError:
                plan = pol.select(cands, budget, resident, net)
            inst = {}
            for p, b in plan.items():
                if p in resident and abs(resident[p] - b) < 1e-9:
                    inst[p] = b
                elif net.reserve(p[0], p[1], b):
                    inst[p] = b
            res = kmap.commit(inst, v, ttl_views=1)
            armed.append(res["installed"])
        out = cons.step()
        pair_lat = {}
        for pair, bits in out.demand.items():
            dem += 1
            h = net.hops(*pair)
            if kmap.lookup(pair, bits, v):
                net.consume(pair[0], pair[1], bits, True); hits += 1
                pair_lat[pair] = T_FAST
            else:
                miss += 1
                net.consume(pair[0], pair[1], bits, False)
                pair_lat[pair] = T_KME + h * T_HOP
        worst = 0.0
        for blk in out.blocks:
            ls = sorted(pair_lat.get(p, T_KME) for p in blk.pairs)
            if ls:
                worst = max(worst, ls[min(max(blk.quorum, 1), len(ls)) - 1])
        if v >= warm:
            lat.append(worst)
        if hasattr(pol, "observe"):
            pol.observe(out.demand)
        if fc is not None:
            fc.observe(v, out.demand, {"leader": out.leader,
                                       "view_change": out.phase.value == "view_change"})
    a = np.array(lat)
    return {"hit_rate": hits / max(dem, 1),
            "p50_ms": float(np.percentile(a, 50) * 1e3),
            "p99_ms": float(np.percentile(a, 99) * 1e3),
            "armed": float(np.mean(armed)) if armed else 0.0}


def main():
    cases = ["reactive", "static VQKP", "DT-VQKP", "ewma+greedy", "structural+quorum"]
    print(f"KME slow path = {T_KME*1e3:.3f} ms (measured, pooled mTLS), "
          f"fast path = {T_FAST*1e6:.1f} us (measured, in kernel)\n")
    print(f"{'scheme':<24}{'hit':>8}{'p50 ms':>10}{'p99 ms':>10}{'armed':>8}"
          f"{'speedup p50':>13}")
    base = None
    rows = []
    for c in cases:
        r = run(c)
        if base is None:
            base = r["p50_ms"]
        r["scheme"] = c
        r["speedup"] = base / r["p50_ms"]
        rows.append(r)
        print(f"{c:<24}{r['hit_rate']:>8.3f}{r['p50_ms']:>10.4f}{r['p99_ms']:>10.3f}"
              f"{r['armed']:>8.0f}{r['speedup']:>13.1f}x")
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "results", "baselines.json")
    json.dump(rows, open(out, "w"), indent=2)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
