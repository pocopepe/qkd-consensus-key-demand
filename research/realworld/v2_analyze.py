#!/usr/bin/env python3
"""Campaign v2 analysis. Usage: v2_analyze.py <raw_dir> <out_json>

Developed against sample A only (the 6 epochs seen before the v2 lock,
converted to the v2 on-disk format); hashed into PREDICTION_LOCK_V2.md before
any held-out epoch was fetched. Bands are constants below, not arguments.

Reuses, unmodified: analyze_epoch / analyze_proposer_rotation /
epoch_bootstrap_ci from fetch_aptos_bitvecs.py (the v1-locked statistics),
and demand_of / pi_of / the predictor classes from the frozen
research/predictor_zoo_corrected.py.
"""
from __future__ import annotations

import glob
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
from fetch_aptos_bitvecs import analyze_epoch, analyze_proposer_rotation, epoch_bootstrap_ci
import predictor_zoo_corrected as zoo

# ---- locked bands -----------------------------------------------------------
H1_MIN_DISTINCT = 0.90          # CI lower bound >= this -> k<m dominant
H1Q_RATIO_BAND = (0.8, 1.2)     # observed repeat rate / sum(s_i^2)
H3_TOL = 0.002                  # |schedule-implied pi - stake-predicted pi|
H8_MIN_FRACTION = 0.99          # rounds with signed stake in [2/3, 2/3+s_max]
H2_STICKY_MARGIN = 0.15         # v1 band, unchanged
H2_IID_MARGIN = 0.05            # v1 band, unchanged
H2B_TOL = 0.05                  # |observed - heterogeneity-predicted| recurrence
H9_MIN_LIVE_STAKE = 0.98        # stake seen signing/proposing in the window
H9_MIN_EPOCH_FRACTION = 0.90
H10_MAX_FAILED = 0.01           # pooled fraction of rounds with a failed proposer
H6_MARGIN = 0.02                # learner mean coverage may not exceed mean pi by more
ZOO_VIEWS, ZOO_WARM = 600, 120
MC_VIEWS = 200_000              # Monte-Carlo length, closed-form self-check only


def bits_of(hexstr: str, n: int) -> list[int]:
    raw = bytes.fromhex(hexstr[2:])
    s = "".join(f"{b:08b}" for b in raw)
    return [i for i in range(min(n, len(s))) if s[i] == "1"]


def load_epoch(path: str) -> dict:
    raw = json.load(open(path))
    vals = sorted(raw["validators"], key=lambda v: v["index"])
    n = len(vals)
    total = sum(v["voting_power"] for v in vals)
    share = [v["voting_power"] / total for v in vals]
    addr_to_idx = {v["addr"]: v["index"] for v in vals}
    evs = sorted(raw["events"], key=lambda e: int(e["data"]["height"]))
    rounds = [{"round": e["data"]["round"], "proposer": e["data"]["proposer"],
               "previous_block_votes_bitvec": list(bytes.fromhex(e["data"]["previous_block_votes_bitvec"][2:])),
               "failed_proposer_indices": e["data"]["failed_proposer_indices"]} for e in evs]
    return {"epoch": raw["epoch"], "n": n, "share": share, "addr_to_idx": addr_to_idx,
            "rounds": rounds, "events": evs}


def schedule_pi(n: int, sched: list[int]) -> float:
    """Mean per-view demand-weighted persistence implied by a leader sequence
    under the hub-union model with full participation (frozen zoo helpers)."""
    prev, acc = None, []
    for t in range(len(sched) - 1):
        d = zoo.demand_of(n, sched, t)
        if prev is not None:
            acc.append(zoo.pi_of(d, prev))
        prev = set(d)
    return sum(acc) / len(acc)


def stake_predicted_pi(n: int, share: list[float]) -> float:
    """Exact E[pi_t] for i.i.d. stake-weighted leaders a,b,c = L(t-1),L(t),L(t+1).
    q = P(two draws collide), r = P(three collide). Cases: b=c -> 1 (single star
    inside S(t-1)); a=c!=b -> 1; a=b!=c -> n/(2(n-1)); all distinct -> pi(n,2,1)."""
    q = sum(x * x for x in share)
    r = sum(x ** 3 for x in share)
    return q + (q - r) + (q - r) * n / (2 * (n - 1)) + (1 - 3 * q + 2 * r) * (0.5 + 1 / (n - 1))


