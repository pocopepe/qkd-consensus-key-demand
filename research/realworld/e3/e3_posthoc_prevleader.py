#!/usr/bin/env python3
"""POST-HOC / EXPLORATORY on E3 (not pre-registered). Vote loss in E3 was
concentrated on the previous leader a=L(t-1) (an emulator artefact, see
PREDICTION_LOCK_E3C.md). Under chained rotation with complete proposal stars,
a missing vote from a removes one carried vote edge {a,c} now AND one carried
proposal edge next view; a missing vote from anyone else removes only the
latter. With mu_a, mu_o = such misses per view:
    pi = (n+1 - 2 mu_a - mu_o) / (2(n-1) - mu_a - mu_o)
Compared with pi(n,2,1) and the i.i.d. pi_p on the same runs."""
import glob, json, os, sys
from collections import defaultdict
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(H, ".."))
from pi_p_model import pi_p_closed_form
res = {r["tag"]: r for r in json.load(open(os.path.join(H, "E3_RESULTS_DEDUP.json")))["runs"]}
rows = []
for p in sorted(glob.glob(os.path.join(H, "raw_dedup", "wan_*.json"))):
    d = json.load(open(p)); n = d["e3_meta"]["n"]; tag = d["e3_meta"]["tag"]
    props = {int(k): v for k, v in d["proposers"].items()}; tmo = {int(k) for k in d["timeout_views"]}
    votes, tgt = defaultdict(set), {}
    for v, _, s, t, ty in d["records"]:
        if ty == "Vote": votes[v].add(s); tgt[v] = t
    T = ma = mo = 0
    for v in votes:
        if v in tmo or (v - 1) in tmo or v not in props or (v - 1) not in props: continue
        T += 1
        for x in set(range(1, n + 1)) - {tgt[v]} - votes[v]:
            if x == props[v - 1]: ma += 1
            else: mo += 1
    mu_a, mu_o = ma / T, mo / T
    r = res[tag]
    rows.append({"tag": tag, "n": n, "pi_meas": r["pi_happy"], "pi_full": r["pi_full"], "pi_p": r["pi_p"],
                 "pi_struct": (n + 1 - 2 * mu_a - mu_o) / (2 * (n - 1) - mu_a - mu_o), "mu_a": mu_a, "mu_o": mu_o})
for k in ("pi_full", "pi_p", "pi_struct"):
    e = [abs(x["pi_meas"] - x[k]) for x in rows]
    print(f"{k:10s} mean|resid|={sum(e)/len(e):.5f}  max={max(e):.5f}")
lossy = [x for x in rows if x["mu_a"] + x["mu_o"] > 0.03]
print("runs with >0.03 missing votes per view:", [(x["tag"], round(x["pi_meas"], 4), round(x["pi_full"], 4), round(x["pi_p"], 4), round(x["pi_struct"], 4)) for x in lossy])
json.dump(rows, open(os.path.join(H, "E3_POSTHOC_PREVLEADER.json"), "w"), indent=1)
