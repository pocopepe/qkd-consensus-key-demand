#!/usr/bin/env python3
"""How much of the persistence result survives real BFT implementation behaviour?

The idealised model gives every view exactly two hubs, one of which carries
over, so pi -> 1/2 and the structural forecaster gains 1 - pi -> 1/2. Real
implementations do not look like that. Each of the mechanisms below changes the
hub structure, and by the general formula pi(n,m,k) -> k/m, anything that raises
the surviving-hub fraction shrinks the gain that the whole design is justified by.

  pipelining     d views in flight at once: m = d+1 hubs, k = d survive
  aggregation    votes reach the leader through an f-ary tree, so interior
                 nodes become hubs too and persist across views
  vote gossip    votes are gossiped over a random mesh of degree g instead of
                 unicast to the leader, adding leader-independent support
  batching       many client requests per proposal. Intended as a control on
                 the assumption that batching changes message size but not
                 support. That assumption is WRONG: pi is demand-weighted, so
                 making proposals heavier than votes shifts the weight onto the
                 star that persists, and pi rises. Whether this happens in a
                 deployment depends on whether key is consumed per message
                 (Wegman-Carter tag, constant) or per byte (one-time-pad
                 payload, proportional to batch size).

This is a falsification test for the practical relevance of the result, not a
demonstration of it.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def star(n, c):
    return {(min(c, j), max(c, j)) for j in range(n) if j != c}


def pi_of(demands):
    """Message-weighted persistence of a sequence of demand multisets."""
    acc = []
    for t in range(1, len(demands)):
        d, prev = demands[t], set(demands[t - 1])
        tot = sum(d.values())
        if tot <= 0:
            continue
        acc.append(sum(w for p, w in d.items() if p in prev) / tot)
    return float(np.mean(acc))


def add(d, pairs, w=1.0):
    for p in pairs:
        d[p] = d.get(p, 0.0) + w


def gen(n, views, mode, seed=0, **kw):
    rng = np.random.default_rng(seed)
    L = [t % n for t in range(views + 8)]
    out = []
    for t in range(views):
        d = {}
        if mode == "ideal":
            add(d, star(n, L[t])); add(d, star(n, L[t + 1]))
        elif mode == "pipelined":
            depth = kw.get("depth", 3)
            for i in range(depth + 1):
                add(d, star(n, L[t + i]))
        elif mode == "aggregation":
            f = kw.get("fanout", 4)
            add(d, star(n, L[t]))                      # proposal broadcast
            # votes climb an f-ary tree rooted at the next leader
            root = L[t + 1]
            others = [v for v in range(n) if v != root]
            level = others[:]
            while len(level) > 1:
                nxt = level[:max(1, len(level) // f)]
                for i, child in enumerate(level):
                    parent = nxt[i % len(nxt)]
                    if parent != child:
                        add(d, {(min(parent, child), max(parent, child))})
                level = nxt
            for v in level:
                if v != root:
                    add(d, {(min(root, v), max(root, v))})
        elif mode == "gossip":
            g = kw.get("degree", 4)
            add(d, star(n, L[t]))
            for v in range(n):                          # each replica gossips
                peers = rng.choice([u for u in range(n) if u != v],
                                   size=min(g, n - 1), replace=False)
                add(d, {(min(v, int(u)), max(v, int(u))) for u in peers})
        elif mode == "batching":
            b = kw.get("batch", 64)
            add(d, star(n, L[t]), w=b); add(d, star(n, L[t + 1]), w=1.0)
        else:
            raise ValueError(mode)
        out.append(d)
    return out


def coverage_ewma(demands, K, alpha=0.5, warm=40):
    s = {}
    acc = []
    for t, d in enumerate(demands):
        if t >= warm and s:
            top = sorted(s, key=lambda p: -s[p])[:K]
            tot = sum(d.values())
            acc.append(sum(d.get(p, 0.0) for p in top) / tot if tot else 1.0)
        for p in set(s) | set(d):
            s[p] = alpha * d.get(p, 0.0) + (1 - alpha) * s.get(p, 0.0)
    return float(np.mean(acc)) if acc else 0.0


def main():
    n, views = 16, 500
    print("=" * 82)
    print("V1  Effect of real implementation mechanisms on persistence and gain")
    print("=" * 82)
    print("  gain = 1 - pi is what the structural forecaster can win. Any")
    print("  mechanism that raises pi shrinks the justification for the design.\n")
    print(f"  {'configuration':<34}{'pi':>9}{'gain':>9}{'ewma cov':>11}{'|S|':>7}")
    rows = []
    cfgs = [
        ("ideal chained (m=2, k=1)", "ideal", {}),
        ("pipelined depth 2", "pipelined", {"depth": 2}),
        ("pipelined depth 3", "pipelined", {"depth": 3}),
        ("pipelined depth 5", "pipelined", {"depth": 5}),
        ("aggregation tree, fanout 4", "aggregation", {"fanout": 4}),
        ("aggregation tree, fanout 2", "aggregation", {"fanout": 2}),
        ("vote gossip, degree 2", "gossip", {"degree": 2}),
        ("vote gossip, degree 4", "gossip", {"degree": 4}),
        ("vote gossip, degree 8", "gossip", {"degree": 8}),
        ("batching x64 (control)", "batching", {"batch": 64}),
    ]
    for label, mode, kw in cfgs:
        ds = gen(n, views, mode, seed=1, **kw)
        pi = pi_of(ds)
        supp = float(np.mean([len(d) for d in ds]))
        cov = coverage_ewma(ds, K=2 * (n - 1))
        rows.append({"config": label, "pi": pi, "gain": 1 - pi,
                     "ewma_cov": cov, "support": supp})
        print(f"  {label:<34}{pi:>9.4f}{1-pi:>9.4f}{cov:>11.4f}{supp:>7.0f}")

    print()
    ideal = next(r for r in rows if r["config"].startswith("ideal"))
    batch = next(r for r in rows if r["config"].startswith("batching"))
    print("  The batching row was expected to act as a control and did not.")
    print(f"    ideal pi = {ideal['pi']:.4f}, batching pi = {batch['pi']:.4f}, "
          f"diff = {abs(ideal['pi']-batch['pi']):.4f}")
    print("  pi is weighted by key demand, not by support membership, so putting")
    print("  most of the demand on the proposal star -- which is precisely the")
    print("  star that carried over from the previous view -- drives pi toward 1.")
    print("  This matters only if key is consumed per byte (OTP payload). Under")
    print("  tag-only authentication the per-pair demand is flat and pi is")
    print("  unchanged, so the deployment choice decides whether the result")
    print("  applies at all.")

    print()
    print("=" * 82)
    print("V2  Which regime still justifies structural forecasting?")
    print("=" * 82)
    thresh = 0.25
    keep = [r for r in rows if r["gain"] >= thresh]
    drop = [r for r in rows if r["gain"] < thresh]
    print(f"  gain >= {thresh} (worth the added complexity):")
    for r in keep:
        print(f"    {r['config']:<34} gain = {r['gain']:.4f}")
    print(f"\n  gain < {thresh} (structural forecasting buys little):")
    for r in drop:
        print(f"    {r['config']:<34} gain = {r['gain']:.4f}")

    rec = {"experiment_id": "V-realism-001",
           "utc": datetime.now(timezone.utc).isoformat(),
           "n": n, "views": views, "rows": rows}
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "V-realism-001.json"), "w") as f:
        json.dump(rec, f, indent=2)
    print("\nwrote research/results/V-realism-001.json")


if __name__ == "__main__":
    main()
