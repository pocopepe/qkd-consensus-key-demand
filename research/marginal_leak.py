#!/usr/bin/env python3
"""The experiment that decides whether the side-channel claim survives.

An adversary who can time consensus responses can also just watch consensus
traffic. In a chained protocol the proposal names L(t) -- that validator is
broadcasting -- and the vote phase names L(t+1), because the votes are addressed
to it. Both are visible without any key-supply layer at all.

So the question is not "does the pre-armed set reveal the leader" -- it plainly
does -- but "does it reveal anything an observer did not already have". Only the
marginal quantity is attributable to pre-arming, and only the marginal quantity
belongs in a paper about pre-arming.

Attacker A (traffic-only baseline): sees which pairs carried messages in view t,
ranks validators by degree.
Attacker B (timing): sees which pairs were served fast in view t, i.e. the
pre-armed set, ranks the same way.

Both are evaluated on the same target: naming L(t+k) for k = 0, 1, 2, 3.
"""
from __future__ import annotations

import itertools
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def star(n, c):
    return {(min(c, j), max(c, j)) for j in range(n) if j != c}


def traffic_support(n, t):
    """What actually goes on the wire in view t of a chained linear protocol."""
    return star(n, t % n) | star(n, (t + 1) % n)


def prearm_support(n, t, H):
    """What a structural forecaster with horizon H installs before view t."""
    s = set()
    for k in range(H + 1):
        s |= star(n, (t + k) % n)
    return s


def guess(n, support, exclude=()):
    deg = np.zeros(n)
    for (a, b) in support:
        deg[a] += 1
        deg[b] += 1
    order = [int(x) for x in np.argsort(-deg)]
    return [v for v in order if v not in exclude]


def visible(support, watched):
    """Restrict an observation to pairs with at least one endpoint watched."""
    if watched is None:
        return support
    return {p for p in support if p[0] in watched or p[1] in watched}


def run(n=16, views=400, horizons=(1, 2, 3, 4), offsets=(0, 1, 2, 3),
        watch_frac=1.0, seed=0):
    rng = np.random.default_rng(seed)
    watched = None
    if watch_frac < 1.0:
        k = max(1, int(round(watch_frac * n)))
        watched = set(int(x) for x in rng.choice(n, size=k, replace=False))

    out = {}
    for H in horizons:
        accA = {o: 0 for o in offsets}
        accB = {o: 0 for o in offsets}
        for t in range(views):
            ta = visible(traffic_support(n, t), watched)
            tb = visible(prearm_support(n, t, H), watched)
            gA, gB = guess(n, ta), guess(n, tb)
            for o in offsets:
                target = (t + o) % n
                # top-1 among candidates the observer has not already seen
                # proposing: excluding L(t) is free information in both cases
                exc = () if o == 0 else (t % n,)
                a = [v for v in gA if v not in exc]
                b = [v for v in gB if v not in exc]
                accA[o] += int(bool(a) and a[0] == target)
                accB[o] += int(bool(b) and b[0] == target)
        out[H] = {o: {"traffic": accA[o] / views, "prearm": accB[o] / views,
                      "marginal": (accB[o] - accA[o]) / views}
                  for o in offsets}
    return out, watched


def main():
    n = 16
    base = 1.0 / n
    print("=" * 78)
    print("M1  Marginal leakage of pre-arming over a traffic-only observer")
    print("=" * 78)
    print(f"  n = {n}, chained linear protocol, baseline top-1 = {base:.4f}")
    print("  'traffic' = attacker sees the messages; 'prearm' = attacker times them\n")

    res, _ = run(n=n)
    for H in sorted(res):
        print(f"  horizon H = {H}")
        print(f"    {'target':>10}{'traffic':>10}{'prearm':>10}{'marginal':>11}")
        for o in sorted(res[H]):
            r = res[H][o]
            tag = "L(t)" if o == 0 else f"L(t+{o})"
            print(f"    {tag:>10}{r['traffic']:>10.4f}{r['prearm']:>10.4f}"
                  f"{r['marginal']:>+11.4f}")
        print()

    print("  Reading: a marginal of ~0 means pre-arming disclosed nothing the")
    print("  observer could not already read off the wire.\n")

    print("=" * 78)
    print("M2  Restricted vantage: the attacker watches only part of the cluster")
    print("=" * 78)
    print("  A passive external observer cannot probe arbitrary validator pairs.")
    print("  A validator sees its own n-1 pairs; an on-path observer sees the")
    print("  pairs crossing its link. Both are far less than all n(n-1)/2.\n")
    print(f"  {'watched':>9}{'H=1 L(t+1)':>13}{'H=2 L(t+2)':>13}{'H=3 L(t+3)':>13}")
    for wf in (1.0, 0.5, 0.25, 0.125, 1.0 / 16):
        row = f"  {int(round(wf*n)):>7}/{n}"
        for H, o in ((1, 1), (2, 2), (3, 3)):
            r, _ = run(n=n, horizons=(H,), offsets=(o,), watch_frac=wf, seed=5)
            row += f"{r[H][o]['prearm']:>13.4f}"
        print(row)
    print(f"\n  baseline = {base:.4f}")

    rec = {
        "experiment_id": "M-marginal-leak-001",
        "utc": datetime.now(timezone.utc).isoformat(),
        "n": n, "views": 400, "protocol": "chained-linear",
        "baseline_top1": base,
        "marginal": {str(H): {str(o): res[H][o] for o in res[H]} for H in res},
    }
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "M-marginal-leak-001.json"), "w") as f:
        json.dump(rec, f, indent=2)
    print(f"\nwrote research/results/M-marginal-leak-001.json")


if __name__ == "__main__":
    main()
