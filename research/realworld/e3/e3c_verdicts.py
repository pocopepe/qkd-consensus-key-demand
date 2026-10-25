#!/usr/bin/env python3
"""Applies the C1-C3 bands of PREDICTION_LOCK_E3C.md to E3C_RESULTS.json (the
output of the unchanged, hashed e3_analyze.py on de-duplicated traces), and
pairs every run with its E3 twin (same geography seed)."""
import json, os, statistics as st
H = os.path.dirname(os.path.abspath(__file__))
c = json.load(open(os.path.join(H, "E3C_RESULTS.json"))); e = json.load(open(os.path.join(H, "E3_RESULTS_DEDUP.json")))
W = [r for r in c["runs"] if not r["silent"]]; F = [r for r in c["runs"] if r["silent"]]
E = {r["tag"]: r for r in e["runs"]}
cells = c["verdicts"]["P2_full_participation_theory"]["cells"]
V = {}
V["C1_vote_loss_was_artefact"] = {"min_p_vote": min(r["p_vote"] for r in W), "runs_below_0.999": [r["tag"] for r in W if r["p_vote"] < 0.999],
    "verdict": "SUPPORTED" if all(r["p_vote"] >= 0.999 for r in W) else "REFUTED"}
cell_res = {n: x["pi_happy_mean"] - x["pi_full"] for n, x in cells.items()}
run_res = [r["pi_happy"] - r["pi_full"] for r in W]
ok = (all(abs(v) <= 0.002 for v in cell_res.values()) and all(abs(v) <= 0.005 for v in run_res)
      and all(r["m2_fraction_happy"] >= 0.99 for r in W) and all(r["rho_mean_happy"] <= 0.01 for r in W))
V["C2_tight_agreement"] = {"cell_residuals": cell_res, "max_abs_run_residual": max(abs(v) for v in run_res),
    "min_m2": min(r["m2_fraction_happy"] for r in W), "max_rho": max(r["rho_mean_happy"] for r in W), "verdict": "SUPPORTED" if ok else "REFUTED"}
fr = [abs(r["pi_all"] - r["pi_mixture_pred"]) for r in F]
V["C3_fault_mixture"] = {"max_abs_residual": max(fr), "views_f1": sum(r["views_present"] for r in F if len(r["silent"]) == 1),
    "views_f5": sum(r["views_present"] for r in F if len(r["silent"]) == 5), "verdict": "SUPPORTED" if max(fr) <= 0.03 else "REFUTED"}
paired = [{"tag": r["tag"], "n": r["n"], "p_vote_E3": E[r["tag"]]["p_vote"], "p_vote_E3c": r["p_vote"],
           "resid_E3": E[r["tag"]]["pi_happy"] - E[r["tag"]]["pi_full"], "resid_E3c": r["pi_happy"] - r["pi_full"],
           "timeout_E3": E[r["tag"]]["timeout_view_fraction"], "timeout_E3c": r["timeout_view_fraction"]} for r in W]
for k, v in V.items(): print(k, v["verdict"], json.dumps({a: b for a, b in v.items() if a != "verdict"}))
print("\ncell  trans   pi_pred  pi_meas(mean+-sd)   resid     votes    props    rho      timeouts | E3 resid  E3 votes")
for n, x in cells.items():
    rr = [r for r in W if r["n"] == int(n)]; ee = [E[r["tag"]] for r in rr]
    print(f"n={n:>2}  {sum(r['happy_transitions'] for r in rr):5d}  {x['pi_full']:.4f}   {x['pi_happy_mean']:.4f}+-{x['pi_happy_sd']:.4f}   {x['pi_happy_mean']-x['pi_full']:+.5f}  {x['p_vote_mean']:.5f}  {st.mean(r['p_prop'] for r in rr):.5f}  {x['rho_mean']:.5f}  {100*x['timeout_fraction_mean']:.1f}%   | {st.mean(q['pi_happy'] for q in ee)-x['pi_full']:+.4f}   {st.mean(q['p_vote'] for q in ee):.4f}")
print("total transitions", sum(r["happy_transitions"] for r in W), "views", sum(r["views_present"] for r in W),
      "| excess ratio", {n: round((x["pi_happy_mean"] - 0.5) * (int(n) - 1), 4) for n, x in cells.items()})
print("worst twin:", [(p["tag"], round(p["p_vote_E3"], 4), "->", round(p["p_vote_E3c"], 4), round(p["resid_E3"], 4), "->", round(p["resid_E3c"], 5)) for p in paired if p["tag"] in ("wan_n8_g2", "wan_n8_g4", "wan_n16_g3")])
json.dump({"verdicts": V, "paired": paired}, open(os.path.join(H, "E3C_VERDICTS.json"), "w"), indent=1)
