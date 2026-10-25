#!/usr/bin/env python3
# Post hoc, not pre-specified. Three things the pool-depth table leaves out, on the same 66 held-out Aptos epochs:
#  blocks   key reaches a pair once per period of P views and tops the pool up to its depth (periodic review)
#  ring     the relay time of a pair is its ring distance in hops times a per-hop delay, so pools differ by pair
#  timeouts a timeout round puts two tags on every pair; how many consecutive rounds a depth absorbs
# Self-checks: the ring run with equal delays reproduces stock_levels.fill; a one-view period with depth 4 serves all.
# usage: stock_refill.py [out.json]
import glob
import json
import math
import os
import sys
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import stock_levels as sl

V = json.load(open(os.path.join(os.path.dirname(HERE), "qkd", "QKD_FEASIBILITY.json")))["observed_view_rates"]["aptos_rounds_per_s"]["mean"]
PERIODS_S = (10, 30, 60, 90)
PHASES = 16
HOP_VIEWS = (1, 2, 5)
QS = (0.99, 0.998, 0.9999)
TARGETS = (0.99, 0.999)
ZMAX = 400


def period_demand(L, n, P, rng):
    # demand of every pair in every period of P views, for PHASES random phases; rows = (phase, period, u, v)
    a = sl.incidence(L, n)
    T = a.shape[0]
    cum = np.vstack([np.zeros((1, n), np.int64), np.cumsum(a, 0)])
    up = np.triu_indices(n, 1)
    out = []
    for _ in range(PHASES):
        phase = int(rng.integers(0, P))
        bounds = list(range(phase, T + 1, P))
        for s, e in zip(bounds[:-1], bounds[1:]):       # complete periods only
            w = cum[e] - cum[s]
            D = w[:, None] + w[None, :]
            out.append(D[up])
    return np.concatenate(out) if out else np.zeros(0, np.int64)


def least_depth(D, targets):
    total = D.sum()
    need = {}
    for z in range(1, ZMAX + 1):
        f = np.minimum(D, z).sum() / total
        for t in targets:
            if t not in need and f >= t:
                need[t] = (z, float(f))
        if len(need) == len(targets):
            break
    return need


def ring_distance(n):
    i = np.arange(n)
    d = np.abs(i[:, None] - i[None, :])
    return np.minimum(d, n - d)


def fill_pairs(L, n, B, D):
    # tags served on time and demanded when pair (u, v) gets its key back D[u, v] views after use
    L = np.asarray(L)
    a = sl.incidence(L, n)
    T = a.shape[0]
    i = np.arange(T)
    cum = np.vstack([np.zeros((1, n), np.int64), np.cumsum(a, 0)])
    cols = np.arange(n)
    b = L[:-1]
    c = L[1:]
    served = 0
    total = 0
    for hub, other in ((b, None), (c, b)):
        d = a[i, hub][:, None] + a
        back = np.maximum(i[:, None] - D[hub], 0)
        W = (cum[i, hub][:, None] - cum[back, hub[:, None]]) + (cum[i][:, cols] - cum[back, cols[None, :]])
        onhand = B[hub] - W
        m = np.ones((T, n), bool)
        m[i, hub] = False
        if other is not None:
            m[i, other] = False
            m[hub == other] = False
        served += int(np.minimum(d, np.maximum(onhand, 0))[m].sum())
        total += int(d[m].sum())
    return served, total


def depth_for_pair(pp, delta, q):
    # q-quantile of Bin(2, pp) + 2 Bin(delta, pp)
    if pp <= 0:
        return 0
    ks = np.arange(delta + 1)
    logc = np.array([math.lgamma(delta + 1) - math.lgamma(k + 1) - math.lgamma(delta - k + 1) for k in ks])
    if pp < 1:
        mid = np.exp(logc + ks * math.log(pp) + (delta - ks) * math.log1p(-pp))
    else:
        mid = (ks == delta).astype(float)
    ends = np.array([(1 - pp) ** 2, 2 * pp * (1 - pp), pp ** 2])
    pmf = np.zeros(2 * delta + 3)
    for k, w in enumerate(mid):
        pmf[2 * k:2 * k + 3] += w * ends
    return int(np.searchsorted(np.cumsum(pmf), q - 1e-12))


def ring_depths(s, D, q):
    n = len(s)
    B = np.zeros((n, n), np.int64)
    for u in range(n):
        for v in range(u + 1, n):
            B[u, v] = B[v, u] = depth_for_pair(min(s[u] + s[v], 1.0), int(D[u, v]), q)
    return B


