#!/usr/bin/env python3
"""Does the persistence ceiling bind *any* history-based predictor, or only smoothers?

The repository claims EWMA coverage equals support persistence pi, and infers
that beating pi requires protocol knowledge. That inference is only valid if no
history-based predictor can exceed pi. It is not obviously true: a round-robin
schedule is periodic with period n, and a predictor with a table rather than a
decaying average can simply learn the cycle.

If a learner reaches coverage 1 on round-robin without being told the schedule,
then "structural knowledge is required" is false for public schedules and the
contribution has to be restated in terms of schedule entropy rather than
protocol structure.

Predictor classes tested:
  ewma        exponentially weighted, the published baseline
  last        predict exactly the previous view's demand
  freq        long-run marginal frequency per pair
  markov1     table keyed on the previous view's highest-degree vertex
  periodic    table keyed on (t mod P) for the best P found by autocorrelation
  oracle      the true next-view demand (upper bound)
"""
from __future__ import annotations

import itertools
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def star(n, c):
    return {(min(c, j), max(c, j)) for j in range(n) if j != c}


def make_schedule(n, kind, views, seed=0):
    rng = np.random.default_rng(seed)
    if kind == "round_robin":
        return [t % n for t in range(views + 4)]
    if kind == "vrf":
        return [int(x) for x in rng.integers(0, n, views + 4)]
    if kind == "shuffled_epoch":
        # a fresh random permutation every epoch of n views: public within the
        # epoch, unpredictable across epochs. Ethereum-like.
        out = []
        while len(out) < views + 4:
            out.extend(int(x) for x in rng.permutation(n))
        return out[:views + 4]
    if kind == "weighted":
        # stake-weighted: a few validators lead far more often
        w = np.array([1.0 / (i + 1) for i in range(n)])
        w = w / w.sum()
        return [int(rng.choice(n, p=w)) for _ in range(views + 4)]
    raise ValueError(kind)


def demand(n, sched, t):
    return star(n, sched[t]) | star(n, sched[t + 1])


def coverage(pred_scores, actual, K):
    if not actual:
        return 1.0
    top = sorted(pred_scores, key=lambda p: -pred_scores[p])[:K]
    return len(set(top) & actual) / min(K, len(actual)) if actual else 1.0


# --------------------------------------------------------------------------
# predictors: each sees only past demand, never the schedule
# --------------------------------------------------------------------------

class EWMA:
    name = "ewma"
    def __init__(self, n, alpha=0.5):
        self.a = alpha; self.s = defaultdict(float)
    def predict(self, t):
        return dict(self.s)
    def observe(self, t, d):
        for p in set(self.s) | d:
            self.s[p] = self.a * (1.0 if p in d else 0.0) + (1 - self.a) * self.s[p]


class LastObs:
    name = "last"
    def __init__(self, n): self.prev = set()
    def predict(self, t): return {p: 1.0 for p in self.prev}
    def observe(self, t, d): self.prev = set(d)


class Freq:
    name = "freq"
    def __init__(self, n): self.c = defaultdict(float); self.t = 0
    def predict(self, t): return dict(self.c)
    def observe(self, t, d):
        self.t += 1
        for p in d: self.c[p] += 1


class Markov1:
    """Table keyed on the previous view's highest-degree vertex."""
    name = "markov1"
    def __init__(self, n):
        self.n = n; self.tab = defaultdict(lambda: defaultdict(float))
        self.prev_key = None
    def _key(self, d):
        deg = np.zeros(self.n)
        for (a, b) in d: deg[a] += 1; deg[b] += 1
        return int(np.argmax(deg))
    def predict(self, t):
        if self.prev_key is None: return {}
        return dict(self.tab[self.prev_key])
    def observe(self, t, d):
        if self.prev_key is not None:
            for p in d: self.tab[self.prev_key][p] += 1
        self.prev_key = self._key(d)


