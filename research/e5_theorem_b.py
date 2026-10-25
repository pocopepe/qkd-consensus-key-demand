#!/usr/bin/env python3
"""E5 -- prove or refute Conjecture B (the RWC ceiling).

Conjecture B as recorded in research_direction.md:

    For every recency-weighted counting (RWC) predictor, cov <= pi, with
    equality attained by last-observation and by EWMA with alpha >= 1/2.

This file argues the conjecture is WRONG as stated, in two ways, and replaces it
with a sharper statement that is provable and that explains every measurement in
the repository.

Definitions. An RWC predictor scores each pair by

    score_t(p) = sum_{s < t} w_{t-s} * 1[p in S(s)]

with w non-negative and independent of p and t. Coverage is measured at budget
K over the demand of view t; pi is the demand-weighted share of view t carried
by S(t-1).

The condition that actually matters is not "alpha >= 1/2" but

    LAG-1 DOMINANCE:   w_1 > sum_{s >= 2} w_s

Under it every member of S(t-1) outranks every non-member, because a member
scores at least w_1 while a non-member scores at most sum_{s>=2} w_s.

For EWMA, w_s = alpha(1-alpha)^(s-1) sums to 1, so sum_{s>=2} w_s = 1 - alpha
and lag-1 dominance is exactly alpha > 1/2 -- which is why the empirical
threshold sat there. For last-observation w = (1,0,0,...) it holds trivially.
For uniform frequency weighting over T views it fails for every T > 2, which is
why `freq` scored far below pi rather than at it.

THEOREM B (corrected). Under lag-1 dominance, with K = |S(t)|:

    |S(t-1)| = K   =>  top-K = S(t-1)   =>  cov = pi   EXACTLY
    |S(t-1)| > K   =>  top-K subset of S(t-1)  =>  cov <= pi
    |S(t-1)| < K   =>  top-K superset of S(t-1) =>  cov >= pi

So the conjecture is wrong twice over: in the constant-support case it is an
equality rather than an inequality, and when the support grows the inequality
runs the other way. Every protocol measured in this repository has constant
support size, which is why the equality was observed everywhere and the failure
mode never appeared.
"""
from __future__ import annotations

import itertools
import json
import os
import random
import sys
from datetime import datetime, timezone

import numpy as np

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
ok = []


