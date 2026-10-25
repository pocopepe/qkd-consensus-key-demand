#!/usr/bin/env python3
"""POST HOC reanalysis (not pre-registered): the wide-area (E3c) and vote-loss (E3d) figures quoted in the paper,
recomputed with and without each run's final view, which the run's duration limit truncates. Same frozen analyser,
same adjacency-correct timeout-free transitions; the only change is dropping the final view.
Usage: reanalysis_final_view.py <out_json>   (needs raw_c_dedup/ and raw_d_dedup/, from e3c_dedup.py)"""
import glob, json, os, statistics as st, sys
from collections import defaultdict
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, "..", "..")); sys.path.insert(0, os.path.join(H, ".."))
from e1_analyze import D_CORE, analyze
from pi_p_model import pi_p_closed_form

def run(path, drop_last):
    d = json.load(open(path)); m = d["e3_meta"]; n = m["n"]; recs = [tuple(r) for r in d["records"]]
    tmo = {int(k) for k in d.get("timeout_views", {})}; props = {int(k): v for k, v in d["proposers"].items()}
    _, per = analyze(recs, n, D_CORE, m["tag"]); present = {r["view"][0] for r in per}; last = max(present)
    good = {r["view"][0]: r["pi"] for r in per if r["pi"] is not None and r["view"][0] not in tmo
            and (r["view"][0] - 1) in present and (r["view"][0] - 1) not in tmo and not (drop_last and r["view"][0] == last)}
    out = {"tag": m["tag"], "n": n, "silent": m.get("silent", []), "pi": st.mean(good.values()), "pi_full": 0.5 + 1 / (n - 1)}
    gv = set(good); cnt = lambda v: sum(1 for r in recs if r[4] == "Vote" and r[0] == v)
    out["p_vote"] = sum(cnt(v) for v in gv) / (len(gv) * (n - 1)); out["T"] = len(gv)
    out["missing"] = sum((n - 1) - cnt(v) for v in gv); out["missing_last"] = ((n - 1) - cnt(last)) if last in gv else 0
    if "role_" in m["tag"]:
        votes, tgt = defaultdict(set), {}
        for v, _, s, t, ty in recs:
            if ty == "Vote": votes[v].add(s); tgt[v] = t
        miss = defaultdict(int); T = nv = 0
        for v in good:
            if v not in props or (v - 1) not in props or v not in tgt: continue
            T += 1; nv += len(votes[v] - {tgt[v]})
            for x in set(range(1, n + 1)) - {tgt[v]} - votes[v]:
                miss["a" if x == props[v - 1] else "b" if x == props[v] else "g" if x == props.get(v + 2) else "o"] += 1
        mu2, mu1 = (miss["a"] + miss["g"]) / T, (miss["b"] + miss["o"]) / T
        out.update(prop1=(n + 1 - 2 * mu2 - mu1) / (2 * (n - 1) - mu2 - mu1), pip=pi_p_closed_form(n, nv / (T * (n - 1))), loss=mu2 + mu1)
    return out

def summarize(drop):
    c = [run(p, drop) for p in sorted(glob.glob(os.path.join(H, "raw_c_dedup", "wan_*.json")))]
    cells = {n: st.mean(r["pi"] for r in c if r["n"] == n) - (0.5 + 1 / (n - 1)) for n in (8, 16, 32, 64)}
    dd = [run(p, drop) for p in sorted(glob.glob(os.path.join(H, "raw_d_dedup", "*.json")))]
    lossy = [r for r in dd if r["loss"] >= 0.03]
    return {"wide_area_cell_residuals": cells, "wide_area_worst_run": max(abs(r["pi"] - r["pi_full"]) for r in c),
            "wide_area_min_participation": min(r["p_vote"] for r in c), "wide_area_runs_below_0999": sum(r["p_vote"] < 0.999 for r in c),
            "wide_area_missing_votes": sum(r["missing"] for r in c), "wide_area_missing_in_final_view": sum(r["missing_last"] for r in c),
            "wide_area_transitions": sum(r["T"] for r in c),
            "vote_loss_max_prop1_residual": max(abs(r["pi"] - r["prop1"]) for r in dd),
            "vote_loss_lossy_runs": len(lossy),
            "vote_loss_prop1_closest": sum(abs(r["pi"] - r["prop1"]) < min(abs(r["pi"] - r["pip"]), abs(r["pi"] - r["pi_full"])) for r in lossy),
            "vote_loss_mean_resid": {k: st.mean(abs(r["pi"] - r[k]) for r in lossy) for k in ("prop1", "pip", "pi_full")}}

if __name__ == "__main__":
    R = {"status": "POST HOC, not pre-registered", "with_final_view_as_locked": summarize(False), "final_view_dropped": summarize(True)}
    json.dump(R, open(sys.argv[1], "w"), indent=1); print(json.dumps(R, indent=1))
