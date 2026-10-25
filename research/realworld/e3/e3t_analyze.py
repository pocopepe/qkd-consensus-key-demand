#!/usr/bin/env python3
"""E3T analysis. Usage: e3t_analyze.py <raw_dir> <out_json>

Per run, on adjacency-correct timeout-free transitions (as E3c/E3d), excluding the run's
final view, which the duration limit truncates (found on development data: a final
view with one message has pi = 1 and biases a run's mean by up to 5e-4): measured pi
(frozen analyser), votes missing by role among the n-1 senders to c = L(t+1)
(a = L(t-1), g = L(t+2) cost two carried units; b = L(t) and others cost one),
mu2 = (miss_a + miss_g)/T, mu1 = (miss_b + miss_other)/T, and
  prop1  = (n+1 - 2 mu2 - mu1) / (2(n-1) - mu2 - mu1)          (Proposition 1)
  blind  = pi_phi(n, phi), phi = 1 - (all missing)/(T (n-1))    (role-blind form)
  cor1   = (n+1) / (2(n-1))                                      (no loss)
Per geography, the arms are paired. D = mean(pi_b, pi_other) - mean(pi_a, pi_g).
Bands are constants, hashed in PREDICTION_LOCK_E3T.md before any held-out run."""
import glob, json, os, random, statistics as st, sys
from collections import defaultdict
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, "..", "..")); sys.path.insert(0, os.path.join(H, ".."))
from e1_analyze import D_CORE, analyze
from pi_p_model import pi_p_closed_form

T1_TOL = 0.002        # |prop1 - measured| in every run
T2_BAND = 0.5         # measured mean D within +-50% of the proposition's predicted mean D, per n
T3_FRAC = 0.5         # |mean(pi_a - pi_g)| and |mean(pi_b - pi_other)| each <= T3_FRAC * predicted mean D
T4_TOL = 0.002        # blind arm: prop1 and role-blind form each within T4_TOL of measured, every run
T5_TOL = 0.002        # none arm: measured within T5_TOL of Corollary 1, every run
T6_TOL = 0.10         # selection guard: for each lossy arm, the pooled share of suppressed views whose NEXT view
                      # is not counted is within T6_TOL of the pooled share of all views not counted
BOOT, SEED = 10000, 20260922

def run(path):
    d = json.load(open(path)); m = d["e3_meta"]; n = m["n"]; recs = [tuple(r) for r in d["records"]]
    tmo = {int(k) for k in d.get("timeout_views", {})}; props = {int(k): v for k, v in d["proposers"].items()}
    _, per = analyze(recs, n, D_CORE, m["tag"])
    present = {r["view"][0] for r in per}
    last = max(present)             # the run's final view is cut off by the duration limit
    good = {r["view"][0]: r["pi"] for r in per if r["pi"] is not None and r["view"][0] not in tmo
            and r["view"][0] != last and (r["view"][0] - 1) in present and (r["view"][0] - 1) not in tmo}
    votes, tgt = defaultdict(set), {}
    for v, _, s, t, ty in recs:
        if ty == "Vote": votes[v].add(s); tgt[v] = t
    miss = defaultdict(int); T = 0; used = []
    for v in sorted(good):
        if v not in props or (v - 1) not in props or v not in tgt: continue
        T += 1; used.append(good[v])
        for x in set(range(1, n + 1)) - {tgt[v]} - votes[v]:
            miss["a" if x == props[v - 1] else "b" if x == props[v] else "g" if x == props.get(v + 2) else "other"] += 1
    mu2, mu1 = (miss["a"] + miss["g"]) / T, (miss["b"] + miss["other"]) / T
    sup_views = {s[0] for s in d.get("suppressed", [])}
    next_excl = sum(1 for t in sup_views if (t + 1) not in good and (t + 1) <= last)
    tot = sum(miss.values())
    return {"tag": m["tag"], "n": n, "arm": m["arm"], "geo": m["geo_seed"], "transitions": T,
            "pi_meas": st.mean(used), "prop1": (n + 1 - 2 * mu2 - mu1) / (2 * (n - 1) - mu2 - mu1),
            "blind": pi_p_closed_form(n, 1 - tot / (T * (n - 1))), "cor1": (n + 1) / (2 * (n - 1)),
            "missing": dict(miss), "mu2": mu2, "mu1": mu1, "suppressed": len(d.get("suppressed", [])),
            "views": len(present), "counted": len(good), "sup_views": len(sup_views), "sup_next_excluded": next_excl,
            "timeouts": len(tmo)}