def _selfcheck_stake_pi() -> None:
    """Closed form vs brute-force Monte-Carlo through the frozen zoo helpers."""
    rng = random.Random(7)
    n = 12
    w = [rng.random() + 0.1 for _ in range(n)]
    share = [x / sum(w) for x in w]
    mc = schedule_pi(n, rng.choices(range(n), weights=share, k=MC_VIEWS))
    assert abs(mc - stake_predicted_pi(n, share)) < 2e-3, (mc, stake_predicted_pi(n, share))


def consecutive_runs(ep: dict) -> list[list[int]]:
    """Proposer-index sequences over maximal runs of consecutive round numbers."""
    runs, cur, last = [], [], None
    for r in ep["rounds"]:
        rn = int(r["round"])
        idx = ep["addr_to_idx"].get(r["proposer"])
        if idx is None or (last is not None and rn != last + 1):
            if len(cur) > 1:
                runs.append(cur)
            cur = []
        if idx is not None:
            cur.append(idx)
        last = rn
    if len(cur) > 1:
        runs.append(cur)
    return runs


def zoo_on_schedule(n: int, sched: list[int]) -> dict:
    """The frozen zoo's scoring loop (run()), driven by a real schedule."""
    views = min(ZOO_VIEWS, len(sched) - 4)
    preds = zoo.build(n, sched)
    acc = {p.name: [] for p in preds}
    viol = {"eq": 0, "gt": 0, "lt": 0, "checked": 0}
    pis, prev = [], None
    for t in range(views):
        d = zoo.demand_of(n, sched, t)
        S = set(d); B = len(S)
        if prev is not None and t >= ZOO_WARM:
            pi_t = zoo.pi_of(d, prev); pis.append(pi_t)
            for p in preds:
                sc = p.predict(t)
                c = zoo.coverage(sc, d, B) if sc else 0.0
                acc[p.name].append(c)
                if p.name in ("last", "ewma0.7"):
                    viol["checked"] += 1
                    if len(prev) == B and abs(c - pi_t) > 1e-12: viol["eq"] += 1
                    if len(prev) > B and c > pi_t + 1e-12: viol["gt"] += 1
                    if len(prev) < B and c < pi_t - 1e-12: viol["lt"] += 1
        for p in preds:
            p.observe(t, d)
        prev = S
    out = {k: sum(v) / len(v) for k, v in acc.items()}
    out["pi_mean"] = sum(pis) / len(pis)
    out["theoremB_violations"] = viol
    out["views_scored"] = len(pis)
    return out


