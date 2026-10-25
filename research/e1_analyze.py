#!/usr/bin/env python3
"""E1 Phases 3-5: per-view demand graphs, hub-union fit, theory vs measurement.

Follows research/e1_trace_model.md exactly. Nothing here is fitted: m is the
minimum vertex cover of the observed support, k is the overlap of consecutive
covers under a tie-break that cannot see the previous view, and pi_theory is
evaluated at the measured n, m, k.
"""
from __future__ import annotations

import itertools
import json
import os
import statistics
import sys
from collections import defaultdict

D_CORE = {"Proposal", "Vote"}
D_ALL = {"NewRoundStep", "NewValidBlock", "Proposal", "ProposalPOL",
         "BlockPart", "Vote", "HasVote", "VoteSetMaj23", "VoteSetBits"}


def build_views(records, types):
    """(height, round) -> {pair: demand}, one unit per logical message."""
    views = defaultdict(dict)
    for h, r, s, d, t in records:
        if t not in types:
            continue
        p = (min(s, d), max(s, d))
        views[(h, r)][p] = views[(h, r)].get(p, 0) + 1
    return dict(sorted(views.items()))


def min_vertex_cover(n, edges, verts=None):
    """Exact minimum vertex cover; lexicographically smallest among minima.

    The tie-break is independent of the previous view by construction, so k
    cannot be inflated by preferring covers that happen to overlap.

    The candidate vertex set is derived from the edges themselves rather than
    assumed to be range(n). Assuming range(n) silently breaks on any
    implementation that numbers replicas from 1, which relab/hotstuff does: the
    highest-numbered replica can never be selected, so a 2-cover is missed and
    a spurious 3-cover is reported instead."""
    if not edges:
        return frozenset()
    if verts is None:
        verts = sorted({v for e in edges for v in e})
    for size in range(0, len(verts) + 1):
        for cand in itertools.combinations(verts, size):
            cs = set(cand)
            if all(a in cs or b in cs for a, b in edges):
                return frozenset(cand)
    return frozenset(verts)


def star_union(n, cover, verts=None):
    """All edges incident to the cover, over the actual vertex set."""
    if verts is None:
        verts = list(range(n))
    out = set()
    for h in cover:
        for j in verts:
            if j != h:
                out.add((min(h, j), max(h, j)))
    return out


def analyze(records, n, types, label):
    views = build_views(records, types)
    # vertex set taken from the trace, so 0- and 1-indexed implementations
    # are both handled correctly
    verts = sorted({v for d in views.values() for e in d for v in e})
    if not verts:
        verts = list(range(n))
    keys = list(views.keys())
    per = []
    prev_support = None
    prev_cover = None
    for vk in keys:
        d = views[vk]
        S = set(d)
        if not S:
            continue
        cover = min_vertex_cover(n, S, verts)
        su = star_union(n, cover, verts)
        rho = (len(su) - len(S)) / len(su) if su else 0.0
        rec = {"view": vk, "support": len(S), "weighted": sum(d.values()),
               "m": len(cover), "rho": rho,
               "k": len(cover & prev_cover) if prev_cover is not None else None,
               "pi": None}
        if prev_support is not None:
            tot = sum(d.values())
            rec["pi"] = sum(w for p, w in d.items() if p in prev_support) / tot
        per.append(rec)
        prev_support, prev_cover = S, cover

    pis = [r["pi"] for r in per if r["pi"] is not None]
    ms = [r["m"] for r in per]
    ks = [r["k"] for r in per if r["k"] is not None]
    rhos = [r["rho"] for r in per]
    sup = [r["support"] for r in per]

    def mstd(x):
        return (statistics.mean(x), statistics.pstdev(x)) if x else (0.0, 0.0)

    m_mean, m_sd = mstd(ms)
    k_mean, k_sd = mstd(ks)
    pi_meas, pi_sd = mstd(pis)
    rho_mean, _ = mstd(rhos)

    mr, kr = round(m_mean), round(k_mean)
    denom = mr * (n - 1) if mr else 1
    pi_theory = (kr * (n - 1) + mr * (mr - kr)) / denom if mr else 0.0

    return {
        "label": label, "n": n, "views": len(per),
        "support_mean": mstd(sup)[0],
        "m_mean": m_mean, "m_sd": m_sd, "m_cv": m_sd / m_mean if m_mean else 0,
        "k_mean": k_mean, "k_sd": k_sd, "k_cv": k_sd / k_mean if k_mean else 0,
        "rho_mean": rho_mean,
        "pi_measured": pi_meas, "pi_sd": pi_sd,
        "m_used": mr, "k_used": kr, "pi_theory": pi_theory,
        "error": abs(pi_meas - pi_theory),
    }, per


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "research/results/e1/raw/comet_trace.json"
    data = json.load(open(src))
    n = data["n_validators"]
    recs = [tuple(r) for r in data["records"]]
    print(f"{len(recs)} records, n={n}\n")
    out = {}
    for label, types in (("D-core", D_CORE), ("D-all", D_ALL)):
        summ, per = analyze(recs, n, types, label)
        out[label] = summ
        print(f"  {label}")
        print(f"    views              {summ['views']}")
        print(f"    support size       {summ['support_mean']:.2f} of {n*(n-1)//2}")
        print(f"    m (min cover)      {summ['m_mean']:.3f} +/- {summ['m_sd']:.3f} "
              f"(cv {summ['m_cv']:.3f})")
        print(f"    k (cover overlap)  {summ['k_mean']:.3f} +/- {summ['k_sd']:.3f} "
              f"(cv {summ['k_cv']:.3f})")
        print(f"    rho (over-predict) {summ['rho_mean']:.4f}")
        print(f"    pi measured        {summ['pi_measured']:.4f} +/- {summ['pi_sd']:.4f}")
        print(f"    pi theory (m={summ['m_used']}, k={summ['k_used']})  "
              f"{summ['pi_theory']:.4f}")
        print(f"    error              {summ['error']:.4f}")
        print()
    return out


if __name__ == "__main__":
    main()
