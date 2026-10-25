#!/usr/bin/env python3
"""Cycle-3 C1 verdicts from cosmos_loss_sim.py output. Usage: c1_verdicts.py <sim_json> <out_json>
Loss effect: Delta_sim = pi(with real absences) - pi(same leader sequence, no loss);
Delta_pred = share of views with four distinct leaders x (Proposition 1 at the measured per-role
rates on those views - Corollary 1). Pooled relative error R = sum|Delta_sim - Delta_pred| / sum|Delta_sim|.
Bands are constants, hashed in PREDICTION_LOCK_C1.md before the held-out fetch."""
import json, sys
C1A_MAX_R = 0.15          # round-robin cells (random and stress subsets, n = 16, 32, 64): R <= this in every cell
C1A_MIN_EFFECT = 1e-4     # a cell whose mean |Delta_sim| is below this is reported but not scored (effect too small to measure)
rows = json.load(open(sys.argv[1])); V = {"cells": {}}
for sch in ("rr", "stake"):
    for sel in ("random", "stress"):
        for n in (16, 32, 64):
            rr = [r for r in rows if r["sched"] == sch and r["sel"] == sel and r["n"] == n]
            if not rr: continue
            num = sum(abs(r["loss_effect_sim"] - r["loss_effect_pred"]) for r in rr); den = sum(abs(r["loss_effect_sim"]) for r in rr)
            eff = den / len(rr)
            cell = {"windows": len(rr), "R": num / den if den else None, "mean_abs_effect": eff,
                    "mean_lost_per_view": sum(r["lost_per_view"] for r in rr) / len(rr),
                    "distinct_share": sum(r["distinct_leader_share"] for r in rr) / len(rr),
                    "max_abs_sim_minus_prop1": max(abs(r["sim"] - r["prop1"]) for r in rr)}
            if sch == "rr":
                cell["scored"] = eff >= C1A_MIN_EFFECT
                cell["ok"] = (not cell["scored"]) or cell["R"] <= C1A_MAX_R
            V["cells"][f"{sch}_{sel}_n{n}"] = cell
scored = [c for k, c in V["cells"].items() if k.startswith("rr_") and c["scored"]]
V["C1A"] = {"scored_cells": len(scored), "verdict": "NOT_TESTABLE" if not scored else ("SUPPORTED" if all(c["ok"] for c in scored) else "REFUTED")}
V["C1B"] = {"verdict": "DESCRIPTIVE", "note": "stake-weighted schedules with repeated leaders are outside Proposition 1; R is reported per cell with the distinct-leader share"}
print(json.dumps(V, indent=1)); json.dump(V, open(sys.argv[2], "w"), indent=1)
