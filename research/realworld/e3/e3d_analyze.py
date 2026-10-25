#!/usr/bin/env python3
"""E3d analysis. Usage: e3d_analyze.py <dedup_raw_dir> <out_json>

Per run, on adjacency-correct timeout-free transitions (as in E3/E3c):
  mu_a = missing votes per view from the previous leader L(t-1)
  mu_o = missing votes per view from anyone else
  pi_role = (n+1 - 2*mu_a - mu_o) / (2(n-1) - mu_a - mu_o)
compared with the frozen analyser's measured pi, with pi(n,2,1) and with the
role-blind pi_p(n, p). Bands are constants, hashed before any E3d run."""
import glob, json, os, statistics as st, sys
from collections import defaultdict
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, "..", "..")); sys.path.insert(0, os.path.join(H, ".."))
from e1_analyze import D_CORE, analyze
from pi_p_model import pi_p_closed_form
R1_TOL = 0.002            # |pi_role - measured| in EVERY run
R2_MIN_LOSS = 0.03        # "lossy" run: missing votes per view
R2_MIN_WIN = 0.80         # pi_role closest of the three in this share of lossy runs ...
R2_MAX_RATIO = 0.5        # ... AND its mean |residual| at most this fraction of pi_p's and of pi(n,2,1)'s
R3_MIN_PREV_SHARE = 0.60  # pooled share of missing votes that come from the previous leader

def run(path):
    d = json.load(open(path)); n = d["e3_meta"]["n"]; recs = [tuple(r) for r in d["records"]]
    tmo = {int(k) for k in d.get("timeout_views", {})}; props = {int(k): v for k, v in d["proposers"].items()}
    _, per = analyze(recs, n, D_CORE, d["e3_meta"]["tag"])
    present = {r["view"][0] for r in per}
    good = {r["view"][0]: r["pi"] for r in per if r["pi"] is not None and r["view"][0] not in tmo
            and (r["view"][0] - 1) in present and (r["view"][0] - 1) not in tmo}
    votes, tgt = defaultdict(set), {}
    for v, _, s, t, ty in recs:
        if ty == "Vote": votes[v].add(s); tgt[v] = t
    ma = mo = T = nv = 0
    for v in good:
        if v not in props or (v - 1) not in props or v not in tgt: continue
        T += 1; nv += len(votes[v] - {tgt[v]})
        for x in set(range(1, n + 1)) - {tgt[v]} - votes[v]:
            if x == props[v - 1]: ma += 1
            else: mo += 1
    mu_a, mu_o = ma / T, mo / T
    meas = st.mean(good.values()); full = 0.5 + 1 / (n - 1)
    return {"tag": d["e3_meta"]["tag"], "n": n, "transitions": T, "pi_meas": meas, "pi_full": full,
            "pi_p": pi_p_closed_form(n, nv / (T * (n - 1))), "pi_role": (n + 1 - 2 * mu_a - mu_o) / (2 * (n - 1) - mu_a - mu_o),
            "mu_a": mu_a, "mu_o": mu_o, "missing_prev": ma, "missing_other": mo}

def main():
    rows = [run(p) for p in sorted(glob.glob(os.path.join(sys.argv[1], "*.json")))]
    for r in rows: print({k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
    err = {k: [abs(r["pi_meas"] - r[k]) for r in rows] for k in ("pi_full", "pi_p", "pi_role")}
    lossy = [r for r in rows if r["mu_a"] + r["mu_o"] >= R2_MIN_LOSS]
    wins = sum(1 for r in lossy if abs(r["pi_meas"] - r["pi_role"]) < min(abs(r["pi_meas"] - r["pi_full"]), abs(r["pi_meas"] - r["pi_p"])))
    prev = sum(r["missing_prev"] for r in rows); tot = prev + sum(r["missing_other"] for r in rows)
    V = {"R1_role_formula_fits": {"max_abs_residual": max(err["pi_role"]), "mean_abs_residual": st.mean(err["pi_role"]), "runs": len(rows),
                                  "verdict": "SUPPORTED" if max(err["pi_role"]) <= R1_TOL else "REFUTED"},
         "R2_beats_role_blind": {"lossy_runs": len(lossy), "wins": wins,
                                 "lossy_max_resid": {k: max(abs(r["pi_meas"] - r[k]) for r in lossy) if lossy else None for k in ("pi_full", "pi_p", "pi_role")},
                                 "lossy_mean_resid": {k: st.mean(abs(r["pi_meas"] - r[k]) for r in lossy) if lossy else None for k in ("pi_full", "pi_p", "pi_role")},
                                 "verdict": "NOT_TESTABLE" if len(lossy) < 5 else ("SUPPORTED" if wins / len(lossy) >= R2_MIN_WIN
                                     and st.mean(abs(r["pi_meas"] - r["pi_role"]) for r in lossy) <= R2_MAX_RATIO * min(
                                         st.mean(abs(r["pi_meas"] - r["pi_p"]) for r in lossy), st.mean(abs(r["pi_meas"] - r["pi_full"]) for r in lossy))
                                     else "REFUTED")},
         "R3_previous_leader_share": {"missing_prev": prev, "missing_total": tot, "share": prev / tot if tot else None,
                                      "verdict": "NOT_TESTABLE" if tot < 50 else ("SUPPORTED" if prev / tot >= R3_MIN_PREV_SHARE else "REFUTED")}}
    print("\n=== E3d VERDICTS ===")
    for k, v in V.items(): print(k, v["verdict"], json.dumps({a: b for a, b in v.items() if a != "verdict"}))
    json.dump({"runs": rows, "verdicts": V}, open(sys.argv[2], "w"), indent=1)

if __name__ == "__main__":
    main()
