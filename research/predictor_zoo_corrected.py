#!/usr/bin/env python3
"""Corrected predictor zoo -- post-freeze addendum to P-predictor-zoo-001.

WHY THIS EXISTS
---------------
research/predictor_zoo.py (frozen, still valid) measures:
    persistence = |S(t) & S(t-1)| / |S(t)|      cardinality-weighted
    budget      = 2(n-1)                        = m(n-1), exceeds |S(t)| by C(m,2)
    coverage    = |top-B & S(t)| / min(B,|S(t)|) cardinality-weighted

The manuscript's Definition 4 uses DEMAND weighting, and Theorem B's cases are
stated on the nomination budget B. This script recomputes every quantity under
the manuscript definitions:

    d_t(p)  = number of DISTINCT hubs incident to pair p   (1 or 2)
    D_t     = sum_p d_t(p)                                 = |hubs| * (n-1)
    S(t)    = {p : d_t(p) > 0}
    B_t     = |S(t)|                                       (support cardinality)
    pi_t    = sum_{p in S(t-1)} d_t(p) / D_t
    cov_t   = sum_{p in top-B}  d_t(p) / D_t

It does NOT overwrite the frozen experiment. Output goes to
research/results/predictor_zoo_corrected/.

TIE-BREAK RULE (explicit, identical for every predictor):
    sort by (-score, pair) where pair is the (min,max) integer tuple.
    Descending score, then ascending pair. No reliance on dict insertion order.
"""
from __future__ import annotations

import hashlib, itertools, json, os, platform, subprocess, sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results", "predictor_zoo_corrected")

VIEWS, WARM = 600, 120
NS = (16, 32)
SCHEDULES = ("round_robin", "shuffled_epoch", "vrf", "weighted")
SEEDS = [0]                      # original zoo used seed=0; recorded explicitly
EWMA_ALPHAS = (0.5, 0.7)         # 0.5 = original (boundary); 0.7 = strictly dominant
TIE_BREAK = "descending score, then ascending pair tuple (min,max)"

# --------------------------------------------------------------------------
# workload -- identical schedule construction to the frozen zoo
# --------------------------------------------------------------------------
def star(n, c):
    return {(min(c, j), max(c, j)) for j in range(n) if j != c}

def make_schedule(n, kind, views, seed=0):
    rng = np.random.default_rng(seed)
    if kind == "round_robin":
        return [t % n for t in range(views + 4)]
    if kind == "vrf":
        return [int(x) for x in rng.integers(0, n, views + 4)]
    if kind == "shuffled_epoch":
        out = []
        while len(out) < views + 4:
            out.extend(int(x) for x in rng.permutation(n))
        return out[:views + 4]
    if kind == "weighted":
        w = np.array([1.0 / (i + 1) for i in range(n)]); w = w / w.sum()
        return [int(rng.choice(n, p=w)) for _ in range(views + 4)]
    raise ValueError(kind)

def hubs_of(sched, t):
    """Distinct hubs of view t: the proposer of t and of t+1."""
    return sorted({sched[t], sched[t + 1]})

def demand_of(n, sched, t):
    """d_t as a dict pair -> number of distinct incident hubs (1 or 2)."""
    d = {}
    for c in hubs_of(sched, t):
        for p in star(n, c):
            d[p] = d.get(p, 0.0) + 1.0
    return d

# --------------------------------------------------------------------------
# metrics -- demand-weighted throughout
# --------------------------------------------------------------------------
def rank(scores):
    return sorted(scores, key=lambda p: (-scores[p], p))

def coverage(scores, d, B):
    D = sum(d.values())
    if D <= 0:
        return 1.0
    top = rank(scores)[:B]
    return sum(d.get(p, 0.0) for p in top) / D

def pi_of(d, prev):
    D = sum(d.values())
    return sum(v for p, v in d.items() if p in prev) / D if D else 1.0