def one_epoch(f):
    n, s, L = sl.load(f)
    name = os.path.basename(f)
    rng = np.random.default_rng([20261011, int(name[6:11])])
    pairs = n * (n - 1) // 2
    rows = {"epoch": name, "n": n, "blocks": {}, "ring": {}}
    for T_s in PERIODS_S:
        P = int(round(V * T_s))
        D = period_demand(L, n, P, rng)
        rows["blocks"][str(T_s)] = {"P": P, "demand": D, "mean_per_period": float(D.mean()) if len(D) else None}
    dist = ring_distance(n)
    for h in HOP_VIEWS:
        Dp = dist * h
        r = {"max_delta": int(Dp.max()), "uniform": {}, "bydist": {}}
        for z in range(1, 41):
            r["uniform"][z] = fill_pairs(L, n, np.full((n, n), z, np.int64), Dp)
        for q in QS:
            B = ring_depths(s, Dp, q)
            r["bydist"][q] = (fill_pairs(L, n, B, Dp), float(B[np.triu_indices(n, 1)].mean()))
        rows["ring"][str(h)] = r
    return rows


def selfcheck():
    rng = np.random.default_rng(3)
    n = 9
    s = rng.dirichlet(np.ones(n))
    L = rng.choice(n, size=400, p=s)
    for delta in (1, 3, 7):
        B = sl.stake_levels(s, delta, 0.95)
        assert fill_pairs(L, n, B, np.full((n, n), delta)) == sl.fill(L, n, B, delta)
        assert (ring_depths(s, np.full((n, n), delta), 0.95) == B).all()
    Lr = np.arange(300) % 7
    D = period_demand(Lr, 7, 7, rng)
    assert D.min() == 4 and D.max() == 4
    assert period_demand(Lr, 7, 1, rng).max() == 2
    assert len(period_demand(Lr, 7, 1000, rng)) == 0
    assert fill_pairs(Lr, 7, np.full((7, 7), 4), ring_distance(7) * 2) == fill_pairs(Lr, 7, np.full((7, 7), 4), np.full((7, 7), 6))


if __name__ == "__main__":
    selfcheck()
    files = sl.epochs("heldout")
    with Pool(10) as pool:
        rows = pool.map(one_epoch, files)
    out = {"note": "post hoc; 66 held-out epochs; views per second as in QKD_FEASIBILITY.json", "views_per_s": V,
           "epochs": len(rows), "blocks": {}, "ring": {}, "timeouts": {}}
    n = rows[0]["n"]
    for T_s in PERIODS_S:
        D = np.concatenate([r["blocks"][str(T_s)]["demand"] for r in rows if len(r["blocks"][str(T_s)]["demand"])])
        n_epochs = sum(1 for r in rows if len(r["blocks"][str(T_s)]["demand"]))
        P = rows[0]["blocks"][str(T_s)]["P"]
        need = least_depth(D, TARGETS)
        out["blocks"][str(T_s)] = {"period_views": P, "epochs_with_a_complete_period": n_epochs, "mean_tags_per_pair_per_period": float(D.mean()),
                                   "formula_4vT_over_n": 4 * V * T_s / n, "p99_demand": float(np.quantile(D, 0.99)),
                                   "need": {str(t): {"depth": z, "fill": f} for t, (z, f) in need.items()}}
        print(f"block refill every {T_s:3d} s = {P:5d} views ({n_epochs} epochs with a complete period): mean demand {D.mean():6.1f} tags/pair/period (4vT/n = {4 * V * T_s / n:6.1f}); "
              + "; ".join(f"{t}: depth {z} ({f:.4f})" for t, (z, f) in need.items()))
    for h in HOP_VIEWS:
        tot = {z: [0, 0] for z in range(1, 41)}
        bd = {q: [0, 0, []] for q in QS}
        for r in rows:
            rr = r["ring"][str(h)]
            for z, (sv, tt) in rr["uniform"].items():
                tot[z][0] += sv
                tot[z][1] += tt
            for q, ((sv, tt), mean_depth) in rr["bydist"].items():
                bd[q][0] += sv
                bd[q][1] += tt
                bd[q][2].append(mean_depth)
        res = {"max_delta_views": max(r["ring"][str(h)]["max_delta"] for r in rows), "uniform": {}, "bydist": {}}
        for z, (sv, tt) in tot.items():
            res["uniform"][str(z)] = sv / tt
        for q, (sv, tt, md) in bd.items():
            res["bydist"][str(q)] = {"fill": sv / tt, "mean_depth": float(np.mean(md))}
        res["need"] = {}
        for t in TARGETS:
            zu = next((z for z in range(1, 41) if res["uniform"][str(z)] >= t), None)
            qd = next((q for q in QS if res["bydist"][str(q)]["fill"] >= t), None)
            res["need"][str(t)] = {"uniform": zu, "bydist_q": qd, "bydist_mean_depth": res["bydist"][str(qd)]["mean_depth"] if qd else None}
        out["ring"][str(h)] = res
        print(f"ring, {h} view(s) per hop, farthest pair {res['max_delta_views']} views: " + "; ".join(
            f"{t}: uniform {res['need'][str(t)]['uniform']} / by distance {res['need'][str(t)]['bydist_mean_depth']}" for t in TARGETS))
    for z in (3, 4, 6, 8, 12, 16):
        out["timeouts"][str(z)] = z // 2
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "REFILL_RESULTS.json"), "w"), indent=1)