class Periodic:
    """Table keyed on (t mod P), P chosen by best in-sample agreement."""
    name = "periodic"
    def __init__(self, n, max_p=None):
        self.n = n; self.hist = []
        self.max_p = max_p or (2 * n + 2)
        self.P = None
    def _fit(self):
        best, bestP = -1.0, None
        for P in range(2, min(self.max_p, len(self.hist) // 2) + 1):
            agree = tot = 0
            for i in range(P, len(self.hist)):
                a, b = self.hist[i], self.hist[i - P]
                agree += len(a & b); tot += max(len(a), 1)
            s = agree / max(tot, 1)
            if s > best: best, bestP = s, P
        self.P = bestP
    def predict(self, t):
        if len(self.hist) < 6: return {}
        if self.P is None or len(self.hist) % 17 == 0: self._fit()
        if self.P is None: return {}
        idx = len(self.hist) - self.P
        if idx < 0: return {}
        return {p: 1.0 for p in self.hist[idx]}
    def observe(self, t, d): self.hist.append(set(d))


class Oracle:
    name = "oracle"
    def __init__(self, n, sched=None): self.sched = sched; self.n = n
    def predict(self, t): return {p: 1.0 for p in demand(self.n, self.sched, t)}
    def observe(self, t, d): pass


def run(n, kind, views=600, warm=120, seed=0):
    sched = make_schedule(n, kind, views, seed)
    preds = [EWMA(n, 0.5), LastObs(n), Freq(n), Markov1(n), Periodic(n),
             Oracle(n, sched)]
    K = 2 * (n - 1)
    acc = {p.name: [] for p in preds}
    pers = []
    prev = None
    for t in range(views):
        d = demand(n, sched, t)
        if prev is not None:
            pers.append(len(d & prev) / max(len(d), 1))
        for p in preds:
            s = p.predict(t)
            if t >= warm:
                acc[p.name].append(coverage(s, d, K) if s else 0.0)
            p.observe(t, d)
        prev = d
    return {k: float(np.mean(v)) for k, v in acc.items()}, float(np.mean(pers))


def main():
    print("=" * 82)
    print("P1  Which predictor classes are bound by the persistence ceiling?")
    print("=" * 82)
    print("  Coverage at K = 2(n-1). Every predictor sees only past demand.")
    print("  'oracle' is told the schedule and is the upper bound.\n")
    rows = []
    for n in (16, 32):
        for kind in ("round_robin", "shuffled_epoch", "vrf", "weighted"):
            r, pi = run(n, kind)
            rows.append({"n": n, "schedule": kind, "pi": pi, **r})
            if kind == "round_robin":
                print(f"  n = {n}")
                print(f"    {'schedule':<16}{'pi':>8}" +
                      "".join(f"{k:>10}" for k in
                              ("ewma", "last", "freq", "markov1", "periodic", "oracle")))
            print(f"    {kind:<16}{pi:>8.4f}" +
                  "".join(f"{r[k]:>10.4f}" for k in
                          ("ewma", "last", "freq", "markov1", "periodic", "oracle")))
        print()

    print("  Reading: any predictor exceeding pi falsifies the claim that the")
    print("  ceiling binds history-based prediction in general.\n")

    breaks = [x for x in rows if max(x["markov1"], x["periodic"], x["last"])
              > x["pi"] + 0.05]
    if breaks:
        print(f"  CEILING EXCEEDED in {len(breaks)}/{len(rows)} configurations:")
        for b in breaks:
            best = max(("markov1", b["markov1"]), ("periodic", b["periodic"]),
                       ("last", b["last"]), key=lambda z: z[1])
            print(f"    n={b['n']:>3} {b['schedule']:<16} pi={b['pi']:.4f} "
                  f"but {best[0]} reaches {best[1]:.4f}")
    else:
        print("  No predictor exceeded pi in any configuration.")

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "P-predictor-zoo-001.json"), "w") as f:
        json.dump({"experiment_id": "P-predictor-zoo-001",
                   "utc": datetime.now(timezone.utc).isoformat(),
                   "K": "2(n-1)", "views": 600, "warm": 120,
                   "rows": rows}, f, indent=2)
    print("\nwrote research/results/P-predictor-zoo-001.json")


if __name__ == "__main__":
    main()
