#!/usr/bin/env python3
"""Activity-weighted Corollary 2 (AIP-1 proposer selection). Usage: cor2_activity.py <raw_dir> <out_json> [thr]

AIP-1 (ProposerAndVoterV2): for round r, a validator's reputation weight is
  failed_weight 1     if its proposer failure rate over rounds (r-10n-20, r-20] is above THR,
  inactive_weight 10  if it had no proposer rounds there and no quorum-certificate votes over (r-n-20, r-20],
  active_weight 1000  otherwise,
multiplied by its stake; the leader is drawn independently in every round with probability proportional to that.
Per evaluated round: s(r) = weights normalised; predicted repeat probability sum_i s_i(r-1) s_i(r); Corollary 2
(v2_analyze.stake_predicted_pi) at s(r). The stake-only version is computed on the same rounds for comparison.
Only rounds whose whole proposer window lies inside the fetched data are evaluated. Epoch-bootstrap intervals use
v2_analyze.ci. The failure threshold THR is not given in AIP-1; it is calibrated on the v2 epochs only."""
import glob, json, os, sys
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import v2_analyze as v2a

W_FAILED, W_INACTIVE, W_ACTIVE = 1, 10, 1000

def epoch_stats(args):
    path, thr = args
    ep = v2a.load_epoch(path); n, share = ep["n"], ep["share"]; A = ep["addr_to_idx"]
    evs = ep["events"]; R = [int(e["data"]["round"]) for e in evs]
    prop = [A.get(e["data"]["proposer"]) for e in evs]
    fails = [[int(x) for x in e["data"]["failed_proposer_indices"]] for e in evs]
    votes = [v2a.bits_of(e["data"]["previous_block_votes_bitvec"], n) for e in evs]   # votes for the previous round
    pw, vw = 10 * n + 20, n + 20
    evald = []   # (j, s_j)
    for j in range(len(evs)):
        r = R[j]
        if r - pw < R[0]: continue
        succ = [0] * n; fl = [0] * n; vt = [0] * n
        for i in range(j - 1, -1, -1):
            if R[i] <= r - pw: break
            if R[i] > r - 20: continue
            if prop[i] is not None: succ[prop[i]] += 1
            for x in fails[i]:
                if x < n: fl[x] += 1
            if R[i] > r - vw:
                for x in votes[i]: vt[x] += 1
        w = []
        for v in range(n):
            tot = succ[v] + fl[v]
            cls = W_FAILED if tot and fl[v] / tot > thr else W_INACTIVE if tot == 0 and vt[v] == 0 else W_ACTIVE
            w.append(share[v] * cls)
        z = sum(w); evald.append((j, [x / z for x in w]))
    idx = {j: s for j, s in evald}
    pairs = [(j, idx[j - 1], idx[j]) for j, _ in evald if j - 1 in idx and R[j] == R[j - 1] + 1 and prop[j] is not None and prop[j - 1] is not None]
    obs_rep = sum(prop[j] == prop[j - 1] for j, _, _ in pairs)
    pred_act = sum(sum(a * b for a, b in zip(s0, s1)) for _, s0, s1 in pairs)
    pred_stake = len(pairs) * sum(x * x for x in share)
    # longest consecutive run inside the evaluated rounds, for schedule persistence
    runs, cur = [], []
    for j, _ in evald:
        if cur and (R[j] != R[cur[-1]] + 1 or prop[j] is None): runs.append(cur); cur = []
        if prop[j] is not None: cur.append(j)
    runs.append(cur); run = max(runs, key=len)
    sched = [prop[j] for j in run]
    return {"epoch": ep["epoch"], "n": n, "rounds_evaluated": len(evald), "pairs": len(pairs), "run_len": len(run),
            "repeat_observed": obs_rep, "repeat_pred_activity": pred_act, "repeat_pred_stake": pred_stake,
            "pi_schedule": v2a.schedule_pi(n, sched),
            "pi_cor2_activity": sum(v2a.stake_predicted_pi(n, idx[j]) for j in run) / len(run),
            "pi_cor2_stake": v2a.stake_predicted_pi(n, share),
            "inactive_share_mean": sum(sum(1 for x in s if x < max(s) * 0.05) for _, s in evald) / len(evald) / n}

def summarize(per):
    ci = lambda vals, seed: v2a.ci(vals, seed)
    return {"epochs": len(per),
            "ratio_activity": ci([p["repeat_observed"] / p["repeat_pred_activity"] for p in per], 11),
            "ratio_stake": ci([p["repeat_observed"] / p["repeat_pred_stake"] for p in per], 12),
            "diff_activity": ci([p["pi_schedule"] - p["pi_cor2_activity"] for p in per], 13),
            "diff_stake": ci([p["pi_schedule"] - p["pi_cor2_stake"] for p in per], 14),
            "ratio_gain": ci([p["repeat_observed"] / p["repeat_pred_stake"] - p["repeat_observed"] / p["repeat_pred_activity"] for p in per], 16),
            "abs_gain": ci([abs(p["pi_schedule"] - p["pi_cor2_stake"]) - abs(p["pi_schedule"] - p["pi_cor2_activity"]) for p in per], 15)}

if __name__ == "__main__":
    thr = float(sys.argv[3]) if len(sys.argv) > 3 else 0.10
    files = sorted(glob.glob(os.path.join(sys.argv[1], "epoch_*.json")))
    with Pool(int(os.environ.get("WORKERS", "10"))) as p: per = p.map(epoch_stats, [(f, thr) for f in files])
    S = summarize(per); json.dump({"threshold": thr, "per_epoch": per, "summary": S}, open(sys.argv[2], "w"), indent=1)
    print(json.dumps({"threshold": thr, **S}, indent=1))