def analyze_one(ep: dict, with_zoo: bool) -> dict:
    n, share, rounds = ep["n"], ep["share"], ep["rounds"]
    T = len(rounds)
    res = {"epoch": ep["epoch"], "n": n, "rounds": T}

    # H1 / H2-R: the v1-locked statistics, reused unmodified
    res["h1"] = analyze_proposer_rotation(rounds)
    res["h2"] = analyze_epoch(rounds, ep["addr_to_idx"])

    # H1q: stake-collision prediction of the repeat-leader rate
    res["sum_s2"] = sum(s * s for s in share)
    res["repeat_rate"] = 1.0 - res["h1"]["distinct_proposer_rate"]

    # H3: schedule-implied pi (longest consecutive run) vs stake-only prediction
    runs = consecutive_runs(ep)
    longest = max(runs, key=len)
    res["pi_schedule_implied"] = schedule_pi(n, longest)
    res["pi_stake_predicted"] = stake_predicted_pi(n, share)
    res["pi_generic_n21"] = 0.5 + 1.0 / (n - 1)
    res["consecutive_run_len"] = len(longest)
    res["lag2_repeat_rate"] = (sum(1 for i in range(len(longest) - 2) if longest[i] == longest[i + 2])
                               / max(1, len(longest) - 2))  # descriptive, no band

    # H8: quorum truncation
    signed = [bits_of(e["data"]["previous_block_votes_bitvec"], n) for e in ep["events"]]
    s_max = max(share)
    fr = [sum(share[i] for i in s) for s in signed if s]
    res["h8_fraction_in_band"] = sum(1 for f in fr if 2 / 3 - 1e-9 <= f <= 2 / 3 + s_max + 1e-9) / len(fr)
    res["signed_stake_min"], res["signed_stake_max"] = min(fr), max(fr)
    res["signed_stake_median"] = sorted(fr)[len(fr) // 2]
    res["signed_count_fraction_mean"] = sum(len(s) for s in signed if s) / (len(fr) * n)

    # H2b: static per-validator heterogeneity, estimated on the first half,
    # tested on the second half (no proposer exclusion on either side)
    absent = [set(range(n)) - set(s) for s in signed]
    h = T // 2
    a = [sum(i in A for A in absent[:h]) / h for i in range(n)]
    res["h2b_predicted"] = sum(x * x for x in a) / sum(a) if sum(a) else float("nan")
    num = sum(len(absent[t] & absent[t + 1]) for t in range(h, T - 1))
    den = sum(len(absent[t]) for t in range(h, T - 1))
    res["h2b_observed"] = num / den if den else float("nan")

    # H9: censoring-robust liveness lower bound
    live = set()
    for s in signed:
        live.update(s)
    live.update(ep["addr_to_idx"][r["proposer"]] for r in rounds if r["proposer"] in ep["addr_to_idx"])
    res["h9_live_count_fraction"] = len(live) / n
    res["h9_live_stake_fraction"] = sum(share[i] for i in live)

    # H10: production failure rate
    res["h10_failed_round_fraction"] = sum(1 for r in rounds if r["failed_proposer_indices"]) / T
    rn = [int(r["round"]) for r in rounds]
    res["round_gaps"] = sum(1 for i in range(T - 1) if rn[i + 1] != rn[i] + 1)

    if with_zoo and len(longest) >= ZOO_WARM + 50:
        res["h6"] = zoo_on_schedule(n, longest)
    return res


def ci(vals: list[float], seed: int) -> dict:
    if len(vals) < 5:
        return {"mean": sum(vals) / len(vals), "n": len(vals), "status": "underpowered_no_ci"}
    m, lo, hi = epoch_bootstrap_ci(vals, seed=seed)
    return {"mean": m, "lo": lo, "hi": hi, "n": len(vals)}


def main() -> int:
    _selfcheck_stake_pi()
    raw_dir, out_path = sys.argv[1], sys.argv[2]
    with_zoo = "--no-zoo" not in sys.argv
    files = sorted(glob.glob(os.path.join(raw_dir, "epoch_*.json")))
    per = []
    for f in files:
        r = analyze_one(load_epoch(f), with_zoo)
        per.append(r)
        print(f"epoch {r['epoch']}: n={r['n']} T={r['rounds']} distinct={r['h1']['distinct_proposer_rate']:.4f} "
              f"sum_s2={r['sum_s2']:.4f} h8={r['h8_fraction_in_band']:.4f} rec={r['h2']['absence_recurrence_rate']:.4f} "
              f"h2b obs/pred={r['h2b_observed']:.4f}/{r['h2b_predicted']:.4f} live_stake={r['h9_live_stake_fraction']:.4f} "
              f"failed={r['h10_failed_round_fraction']:.4f}", flush=True)

    V = {}
    d = ci([r["h1"]["distinct_proposer_rate"] for r in per], 1)
    V["H1"] = {**d, "verdict": "UNDERPOWERED" if "lo" not in d else
               ("K_LT_M_DOMINANT" if d["lo"] >= H1_MIN_DISTINCT else
                "K_EQ_M_DOMINANT" if d["hi"] <= 0.10 else "MIXED_REGIME")}

    d = ci([r["repeat_rate"] / r["sum_s2"] for r in per], 2)
    V["H1q"] = {**d, "pooled_repeat_rate": sum(r["repeat_rate"] for r in per) / len(per),
                "pooled_sum_s2": sum(r["sum_s2"] for r in per) / len(per),
                "verdict": "UNDERPOWERED" if "lo" not in d else
                ("STAKE_COLLISION_SUPPORTED" if H1Q_RATIO_BAND[0] <= d["lo"] and d["hi"] <= H1Q_RATIO_BAND[1]
                 else "STAKE_COLLISION_REFUTED" if d["hi"] < H1Q_RATIO_BAND[0] or d["lo"] > H1Q_RATIO_BAND[1]
                 else "INCONCLUSIVE")}

    d = ci([r["pi_schedule_implied"] - r["pi_stake_predicted"] for r in per], 3)
    V["H3"] = {**d, "mean_pi_schedule_implied": sum(r["pi_schedule_implied"] for r in per) / len(per),
               "mean_pi_stake_predicted": sum(r["pi_stake_predicted"] for r in per) / len(per),
               "mean_pi_generic": sum(r["pi_generic_n21"] for r in per) / len(per),
               "verdict": "UNDERPOWERED" if "lo" not in d else
               ("SUPPORTED" if -H3_TOL <= d["lo"] and d["hi"] <= H3_TOL else
                "REFUTED" if d["hi"] < -H3_TOL or d["lo"] > H3_TOL else "INCONCLUSIVE")}

    pooled_h8 = sum(r["h8_fraction_in_band"] * r["rounds"] for r in per) / sum(r["rounds"] for r in per)
    V["H8"] = {"pooled_fraction_in_band": pooled_h8,
               "signed_stake_min": min(r["signed_stake_min"] for r in per),
               "signed_stake_max": max(r["signed_stake_max"] for r in per),
               "verdict": "QUORUM_TRUNCATED" if pooled_h8 >= H8_MIN_FRACTION else "NOT_TRUNCATED"}

    h2 = [r for r in per if r["h2"].get("denominator", 0) > 0]
    d = ci([r["h2"]["absence_recurrence_rate"] for r in h2], 0)
    iid = sum(r["h2"]["predicted_iid_recurrence"] for r in h2) / len(h2)
    V["H2R"] = {**d, "mean_iid_predicted": iid, "verdict": "UNDERPOWERED" if "lo" not in d else
                ("IID" if d["lo"] <= iid <= d["hi"] or abs(d["mean"] - iid) <= H2_IID_MARGIN else
                 "NON_IID" if d["lo"] - iid >= H2_STICKY_MARGIN else "INCONCLUSIVE")}

    d = ci([r["h2b_observed"] - r["h2b_predicted"] for r in per], 4)
    V["H2b"] = {**d, "mean_observed": sum(r["h2b_observed"] for r in per) / len(per),
                "mean_predicted": sum(r["h2b_predicted"] for r in per) / len(per),
                "verdict": "UNDERPOWERED" if "lo" not in d else
                ("STATIC_HETEROGENEITY_EXPLAINS" if -H2B_TOL <= d["lo"] and d["hi"] <= H2B_TOL else
                 "TEMPORAL_MEMORY_BEYOND_HETEROGENEITY" if d["lo"] > H2B_TOL or d["hi"] < -H2B_TOL
                 else "INCONCLUSIVE")}

    ok = sum(1 for r in per if r["h9_live_stake_fraction"] >= H9_MIN_LIVE_STAKE) / len(per)
    V["H9"] = {"epochs_meeting_bound": ok,
               "min_live_stake": min(r["h9_live_stake_fraction"] for r in per),
               "mean_live_stake": sum(r["h9_live_stake_fraction"] for r in per) / len(per),
               "mean_live_count": sum(r["h9_live_count_fraction"] for r in per) / len(per),
               "verdict": "LIVENESS_BOUND_HOLDS" if ok >= H9_MIN_EPOCH_FRACTION else "LIVENESS_BOUND_FAILS"}

    pooled_fail = sum(r["h10_failed_round_fraction"] * r["rounds"] for r in per) / sum(r["rounds"] for r in per)
    V["H10"] = {"pooled_failed_round_fraction": pooled_fail,
                "total_round_gaps": sum(r["round_gaps"] for r in per),
                "verdict": "LOW_FAULT_RATE" if pooled_fail <= H10_MAX_FAILED else "FAULT_RATE_EXCEEDS_BAND"}

    z = [r["h6"] for r in per if "h6" in r]
    if z:
        learners = ["ewma0.5", "ewma0.7", "last", "freq", "markov1", "periodic"]
        h6 = {"epochs": len(z), "pi_mean": sum(x["pi_mean"] for x in z) / len(z)}
        worst = -1.0
        for name in learners + ["oracle"]:
            d = ci([x[name] - x["pi_mean"] for x in z], 5)
            h6[name] = {"mean_coverage": sum(x[name] for x in z) / len(z), "excess_over_pi": d}
            if name != "oracle":
                worst = max(worst, d.get("hi", d["mean"]))
        h6["theoremB_violations"] = {k: sum(x["theoremB_violations"][k] for x in z) for k in ("eq", "gt", "lt", "checked")}
        h6["verdict"] = ("NO_LEARNER_EXCEEDS_PI" if worst <= H6_MARGIN else "LEARNER_EXCEEDS_PI")
        V["H6"] = h6

    print("\n=== VERDICTS ===")
    for k, v in V.items():
        print(f"{k}: {v['verdict']}  " + json.dumps({a: b for a, b in v.items() if a != 'verdict' and not isinstance(b, dict)}))
    json.dump({"per_epoch": per, "verdicts": V}, open(out_path, "w"), indent=1)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