# --------------------------------------------------------------------------
# predictors
# --------------------------------------------------------------------------
class EWMA:
    is_rwc, strict_dominant = True, None
    def __init__(self, n, alpha):
        self.a, self.s = alpha, defaultdict(float)
        self.name = f"ewma{alpha:g}"
        self.strict_dominant = alpha > 0.5      # w1=a, tail=1-a
    def predict(self, t): return dict(self.s)
    def observe(self, t, d):
        for p in set(self.s) | set(d):
            self.s[p] = self.a * (1.0 if p in d else 0.0) + (1 - self.a) * self.s[p]

class LastObs:
    name, is_rwc, strict_dominant = "last", True, True   # w=(1,0,0,...)
    def __init__(self, n): self.prev = set()
    def predict(self, t): return {p: 1.0 for p in self.prev}
    def observe(self, t, d): self.prev = set(d)

class Freq:
    name, is_rwc, strict_dominant = "freq", True, False  # uniform weights, fails dominance
    def __init__(self, n): self.c = defaultdict(float)
    def predict(self, t): return dict(self.c)
    def observe(self, t, d):
        for p in d: self.c[p] += 1

class Markov1:
    name, is_rwc, strict_dominant = "markov1", False, False
    def __init__(self, n):
        self.n = n; self.tab = defaultdict(lambda: defaultdict(float)); self.prev_key = None
    def _key(self, d):
        deg = np.zeros(self.n)
        for (a, b) in d: deg[a] += 1; deg[b] += 1
        return int(np.argmax(deg))
    def predict(self, t):
        return {} if self.prev_key is None else dict(self.tab[self.prev_key])
    def observe(self, t, d):
        if self.prev_key is not None:
            for p in d: self.tab[self.prev_key][p] += 1
        self.prev_key = self._key(d)

class Periodic:
    name, is_rwc, strict_dominant = "periodic", False, False
    def __init__(self, n, max_p=None):
        self.n = n; self.hist = []; self.max_p = max_p or (2 * n + 2); self.P = None
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
        return {} if idx < 0 else {p: 1.0 for p in self.hist[idx]}
    def observe(self, t, d): self.hist.append(set(d))

class Oracle:
    name, is_rwc, strict_dominant = "oracle", False, False
    def __init__(self, n, sched): self.n, self.sched = n, sched
    def predict(self, t): return {p: 1.0 for p in demand_of(self.n, self.sched, t)}
    def observe(self, t, d): pass

def build(n, sched):
    ps = [EWMA(n, a) for a in EWMA_ALPHAS]
    return ps + [LastObs(n), Freq(n), Markov1(n), Periodic(n), Oracle(n, sched)]

# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------
def run(n, kind, seed):
    sched = make_schedule(n, kind, VIEWS, seed)
    preds = build(n, sched)
    acc = {p.name: [] for p in preds}
    cases = {p.name: {"eq": [], "gt": [], "lt": []} for p in preds}
    pis, sizes, dtot = [], [], []
    prev = None
    for t in range(VIEWS):
        d = demand_of(n, sched, t)
        S = set(d); B = len(S); D = sum(d.values())
        if prev is not None and t >= WARM:
            pi_t = pi_of(d, prev)
            pis.append(pi_t); sizes.append(B); dtot.append(D)
            for p in preds:
                sc = p.predict(t)
                c = coverage(sc, d, B) if sc else 0.0
                acc[p.name].append(c)
                key = "eq" if len(prev) == B else ("gt" if len(prev) > B else "lt")
                cases[p.name][key].append(c - pi_t)
        for p in preds:
            p.observe(t, d)
        prev = S
    return preds, acc, cases, pis, sizes, dtot

