#!/usr/bin/env python3
"""POST HOC, NOT PRE-REGISTERED. Usage: e3d_posthoc_roles.py <dedup_raw_d_dir> <out_json>

The locked E3d analysis (e3d_analyze.py) splits missing votes into the previous
leader L(t-1) and "anyone else". role_loss_check.py shows that a vote missing
from L(t+2) also removes two carried units, so the first-order expression has a
second double-cost role. This script re-splits the SAME transitions into four
roles and evaluates

  pi_role3 = (n+1 - 2*(mu_prev+mu_next2) - mu_one) / (2(n-1) - mu_prev - mu_next2 - mu_one)

next to the locked two-role value. It changes no locked verdict."""
import glob, json, os, statistics as st, sys
from collections import defaultdict
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(H, "..", "..")); sys.path.insert(0, os.path.join(H, ".."))
from e1_analyze import D_CORE, analyze

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
    miss = defaultdict(int); T = 0
    for v in good:
        if v not in props or (v - 1) not in props or v not in tgt: continue
        T += 1
        nxt2 = props.get(v + 2)                     # None when view v+2 has no logged proposer
        for x in set(range(1, n + 1)) - {tgt[v]} - votes[v]:
            miss["prev" if x == props[v - 1] else "cur" if x == props[v] else "next2" if x == nxt2 else "other"] += 1
    mu = {k: miss[k] / T for k in ("prev", "cur", "next2", "other")}
    two, one = mu["prev"] + mu["next2"], mu["cur"] + mu["other"]
    rest = mu["cur"] + mu["next2"] + mu["other"]
    return {"tag": d["e3_meta"]["tag"], "n": n, "transitions": T, "pi_meas": st.mean(good.values()),
            "pi_role_locked": (n + 1 - 2 * mu["prev"] - rest) / (2 * (n - 1) - mu["prev"] - rest),
            "pi_role3": (n + 1 - 2 * two - one) / (2 * (n - 1) - two - one), "missing": dict(miss)}

def main():
    rows = [run(p) for p in sorted(glob.glob(os.path.join(sys.argv[1], "*.json")))]
    tot = defaultdict(int)
    for r in rows:
        for k, v in r["missing"].items(): tot[k] += v
    e2 = [abs(r["pi_meas"] - r["pi_role_locked"]) for r in rows]; e3 = [abs(r["pi_meas"] - r["pi_role3"]) for r in rows]
    out = {"status": "POST HOC, not pre-registered", "runs": rows, "missing_by_role": dict(tot), "missing_total": sum(tot.values()),
           "max_abs_resid": {"two_role_locked": max(e2), "three_role": max(e3)},
           "mean_abs_resid": {"two_role_locked": st.mean(e2), "three_role": st.mean(e3)},
           "max_abs_change_between_forms": max(abs(r["pi_role3"] - r["pi_role_locked"]) for r in rows)}
    print(json.dumps({k: v for k, v in out.items() if k != "runs"}, indent=1))
    json.dump(out, open(sys.argv[2], "w"), indent=1)

if __name__ == "__main__":
    main()
