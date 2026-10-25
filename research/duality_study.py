#!/usr/bin/env python3
"""H1 and H2: does communication complexity set both predictability and leakage?

H1  Predictability-Complexity Duality. A protocol's support persistence pi -- and
    with it the ceiling on any carry-forward forecaster -- is fixed by its
    steady-state message complexity, not by tuning.

H2  Gain-Leak Duality. The advantage a structural forecaster holds over a
    statistical one, and the leader information an observer recovers from the
    pre-armed set, are the same quantity measured twice.

Round-robin protocols have period n, so the EWMA steady state is computed in
closed form rather than sampled: exact, and fast enough to reach n = 128.
Sortition has no period and is sampled.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import itertools
import numpy as np

from research.protocols import (PROTOCOLS, AlgorandCommittee, Protocol,
                                coverage_at, leakage, support_persistence)


def demand_matrix(proto: Protocol, period: int):
    """(period x n_pairs) demand matrix and the pair index."""
    pairs = list(itertools.combinations(range(proto.n), 2))
    idx = {p: k for k, p in enumerate(pairs)}
    D = np.zeros((period, len(pairs)))
    for t in range(period):
        for p, b in proto.demand(t).items():
            D[t, idx[p]] += b
    return D, pairs


def ewma_steady(D, alpha):
    """Exact periodic steady state of dhat(t+1) = a d(t) + (1-a) dhat(t)."""
    n, q = D.shape[0], 1.0 - alpha
    acc = np.zeros(D.shape[1])
    for k in range(n):
        acc += q ** (n - 1 - k) * D[k]
    x = alpha * acc / (1.0 - q ** n)
    out = np.zeros_like(D)
    for t in range(n):
        out[t] = x
        x = alpha * D[t] + q * x
    return out


def cov_matrix(D, P, K):
    """Mean coverage of each row of D by the top-K entries of the matching P."""
    out = []
    for t in range(D.shape[0]):
        tot = D[t].sum()
        if tot <= 0:
            continue
        top = np.argpartition(-P[t], min(K, P.shape[1] - 1))[:K]
        out.append(D[t][top].sum() / tot)
    return float(np.mean(out))


def persistence_matrix(D):
    out = []
    for t in range(D.shape[0]):
        tot = D[t].sum()
        if tot <= 0:
            continue
        prev = D[(t - 1) % D.shape[0]] > 0
        out.append(D[t][prev].sum() / tot)
    return float(np.mean(out))


def leak_matrix(D, pairs, n, leaders):
    """Top-1 leader recovery and MI from the support of each row."""
    hits, counts = 0, np.zeros((n, n))
    T = D.shape[0]
    for t in range(T):
        ld = leaders[t]
        if ld is None:
            continue
        deg = np.zeros(n)
        sup = np.nonzero(D[t])[0]
        for k in sup:
            a, b = pairs[k]
            deg[a] += 1
            deg[b] += 1
        g = int(np.argmax(deg))
        counts[g, ld] += 1
        hits += int(g == ld)
    tot = counts.sum()
    if tot == 0:
        return {"top1": 1.0 / n, "mi_bits": 0.0, "advantage": 0.0}
    p = counts / tot
    px, py = p.sum(1, keepdims=True), p.sum(0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        term = p * np.log2(p / (px * py))
    mi = float(np.nansum(np.where(p > 0, term, 0.0)))
    acc = hits / tot
    base = 1.0 / n
    return {"top1": acc, "mi_bits": mi,
            "advantage": (acc - base) / max(1 - base, 1e-9)}


ALPHAS = (0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9)


def study(P, n, seed=0):
    proto = P(n, seed=seed)
    if isinstance(proto, AlgorandCommittee):
        pi = support_persistence(proto, views=200)
        supports = [len([1 for b in proto.demand(t).values() if b > 0])
                    for t in range(20, 220)]
        K = int(np.ceil(np.mean(supports)))
        from research.protocols import evaluate
        ev = evaluate(proto)
        lk = leakage(proto)
        return {"pi": pi, "K": K, "ewma": ev["ewma"], "alpha": ev["alpha"],
                "structural": ev["structural"], "gain": ev["gain"], **lk}

    D, pairs = demand_matrix(proto, n)
    K = int(np.ceil(np.mean([(D[t] > 0).sum() for t in range(n)])))
    pi = persistence_matrix(D)
    best, ba = -1.0, None
    for a in ALPHAS:
        c = cov_matrix(D, ewma_steady(D, a), K)
        if c > best:
            best, ba = c, a
    struct = cov_matrix(D, D, K)          # knows the schedule exactly
    leaders = [proto.leader(t) for t in range(n)]
    lk = leak_matrix(D, pairs, n, leaders)
    return {"pi": pi, "K": K, "ewma": best, "alpha": ba,
            "structural": struct, "gain": struct - best, **lk}


def main():
    NS = [4, 7, 16, 31, 64, 128]
    rows = []
    print(f"{'protocol':<20}{'class':<22}{'n':>5}{'pi':>8}{'ewma':>8}"
          f"{'struct':>8}{'gain':>8}{'leak top1':>11}{'MI bits':>9}")
    for P in PROTOCOLS:
        for n in NS:
            if n < 4:
                continue
            r = study(P, n)
            r.update(protocol=P(n).name, complexity=P(n).complexity, n=n)
            rows.append(r)
            print(f"{r['protocol']:<20}{r['complexity']:<22}{n:>5}{r['pi']:>8.4f}"
                  f"{r['ewma']:>8.4f}{r['structural']:>8.4f}{r['gain']:>8.4f}"
                  f"{r['top1']:>11.4f}{r['mi_bits']:>9.4f}", flush=True)
        print()

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "results", "duality.json")
    with open(out, "w") as f:
        json.dump(rows, f, indent=2)

    # ---- H1 test -------------------------------------------------------
    print("=" * 78)
    print("H1: pi is determined by message-complexity class")
    print("=" * 78)
    by_class = {}
    for r in rows:
        by_class.setdefault(r["complexity"], []).append(r["pi"])
    for c, vs in by_class.items():
        print(f"  {c:<24} pi = {np.mean(vs):.4f} +/- {np.std(vs):.4f}  "
              f"(n from {min(NS)} to {max(NS)}, {len(vs)} points)")
    spreads = [np.std(v) for v in by_class.values()]
    print(f"\n  within-class spread max = {max(spreads):.4f}; "
          f"between-class range = {max(np.mean(v) for v in by_class.values()) - min(np.mean(v) for v in by_class.values()):.4f}")

    # ---- H2 test -------------------------------------------------------
    print()
    print("=" * 78)
    print("H2: structural gain and leader leakage are the same quantity")
    print("=" * 78)
    g = np.array([r["gain"] for r in rows])
    a = np.array([r["advantage"] for r in rows])
    m = np.array([r["mi_bits"] for r in rows])
    print(f"  corr(gain, leak advantage) = {np.corrcoef(g, a)[0,1]:+.4f}")
    print(f"  corr(gain, MI bits)        = {np.corrcoef(g, m)[0,1]:+.4f}")
    zero_gain = [r for r in rows if r["gain"] < 0.01]
    big_gain = [r for r in rows if r["gain"] > 0.2]
    print(f"\n  where structural gains nothing (gain<0.01, {len(zero_gain)} pts): "
          f"mean leak advantage = {np.mean([r['advantage'] for r in zero_gain]):.4f}")
    print(f"  where it gains a lot  (gain>0.20, {len(big_gain)} pts): "
          f"mean leak advantage = {np.mean([r['advantage'] for r in big_gain]):.4f}")


if __name__ == "__main__":
    main()