def check(name, cond, detail=""):
    ok.append(bool(cond))
    print(f"  [{'ok' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


def rwc_scores(hist, w):
    """hist[-1] is S(t-1). score(p) = sum_s w_s * 1[p in S(t-s)]."""
    sc = {}
    for lag, S in enumerate(reversed(hist), start=1):
        if lag > len(w):
            break
        for p in S:
            sc[p] = sc.get(p, 0.0) + w[lag - 1]
    return sc


def coverage(sc, demand, K):
    tot = sum(demand.values())
    if tot <= 0:
        return 1.0
    top = sorted(sc, key=lambda p: (-sc[p], p))[:K]
    return sum(demand.get(p, 0.0) for p in top) / tot


def pi_of(demand, prev):
    tot = sum(demand.values())
    return sum(v for p, v in demand.items() if p in prev) / tot if tot else 1.0


def lag1_dominant(w):
    return w[0] > sum(w[1:]) + 1e-12


# ---------------------------------------------------------------------------
print("=" * 78)
print("B1  EWMA lag-1 dominance threshold is exactly alpha = 1/2")
print("=" * 78)
T = 24
print(f"  {'alpha':>7}{'w1':>10}{'sum w>=2':>11}{'dominant?':>11}")
rows = []
for a in (0.1, 0.3, 0.45, 0.49, 0.5, 0.51, 0.7, 0.9):
    w = [a * (1 - a) ** (s - 1) for s in range(1, T + 1)]
    rows.append((a, lag1_dominant(w)))
    print(f"  {a:>7.2f}{w[0]:>10.4f}{sum(w[1:]):>11.4f}{str(lag1_dominant(w)):>11}")
check("dominance holds iff alpha > 1/2",
      all(d == (a > 0.5) for a, d in rows if abs(a - 0.5) > 1e-9))

# ---------------------------------------------------------------------------
print()
print("=" * 78)
print("B2  Constant support size: cov = pi EXACTLY under dominance")
print("=" * 78)


def star(n, c):
    return {(min(c, j), max(c, j)) for j in range(n) if j != c}


def chained_demand(n, t, B=1.0):
    d = {}
    for c in (t % n, (t + 1) % n):
        for p in star(n, c):
            d[p] = d.get(p, 0.0) + B
    return d


worst_eq, worst_lt = 0.0, -1.0
print(f"  {'n':>4}{'alpha':>7}{'dominant':>10}{'pi':>10}{'cov':>10}{'cov-pi':>11}")
for n in (8, 16, 32):
    for a in (0.1, 0.3, 0.5, 0.7, 0.9):
        w = [a * (1 - a) ** (s - 1) for s in range(1, T + 1)]
        hist, pis, covs = [], [], []
        for t in range(120):
            d = chained_demand(n, t)
            if len(hist) >= 8:
                K = len({p for p in d})
                sc = rwc_scores(hist, w)
                covs.append(coverage(sc, d, K))
                pis.append(pi_of(d, set(hist[-1])))
            hist.append(set(d))
        pi_m, cov_m = float(np.mean(pis)), float(np.mean(covs))
        dom = lag1_dominant(w)
        if dom:
            worst_eq = max(worst_eq, abs(cov_m - pi_m))
        else:
            worst_lt = max(worst_lt, cov_m - pi_m)
        if n == 16:
            print(f"  {n:>4}{a:>7.2f}{str(dom):>10}{pi_m:>10.6f}{cov_m:>10.6f}"
                  f"{cov_m - pi_m:>+11.6f}")
check("under dominance, cov = pi to machine precision", worst_eq < 1e-12,
      f"max |cov - pi| = {worst_eq:.2e}")
check("without dominance, cov < pi (never above)", worst_lt < 1e-12,
      f"max (cov - pi) = {worst_lt:+.6f}")

# ---------------------------------------------------------------------------
print()
print("=" * 78)
print("B3  The conjecture FAILS when the support grows: cov > pi")
print("=" * 78)
print("""  Construction: |S(t-1)| < |S(t)|. Under dominance the top-K contains all
  of S(t-1) plus extra pairs drawn from older views, and any of those extras
  that happen to lie in S(t) raise coverage above pi.
""")
w_last = [1.0] + [0.0] * (T - 1)          # last-observation, trivially dominant
# S(t-2) = {a,b,c}, S(t-1) = {a}, S(t) = {a,b,c}
hist = [{"a", "b", "c"}, {"a"}]
demand = {"a": 1.0, "b": 1.0, "c": 1.0}
K = 3
sc = rwc_scores(hist, w_last)
cov = coverage(sc, demand, K)
pi = pi_of(demand, hist[-1])
print(f"    S(t-2)={sorted(hist[0])}  S(t-1)={sorted(hist[1])}  S(t)={sorted(demand)}")
print(f"    K={K}  pi={pi:.4f}  cov={cov:.4f}  ->  cov - pi = {cov - pi:+.4f}")
check("counterexample to 'cov <= pi' exists under a dominant weight",
      cov > pi + 1e-9, f"cov={cov:.4f} > pi={pi:.4f}")

# ---------------------------------------------------------------------------
print()
print("=" * 78)
print("B4  Exhaustive search of small cases against the corrected theorem")
print("=" * 78)
print("""  All support sequences over a 4-element universe, |S| in 1..4, three views,
  every dominant weight vector from a grid. Checks the three-case statement.
""")
U = ["a", "b", "c", "d"]
subsets = [frozenset(s) for r in range(1, 5) for s in itertools.combinations(U, r)]
WS = ([1.0, 0.0, 0.0], [0.9, 0.05, 0.05], [0.7, 0.2, 0.05], [0.6, 0.3, 0.05])
viol = {"eq": 0, "le": 0, "ge": 0}
tested = 0
for S2 in subsets:
    for S1 in subsets:
        for S0 in subsets:
            demand = {p: 1.0 for p in S0}
            K = len(S0)
            pi = pi_of(demand, S1)
            for w in WS:
                if not lag1_dominant(w):
                    continue
                sc = rwc_scores([set(S2), set(S1)], w)
                cov = coverage(sc, demand, K)
                tested += 1
                if len(S1) == K and abs(cov - pi) > 1e-9:
                    viol["eq"] += 1
                elif len(S1) > K and cov > pi + 1e-9:
                    viol["le"] += 1
                elif len(S1) < K and cov < pi - 1e-9:
                    viol["ge"] += 1
print(f"  {tested} (support-triple, weight) combinations tested")
print(f"  violations: |S1|=K -> equality: {viol['eq']};  "
      f"|S1|>K -> cov<=pi: {viol['le']};  |S1|<K -> cov>=pi: {viol['ge']}")
check("no violation of the corrected three-case theorem",
      sum(viol.values()) == 0)

# ---------------------------------------------------------------------------
print()
print("=" * 78)
print("B5  Randomised search for a counterexample to the corrected theorem")
print("=" * 78)
rng = random.Random(12345)
bad, trials = 0, 40000
for _ in range(trials):
    m = rng.randint(3, 9)
    uni = list(range(m))
    depth = rng.randint(2, 5)
    hist = [set(rng.sample(uni, rng.randint(1, m))) for _ in range(depth)]
    S0 = set(rng.sample(uni, rng.randint(1, m)))
    demand = {p: rng.random() + 0.1 for p in S0}
    K = len(S0)
    # random dominant weight vector
    tail = [rng.random() for _ in range(depth - 1)]
    ssum = sum(tail) or 1.0
    tail = [x / ssum * rng.uniform(0.05, 0.95) for x in tail]
    w = [1.0] + tail
    if not lag1_dominant(w):
        continue
    sc = rwc_scores(hist, w)
    cov = coverage(sc, demand, K)
    pi = pi_of(demand, hist[-1])
    n1 = len(hist[-1])
    if n1 == K and abs(cov - pi) > 1e-9:
        bad += 1
    elif n1 > K and cov > pi + 1e-9:
        bad += 1
    elif n1 < K and cov < pi - 1e-9:
        bad += 1
print(f"  {trials} randomised instances, dominant weights only")
check("no counterexample found to the corrected theorem", bad == 0,
      f"violations = {bad}")

# ---------------------------------------------------------------------------
print()
print("=" * 78)
print("B6  The corrected theorem explains the measured predictor zoo")
print("=" * 78)
zoo = json.load(open(os.path.join(RESULTS, "P-predictor-zoo-001.json")))
print(f"  {'n':>4}{'pi':>9}{'ewma(.5)':>11}{'last':>9}{'freq':>9}   explanation")
agree = True
for r in zoo["rows"]:
    if r["schedule"] != "round_robin":
        continue
    eq = abs(r["ewma"] - r["pi"]) < 1e-9 and abs(r["last"] - r["pi"]) < 1e-9
    lt = r["freq"] < r["pi"]
    agree = agree and eq and lt
    print(f"  {r['n']:>4}{r['pi']:>9.4f}{r['ewma']:>11.4f}{r['last']:>9.4f}"
          f"{r['freq']:>9.4f}   dominant->equality; freq not dominant->below")
check("measurements match the corrected theorem exactly", agree)

rec = {"experiment_id": "E5-theorem-b-001",
       "utc": datetime.now(timezone.utc).isoformat(),
       "conjecture_as_stated": "cov <= pi for every RWC predictor",
       "status": "REFUTED as stated; replaced by the three-case theorem",
       "condition": "lag-1 dominance: w_1 > sum_{s>=2} w_s",
       "ewma_equivalent": "alpha > 1/2",
       "cases": {"|S(t-1)|=K": "cov = pi exactly",
                 "|S(t-1)|>K": "cov <= pi",
                 "|S(t-1)|<K": "cov >= pi"},
       "checks_passed": f"{sum(ok)}/{len(ok)}"}
os.makedirs(RESULTS, exist_ok=True)
json.dump(rec, open(os.path.join(RESULTS, "E5-theorem-b-001.json"), "w"), indent=2)

print()
print("=" * 78)
print(f"E5 VERIFICATION: {sum(ok)}/{len(ok)} checks passed")
print("=" * 78)
sys.exit(0 if all(ok) else 1)