def boot_ci(xs, rng):
    ms = sorted(st.mean(rng.choices(xs, k=len(xs))) for _ in range(BOOT))
    return ms[int(0.025 * BOOT)], ms[int(0.975 * BOOT) - 1]

def main():
    rows = [run(p) for p in sorted(glob.glob(os.path.join(sys.argv[1], "*.json")))]
    rng = random.Random(SEED); V = {}
    by = defaultdict(dict)
    for r in rows: by[(r["n"], r["geo"])][r["arm"]] = r
    for n in sorted({r["n"] for r in rows}):
        geos = [g for (nn, g), a in by.items() if nn == n and all(k in a for k in ("a", "g", "b", "other"))]
        Dm = [st.mean([by[(n, g)]["b"]["pi_meas"], by[(n, g)]["other"]["pi_meas"]]) - st.mean([by[(n, g)]["a"]["pi_meas"], by[(n, g)]["g"]["pi_meas"]]) for g in geos]
        Dp = [st.mean([by[(n, g)]["b"]["prop1"], by[(n, g)]["other"]["prop1"]]) - st.mean([by[(n, g)]["a"]["prop1"], by[(n, g)]["g"]["prop1"]]) for g in geos]
        Db = [st.mean([by[(n, g)]["b"]["blind"], by[(n, g)]["other"]["blind"]]) - st.mean([by[(n, g)]["a"]["blind"], by[(n, g)]["g"]["blind"]]) for g in geos]
        ag = [by[(n, g)]["a"]["pi_meas"] - by[(n, g)]["g"]["pi_meas"] for g in geos]
        bo = [by[(n, g)]["b"]["pi_meas"] - by[(n, g)]["other"]["pi_meas"] for g in geos]
        lo, hi = boot_ci(Dm, rng) if len(Dm) > 1 else (None, None)
        mDm, mDp = st.mean(Dm), st.mean(Dp)
        V[f"n{n}"] = {"geographies": len(geos), "D_measured": mDm, "D_ci": [lo, hi], "D_prop1": mDp, "D_blind": st.mean(Db),
                      "a_minus_g": st.mean(ag), "b_minus_other": st.mean(bo),
                      "T2_verdict": "NOT_TESTABLE" if lo is None else ("SUPPORTED" if lo > 0 and abs(mDm - mDp) <= T2_BAND * mDp else "REFUTED"),
                      "T3_verdict": "SUPPORTED" if abs(st.mean(ag)) <= T3_FRAC * mDp and abs(st.mean(bo)) <= T3_FRAC * mDp else "REFUTED"}
    lossy = [r for r in rows if r["arm"] != "none"]
    V["T1"] = {"max_abs": max(abs(r["pi_meas"] - r["prop1"]) for r in lossy), "runs": len(lossy),
               "verdict": "SUPPORTED" if max(abs(r["pi_meas"] - r["prop1"]) for r in lossy) <= T1_TOL else "REFUTED"}
    bl = [r for r in rows if r["arm"] == "blind"]
    V["T4"] = {"max_prop1": max((abs(r["pi_meas"] - r["prop1"]) for r in bl), default=None),
               "max_blind": max((abs(r["pi_meas"] - r["blind"]) for r in bl), default=None),
               "verdict": "SUPPORTED" if bl and all(abs(r["pi_meas"] - r["prop1"]) <= T4_TOL and abs(r["pi_meas"] - r["blind"]) <= T4_TOL for r in bl) else "REFUTED"}
    no = [r for r in rows if r["arm"] == "none"]
    V["T5"] = {"max_abs": max((abs(r["pi_meas"] - r["cor1"]) for r in no), default=None),
               "verdict": "SUPPORTED" if no and all(abs(r["pi_meas"] - r["cor1"]) <= T5_TOL for r in no) else "REFUTED"}
    t6 = {}
    for arm in ("a", "g", "b", "other", "blind"):
        rr = [r for r in rows if r["arm"] == arm]
        if not rr: continue
        after = sum(r["sup_next_excluded"] for r in rr) / max(1, sum(r["sup_views"] for r in rr))
        base = 1 - sum(r["counted"] for r in rr) / sum(r["views"] for r in rr)
        t6[arm] = {"after_suppression": after, "baseline": base, "ok": abs(after - base) <= T6_TOL}
    V["T6"] = {"arms": t6, "verdict": "SUPPORTED" if t6 and all(x["ok"] for x in t6.values()) else "REFUTED"}
    for r in rows: print({k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items() if k not in ("geo",)})
    print(json.dumps(V, indent=1))
    json.dump({"runs": rows, "verdicts": V}, open(sys.argv[2], "w"), indent=1)

if __name__ == "__main__":
    main()
