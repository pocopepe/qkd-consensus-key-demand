#!/usr/bin/env python3
"""E3 analysis. Reuses the frozen research/e1_analyze.py analyze() UNMODIFIED
on all views (so every transition is between truly adjacent trace views), then
selects adjacency-correct happy transitions: view v counts only if v and v-1
are both present and neither had a local timeout. Bands are constants."""
from __future__ import annotations

import glob, json, os, statistics as st, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(HERE, ".."))
from e1_analyze import D_CORE, analyze
from pi_p_model import pi_p_closed_form

P1_MIN_M2 = 0.99; P1_MAX_RHO = 0.05
P2_TOL = 0.05; P2_DIRECTION_SLACK = 0.002
P3_P_CUTOFF = 0.995; P3_MIN_WIN = 0.80
F_TOL = 0.03


def pi_full(n, m=2, k=1):
    return (k * (n - 1) + m * (m - k)) / (m * (n - 1))


def run_stats(path):
    d = json.load(open(path)); meta = d["e3_meta"]; n = meta["n"]
    recs = [tuple(r) for r in d["records"]]
    tmo = {int(k) for k in d.get("timeout_views", {})}
    summ, per = analyze(recs, n, D_CORE, meta["tag"])
    present = {r["view"][0] for r in per}
    good = [r for r in per if r["pi"] is not None and r["view"][0] not in tmo
            and (r["view"][0] - 1) in present and (r["view"][0] - 1) not in tmo]
    gv = {r["view"][0] for r in good}
    votes = sum(1 for r in recs if r[4] == "Vote" and r[0] in gv)
    props = sum(1 for r in recs if r[4] == "Proposal" and r[0] in gv)
    p_vote = votes / (len(gv) * (n - 1)); p_prop = props / (len(gv) * (n - 1))
    span = max(present) - min(present) + 1
    out = {"tag": meta["tag"], "n": n, "silent": meta["silent"], "views_present": len(per), "view_span": span,
           "happy_transitions": len(good), "timeout_view_fraction": len(tmo & present) / len(present),
           "pi_all": summ["pi_measured"], "pi_happy": st.mean(r["pi"] for r in good),
           "m2_fraction_happy": sum(1 for r in good if r["m"] == 2) / len(good),
           "k_mean_happy": st.mean(r["k"] for r in good), "rho_mean_happy": st.mean(r["rho"] for r in good),
           "p_vote": p_vote, "p_prop": p_prop, "pi_full": pi_full(n), "pi_p": pi_p_closed_form(n, p_vote),
           "k0_transitions": sum(1 for r in per if r["k"] == 0),
           "pi_k0_mean": (st.mean(r["pi"] for r in per if r["k"] == 0 and r["pi"] is not None)
                          if any(r["k"] == 0 for r in per) else None),
           "loadavg": [meta["loadavg_before"], meta["loadavg_after"]]}
    f = len(meta["silent"])
    if f:
        g = f / (n - f)
        out["pi_mixture_pred"] = (1 - g) * pi_full(n) + g * pi_full(n, 2, 0)
        out["missing_view_fraction"] = 1 - len(per) / span
    return out


def main():
    raw, dst = sys.argv[1], sys.argv[2]
    runs = [run_stats(p) for p in sorted(glob.glob(os.path.join(raw, "*.json")))]
    for r in runs:
        print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if k not in ("loadavg",)}, flush=True)
    wan = [r for r in runs if not r["silent"]]; flt = [r for r in runs if r["silent"]]
    V = {}
    V["P1_structure"] = {"min_m2_fraction": min(r["m2_fraction_happy"] for r in wan),
                         "max_rho": max(r["rho_mean_happy"] for r in wan)}
    V["P1_structure"]["verdict"] = ("SUPPORTED" if V["P1_structure"]["min_m2_fraction"] >= P1_MIN_M2
                                    and V["P1_structure"]["max_rho"] <= P1_MAX_RHO else "REFUTED")
    cells = {}
    for n in sorted({r["n"] for r in wan}):
        c = [r for r in wan if r["n"] == n]
        cells[n] = {"pi_happy_mean": st.mean(r["pi_happy"] for r in c), "pi_happy_sd": st.pstdev(r["pi_happy"] for r in c),
                    "pi_full": pi_full(n), "pi_p_mean": st.mean(r["pi_p"] for r in c),
                    "p_vote_mean": st.mean(r["p_vote"] for r in c), "rho_mean": st.mean(r["rho_mean_happy"] for r in c),
                    "timeout_fraction_mean": st.mean(r["timeout_view_fraction"] for r in c),
                    "pi_all_mean": st.mean(r["pi_all"] for r in c), "runs": len(c)}
    worst = max(abs(c["pi_happy_mean"] - c["pi_full"]) for c in cells.values())
    direction_ok = all(c["pi_happy_mean"] <= c["pi_full"] + P2_DIRECTION_SLACK for c in cells.values())
    V["P2_full_participation_theory"] = {"cells": cells, "max_abs_residual": worst, "direction_ok": direction_ok,
                                         "verdict": "SUPPORTED" if worst <= P2_TOL and direction_ok else "REFUTED"}
    elig = [r for r in wan if r["p_vote"] < P3_P_CUTOFF]
    wins = sum(1 for r in elig if abs(r["pi_happy"] - r["pi_p"]) < abs(r["pi_happy"] - r["pi_full"]))
    V["P3_pi_p_improves"] = {"eligible_runs": len(elig), "wins": wins,
                             "mean_abs_resid_full": st.mean(abs(r["pi_happy"] - r["pi_full"]) for r in elig) if elig else None,
                             "mean_abs_resid_pi_p": st.mean(abs(r["pi_happy"] - r["pi_p"]) for r in elig) if elig else None,
                             "verdict": ("NOT_TESTABLE" if len(elig) < 5 else
                                         "SUPPORTED" if wins / len(elig) >= P3_MIN_WIN else "REFUTED")}
    for f in sorted({len(r["silent"]) for r in flt}):
        c = [r for r in flt if len(r["silent"]) == f]
        resid = [r["pi_all"] - r["pi_mixture_pred"] for r in c]
        V[f"F{f}_fault_mixture"] = {"pi_all_mean": st.mean(r["pi_all"] for r in c), "pi_all_sd": st.pstdev(r["pi_all"] for r in c),
                                    "pi_mixture_pred": c[0]["pi_mixture_pred"], "max_abs_residual": max(abs(x) for x in resid),
                                    "pi_k0_mean": st.mean(r["pi_k0_mean"] for r in c if r["pi_k0_mean"] is not None),
                                    "pi_n20": pi_full(c[0]["n"], 2, 0), "missing_view_fraction_mean": st.mean(r["missing_view_fraction"] for r in c),
                                    "runs": len(c), "verdict": "SUPPORTED" if max(abs(x) for x in resid) <= F_TOL else "REFUTED"}
    print("\n=== E3 VERDICTS ===")
    for k, v in V.items():
        print(k, v["verdict"], json.dumps({a: b for a, b in v.items() if a not in ("verdict", "cells")}))
    json.dump({"runs": runs, "verdicts": V}, open(dst, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