# --------------------------------------------------------------------------
# PRE-RUN VALIDATION -- hard stop
# --------------------------------------------------------------------------
def preflight():
    print("=" * 78); print("PRE-RUN VALIDATION"); print("=" * 78)
    fails = []
    n = 16
    sched = make_schedule(n, "round_robin", VIEWS, 0)
    d = demand_of(n, sched, 5)
    hubs = hubs_of(sched, 5); m = len(hubs)
    S = set(d); D = sum(d.values())
    dbl = [p for p, v in d.items() if v == 2.0]
    print(f"  n={n}  schedule=round_robin  view t=5")
    print(f"  hubs                 = {hubs}   (m = {m})")
    print(f"  |S(t)|               = {len(S)}")
    print(f"  B (= |S(t)|)         = {len(S)}")
    print(f"  D_t (total demand)   = {D:.0f}")
    print(f"  pairs with d=2       = {dbl}   (count {len(dbl)} = C(m,2) = {m*(m-1)//2})")
    print(f"  weighting            = d_t(p) = # distinct hubs incident to p")
    print(f"  tie-break            = {TIE_BREAK}")

    def chk(name, cond, detail=""):
        print(f"  [{'ok' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
        if not cond: fails.append(name)

    chk("m == 2", m == 2, f"m={m}")
    chk("|S| == 29", len(S) == 29, f"|S|={len(S)}")
    chk("B  == 29", len(S) == 29)
    chk("D  == 30", abs(D - 30) < 1e-12, f"D={D}")
    chk("exactly C(m,2)=1 hub-hub pair carries demand 2", len(dbl) == 1)

    # pi for round-robin must be Theorem A's (n+1)/(2(n-1)) = 17/30
    prev = None; pis = []
    for t in range(VIEWS):
        dd = demand_of(n, sched, t)
        if prev is not None and t >= WARM: pis.append(pi_of(dd, prev))
        prev = set(dd)
    pim = float(np.mean(pis)); target = 17.0 / 30.0
    chk("pi(round-robin,n=16) == 17/30", abs(pim - target) < 1e-12,
        f"measured {pim:.15f} vs {target:.15f}  (Theorem A pi(16,2,1))")

    # coverage denominator must be D, not |S|
    sc = {p: 1.0 for p in S}
    cov_all = coverage(sc, d, len(S))
    chk("coverage denominator is D (all-of-S scores 1.0, not 29/29)",
        abs(cov_all - 1.0) < 1e-12, f"cov(all of S)={cov_all:.6f}")
    half = dict(list(sc.items())[:1])
    p0 = list(half)[0]
    chk("coverage uses demand weights", abs(coverage(half, d, 1) - d[p0] / D) < 1e-12,
        f"single-pair cov = {coverage(half,d,1):.6f} = d/D = {d[p0]/D:.6f}")
    print()
    if fails:
        print(f"PRE-RUN VALIDATION FAILED: {fails}"); sys.exit(1)
    print("PRE-RUN VALIDATION PASSED\n")

if __name__ == "__main__":
    print("=" * 78); print("CORRECTED PREDICTOR ZOO -- configuration"); print("=" * 78)
    print(f"  n values      : {NS}")
    print(f"  schedules     : {SCHEDULES}")
    print(f"  views         : {VIEWS}   burn-in: {WARM}")
    print(f"  seeds         : {SEEDS}")
    print(f"  EWMA alphas   : {EWMA_ALPHAS}  (0.5 = frozen-zoo value, boundary; 0.7 strictly dominant)")
    print(f"  budget        : B_t = |S(t)|  (NOT m(n-1))")
    print(f"  pi            : demand-weighted, sum_{{p in S(t-1)}} d_t(p) / D_t")
    print(f"  coverage      : demand-weighted, sum_{{p in top-B}} d_t(p) / D_t")
    print(f"  tie-break     : {TIE_BREAK}")
    print()
    preflight()

    # ----------------------------------------------------------------------
    print("=" * 78); print("RESULTS  (demand-weighted, B = |S(t)|)"); print("=" * 78)
    PRED_ORDER = ["ewma0.5", "ewma0.7", "last", "freq", "markov1", "periodic", "oracle"]
    rows, allcases = [], []
    for n in NS:
        print(f"\n  n = {n}")
        print(f"    {'schedule':<16}{'pi':>9}{'|S| min':>9}{'|S| max':>9}" +
              "".join(f"{k:>10}" for k in PRED_ORDER))
        for kind in SCHEDULES:
            for seed in SEEDS:
                preds, acc, cases, pis, sizes, dtot = run(n, kind, seed)
                r = {"n": n, "schedule": kind, "seed": seed,
                     "pi": float(np.mean(pis)),
                     "S_min": int(min(sizes)), "S_max": int(max(sizes)),
                     "D_mean": float(np.mean(dtot)), "views_scored": len(pis)}
                for name, v in acc.items(): r[name] = float(np.mean(v))
                rows.append(r)
                allcases.append({"n": n, "schedule": kind, "seed": seed,
                                 "cases": {nm: {k: [float(x) for x in v]
                                                for k, v in c.items()}
                                           for nm, c in cases.items()},
                                 "rwc": {p.name: bool(p.is_rwc) for p in preds},
                                 "dominant": {p.name: bool(p.strict_dominant) for p in preds}})
                print(f"    {kind:<16}{r['pi']:>9.4f}{r['S_min']:>9}{r['S_max']:>9}" +
                      "".join(f"{r[k]:>10.4f}" for k in PRED_ORDER))

    # ----------------------------------------------------------------------
    print(); print("=" * 78); print("POST-RUN VALIDATION"); print("=" * 78)
    checks, viol_detail = [], []
    def ck(name, cond, detail=""):
        checks.append({"check": name, "pass": bool(cond), "detail": detail})
        print(f"  [{'ok' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))

    # A -- pi matches Theorem A on deterministic round-robin
    worst = 0.0
    for r in rows:
        if r["schedule"] != "round_robin": continue
        n = r["n"]; th = (n + 1) / (2 * (n - 1))
        worst = max(worst, abs(r["pi"] - th))
    ck("A. pi == Theorem A pi(n,2,1)=(n+1)/(2(n-1)) on round-robin",
       worst < 1e-12, f"max |pi_measured - pi_theory| = {worst:.3e}")

    # B -- three-case theorem, per view, for strictly dominant RWC predictors only
    nviol = {"eq": 0, "gt": 0, "lt": 0}; ntot = {"eq": 0, "gt": 0, "lt": 0}
    for blk in allcases:
        for nm, c in blk["cases"].items():
            if not (blk["rwc"][nm] and blk["dominant"][nm]): continue
            for key, deltas in c.items():
                ntot[key] += len(deltas)
                for dd in deltas:
                    bad = (abs(dd) > 1e-9) if key == "eq" else \
                          (dd > 1e-9 if key == "gt" else dd < -1e-9)
                    if bad:
                        nviol[key] += 1
                        viol_detail.append({"n": blk["n"], "schedule": blk["schedule"],
                                            "predictor": nm, "case": key,
                                            "cov_minus_pi": dd})
    ck("B. |S(t-1)|=B => cov=pi   (strictly dominant RWC)",
       nviol["eq"] == 0, f"{nviol['eq']} violations / {ntot['eq']} views")
    ck("B. |S(t-1)|>B => cov<=pi  (strictly dominant RWC)",
       nviol["gt"] == 0, f"{nviol['gt']} violations / {ntot['gt']} views")
    ck("B. |S(t-1)|<B => cov>=pi  (strictly dominant RWC)",
       nviol["lt"] == 0, f"{nviol['lt']} violations / {ntot['lt']} views")

    # boundary predictor reported separately, never excluded
    bnv, bnt = 0, 0
    for blk in allcases:
        for nm, c in blk["cases"].items():
            if nm != "ewma0.5": continue
            for key, deltas in c.items():
                bnt += len(deltas)
                for dd in deltas:
                    if (abs(dd) > 1e-9) if key == "eq" else \
                       (dd > 1e-9 if key == "gt" else dd < -1e-9): bnv += 1
    print(f"  [--] ewma0.5 (alpha at the dominance BOUNDARY, w1 = sum w_s>=2): "
          f"{bnv} deviations / {bnt} views -- reported, not excluded")

    # C, D -- non-RWC predictors may exceed pi
    per_hit = [r for r in rows if r["periodic"] > r["pi"] + 1e-6]
    mk_hit  = [r for r in rows if r["markov1"]  > r["pi"] + 1e-6]
    ck("C. periodicity can exceed pi", len(per_hit) > 0,
       f"{len(per_hit)}/{len(rows)} configs; max {max((r['periodic']-r['pi'] for r in per_hit), default=0):+.4f}")
    ck("D. markov1 can exceed pi", len(mk_hit) > 0,
       f"{len(mk_hit)}/{len(rows)} configs; max {max((r['markov1']-r['pi'] for r in mk_hit), default=0):+.4f}")

    # E -- freq is outside the dominance class
    ck("E. freq (uniform weights) fails lag-1 dominance and is unbounded by the theorem",
       all(not blk["dominant"]["freq"] for blk in allcases),
       f"freq mean coverage {np.mean([r['freq'] for r in rows]):.4f} vs mean pi {np.mean([r['pi'] for r in rows]):.4f}")

    if viol_detail:
        print(f"\n  VIOLATIONS ({len(viol_detail)}), first 10:")
        for v in viol_detail[:10]: print("   ", v)

    # ----------------------------------------------------------------------
    os.makedirs(OUT, exist_ok=True)
    def sha(path):
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    def git(*a):
        try: return subprocess.check_output(["git"] + list(a), cwd=HERE,
                                            stderr=subprocess.DEVNULL).decode().strip()
        except Exception: return None
    rec = {"experiment_id": "P-predictor-zoo-corrected-001",
           "utc": datetime.now(timezone.utc).isoformat(),
           "supersedes": None,
           "addendum_to": "P-predictor-zoo-001 (frozen, NOT overwritten)",
           "definitions": {
               "demand": "d_t(p) = number of distinct hubs incident to p (1 or 2)",
               "D_t": "sum_p d_t(p) = |hubs| * (n-1)",
               "S_t": "{p : d_t(p) > 0}",
               "budget_B": "|S(t)|  (support cardinality)",
               "pi": "sum_{p in S(t-1)} d_t(p) / D_t",
               "coverage": "sum_{p in top-B} d_t(p) / D_t",
               "tie_break": TIE_BREAK},
           "config": {"n_values": list(NS), "schedules": list(SCHEDULES),
                      "views": VIEWS, "burn_in": WARM, "seeds": SEEDS,
                      "ewma_alphas": list(EWMA_ALPHAS)},
           "environment": {"python": platform.python_version(),
                           "numpy": np.__version__,
                           "platform": platform.platform()},
           "provenance": {"git_commit_before_run": git("rev-parse", "HEAD"),
                          "script_sha256": sha(os.path.abspath(__file__)),
                          "command": "python3 research/predictor_zoo_corrected.py"},
           "rows": rows,
           "checks": checks,
           "violations": viol_detail,
           "boundary_predictor_note": {
               "predictor": "ewma0.5",
               "deviations": bnv, "views": bnt,
               "reason": "alpha=0.5 gives w1 = sum_{s>=2} w_s exactly; lag-1 dominance "
                         "requires STRICT inequality, so ewma0.5 is on the class boundary "
                         "and is excluded from check B but reported here."}}
    outp = os.path.join(OUT, "P-predictor-zoo-corrected-001.json")
    json.dump(rec, open(outp, "w"), indent=2)
    print(f"\n  wrote {os.path.relpath(outp, os.path.dirname(HERE))}")
    print(f"  result sha256 {sha(outp)}")
    print(f"  script sha256 {sha(os.path.abspath(__file__))}")
    npass = sum(1 for c in checks if c["pass"])
    print()
    print("=" * 78)
    print(f"POST-RUN VALIDATION: {npass}/{len(checks)} checks passed")
    print("=" * 78)
    sys.exit(0 if npass == len(checks) else 1)
