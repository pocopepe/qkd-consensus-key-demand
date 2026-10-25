#!/usr/bin/env python3
"""POST-HOC (data already seen; not pre-registered). The stake-weighted corollary
fixes the distribution of the per-view value pi_t, hence how much the mean over a
window of T views should scatter. Predicted SD of a T-view window mean is obtained
by simulating i.i.d. stake-weighted leaders with each epoch's real stake vector
and the analytic per-view cases; compared with the SD of the 30 observed epochs."""
import glob, json, os, random, statistics as st
H = os.path.dirname(os.path.abspath(__file__))
per = {r["epoch"]: r for r in json.load(open(os.path.join(H, "V2_RESULTS.json")))["per_epoch"]}
def pv(a, b, c, n):
    if b == c or a == c: return 1.0
    if a == b: return n / (2 * (n - 1))
    return (n + 1) / (2 * (n - 1))
rng = random.Random(20260920); sims = []; obs = []
for p in sorted(glob.glob(os.path.join(H, "raw_v2", "epoch_*.json"))):
    d = json.load(open(p)); vals = sorted(d["validators"], key=lambda v: v["index"]); n = len(vals)
    w = [v["voting_power"] for v in vals]; T = per[d["epoch"]]["consecutive_run_len"]
    obs.append(per[d["epoch"]]["pi_schedule_implied"] - per[d["epoch"]]["pi_stake_predicted"])
    for _ in range(40):
        L = rng.choices(range(n), weights=w, k=T)
        m = st.mean(pv(L[t - 1], L[t], L[t + 1], n) for t in range(1, T - 1))
        sims.append(m - per[d["epoch"]]["pi_stake_predicted"])
out = {"observed_sd_across_epochs": st.pstdev(obs), "predicted_sd_window_mean": st.pstdev(sims),
       "ratio": st.pstdev(obs) / st.pstdev(sims), "observed_mean_offset": st.mean(obs), "simulated_mean_offset": st.mean(sims),
       "epochs": len(obs), "simulated_windows": len(sims)}
print(json.dumps(out, indent=1)); json.dump(out, open(os.path.join(H, "V2_POSTHOC_SPREAD.json"), "w"), indent=1)
