#!/usr/bin/env python3
"""POST-HOC / EXPLORATORY (written after V2_RESULTS.json was seen; not
pre-registered; nothing here changes a locked verdict).

Q1. H1q's ratio CI [1.015,1.155] sits inside the locked band but excludes 1.
    Aptos leader reputation down-weights inactive validators. Does
    renormalising stake over validators actually seen active in the window
    remove the excess?
Q2. What share of the recurrence gap over IID does static heterogeneity explain?
Q3. pi bracket implied by never-seen validators (count-based p)."""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_aptos_bitvecs import epoch_bootstrap_ci
from pi_p_model import pi_p_closed_form

res = {r["epoch"]: r for r in json.load(open(os.path.join(HERE, "V2_RESULTS.json")))["per_epoch"]}
ratios, never_cnt, never_stake, pi_lb = [], [], [], []
for p in sorted(glob.glob(os.path.join(HERE, "raw_v2", "epoch_*.json"))):
    d = json.load(open(p)); vals = sorted(d["validators"], key=lambda v: v["index"]); n = len(vals)
    idx = {v["addr"]: v["index"] for v in vals}
    seen = set()
    for e in d["events"]:
        hx = e["data"]["previous_block_votes_bitvec"]; x = int(hx[2:], 16); w = 4 * (len(hx) - 2)
        seen |= {i for i in range(n) if (x >> (w - 1 - i)) & 1}
        if e["data"]["proposer"] in idx: seen.add(idx[e["data"]["proposer"]])
    tot = sum(v["voting_power"] for v in vals)
    act = sum(vals[i]["voting_power"] for i in seen)
    q_active = sum(vals[i]["voting_power"] ** 2 for i in seen) / act ** 2
    r = res[d["epoch"]]
    ratios.append(r["repeat_rate"] / q_active)
    never_cnt.append(n - len(seen)); never_stake.append(1 - act / tot)
    pi_lb.append(pi_p_closed_form(n, (len(seen) - 1) / (n - 1)))
m, lo, hi = epoch_bootstrap_ci(ratios, seed=11)
print(f"Q1 repeat-rate / sum s^2 over ACTIVE stake: mean {m:.4f} CI [{lo:.4f}, {hi:.4f}]  (locked H1q, all stake: 1.0845 [1.0147, 1.1554])")
obs = sum(r["h2b_observed"] for r in res.values()) / len(res); pred = sum(r["h2b_predicted"] for r in res.values()) / len(res)
iid = sum(r["h2"]["predicted_iid_recurrence"] for r in res.values()) / len(res)
print(f"Q2 heterogeneity explains {(pred - iid) / (obs - iid):.1%} of the recurrence gap over IID ({iid:.4f} -> {pred:.4f} of {obs:.4f})")
print(f"Q3 never-seen validators per epoch: min {min(never_cnt)} max {max(never_cnt)}; stake {min(never_stake):.4f}..{max(never_stake):.4f}")
print(f"   pi_p with p = (seen-1)/(n-1): mean {sum(pi_lb)/len(pi_lb):.4f}  vs pi(n,2,1) ~ 0.5120")
json.dump({"q1_ratio_active": [m, lo, hi], "q2_share_explained": (pred - iid) / (obs - iid),
           "never_seen_count": never_cnt, "never_seen_stake": never_stake, "pi_p_seen_mean": sum(pi_lb) / len(pi_lb)},
          open(os.path.join(HERE, "V2_POSTHOC.json"), "w"), indent=1)
