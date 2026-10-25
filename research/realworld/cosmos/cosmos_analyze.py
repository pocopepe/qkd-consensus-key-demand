#!/usr/bin/env python3
"""Cosmos Hub campaign analysis. Usage: cosmos_analyze.py <raw_dir> <out_json>
Bands are constants; hashed into PREDICTION_LOCK_COSMOS.md before any window
was fetched. Bootstrap over windows reuses the v1/v2 routine unmodified."""
from __future__ import annotations
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from fetch_aptos_bitvecs import epoch_bootstrap_ci

CH0_MIN_POWER, CH0_MIN_FRACTION = 0.90, 0.99   # record is NOT quorum-truncated
CH1_MIN_COUNT, CH1_MIN_POWER = 0.98, 0.99      # participation (CI lower bounds)
CH2_MARGIN = 0.15                              # recurrence - (1-p), CI lower bound
CH2B_TOL = 0.05                                # |observed - static-heterogeneity prediction|
CH3_MAX_ROUND_GT0 = 0.01


def window_stats(path: str) -> dict:
    w = json.load(open(path)); power = w["power"]; tot = sum(power.values()); B = w["blocks"]; T = len(B)
    absent = [set(b["absent"]) | set(b["nil"]) for b in B]           # no precommit for the block
    p_count = [1 - len(a) / b["n"] for a, b in zip(absent, B)]
    p_power = [1 - sum(power.get(x, 0) for x in a) / tot for a in absent]
    num = sum(len(absent[i] & absent[i + 1]) for i in range(T - 1)); den = sum(len(absent[i]) for i in range(T - 1))
    h = T // 2; vals = list(power)
    rate = {v: sum(1 for a in absent[:h] if v in a) / h for v in vals}
    sr = sum(rate.values())
    n2 = sum(len(absent[i] & absent[i + 1]) for i in range(h, T - 1)); d2 = sum(len(absent[i]) for i in range(h, T - 1))
    return {"start": w["start"], "blocks": T, "n": len(power), "p_count": sum(p_count) / T, "p_power": sum(p_power) / T,
            "min_block_power": min(p_power), "frac_blocks_power_ge": sum(1 for x in p_power if x >= CH0_MIN_POWER) / T,
            "full_blocks": sum(1 for a in absent if not a) / T,
            "recurrence": num / den if den else None, "iid": 1 - sum(p_count) / T,
            "h2b_obs": n2 / d2 if d2 else None, "h2b_pred": (sum(x * x for x in rate.values()) / sr) if sr else None,
            "round_gt0": sum(1 for b in B if b["r"] > 0) / T,
            "never_seen": sum(1 for v in vals if all(v in a for a in absent)),
            "inconsistent_blocks": sum(1 for b in B if not b["consistent"]), "valset_refetches": w["valset_refetches"],
            "distinct_proposer_rate": sum(1 for i in range(T - 1) if B[i]["p"] != B[i + 1]["p"]) / (T - 1)}


def ci(v, seed):
    if len(v) < 5:
        return {"mean": sum(v) / len(v) if v else None, "n": len(v), "status": "underpowered"}
    m, lo, hi = epoch_bootstrap_ci(v, seed=seed); return {"mean": m, "lo": lo, "hi": hi, "n": len(v)}


def main() -> int:
    per = [window_stats(p) for p in sorted(glob.glob(os.path.join(sys.argv[1], "window_*.json")))]
    for r in per:
        print({k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
    V = {}
    tb = sum(r["blocks"] for r in per)
    f0 = sum(r["frac_blocks_power_ge"] * r["blocks"] for r in per) / tb
    V["CH0_not_truncated"] = {"pooled_fraction_power_ge_0.90": f0, "min_block_power": min(r["min_block_power"] for r in per),
                              "verdict": "SUPPORTED" if f0 >= CH0_MIN_FRACTION else "REFUTED"}
    c, p = ci([r["p_count"] for r in per], 1), ci([r["p_power"] for r in per], 2)
    V["CH1_participation"] = {"count": c, "power": p, "verdict": "UNDERPOWERED" if "lo" not in c else
                              ("SUPPORTED" if c["lo"] >= CH1_MIN_COUNT and p["lo"] >= CH1_MIN_POWER else "REFUTED")}
    rr = [r for r in per if r["recurrence"] is not None]
    d = ci([r["recurrence"] - r["iid"] for r in rr], 3)
    V["CH2_absence_recurs"] = {**d, "mean_recurrence": sum(r["recurrence"] for r in rr) / len(rr) if rr else None,
                               "mean_iid": sum(r["iid"] for r in rr) / len(rr) if rr else None,
                               "verdict": "NOT_TESTABLE" if "lo" not in d else ("SUPPORTED" if d["lo"] >= CH2_MARGIN else "REFUTED")}
    hb = [r for r in per if r["h2b_obs"] is not None and r["h2b_pred"] is not None]
    d = ci([r["h2b_obs"] - r["h2b_pred"] for r in hb], 4)
    V["CH2b_static_heterogeneity"] = {**d, "verdict": "NOT_TESTABLE" if "lo" not in d else
                                      ("SUPPORTED" if -CH2B_TOL <= d["lo"] and d["hi"] <= CH2B_TOL else
                                       "REFUTED" if d["lo"] > CH2B_TOL or d["hi"] < -CH2B_TOL else "INCONCLUSIVE")}
    f3 = sum(r["round_gt0"] * r["blocks"] for r in per) / tb
    V["CH3_low_fault_rate"] = {"pooled_fraction_round_gt0": f3, "verdict": "SUPPORTED" if f3 <= CH3_MAX_ROUND_GT0 else "REFUTED"}
    print("\n=== VERDICTS ===")
    for k, v in V.items(): print(k, v["verdict"], json.dumps({a: b for a, b in v.items() if a != "verdict"}))
    json.dump({"per_window": per, "verdicts": V, "blocks": tb}, open(sys.argv[2], "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
