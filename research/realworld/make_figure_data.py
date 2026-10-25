#!/usr/bin/env python3
# Writes FIGURE_DATA.json: the pgfplots coordinate lists of the real-world figures, from the result files.
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
out = {}

# paired wide-area residuals, one point per run
for name, fname in (("serial", "E3_RESULTS_DEDUP.json"), ("permsg", "E3C_RESULTS.json")):
    runs = [r for r in json.load(open(os.path.join(HERE, "e3", fname)))["runs"] if not r["silent"]]
    runs.sort(key=lambda r: (r["n"], r["tag"]))
    out[name] = " ".join(f"({r['n']},{r['pi_happy'] - r['pi_full']:.5f})" for r in runs)

# signed-stake histogram over all rounds, bin width 0.002
lo = 0.660
width = 0.002
nbins = 22
hist = [0] * nbins
total = 0
smax = 0
for path in sorted(glob.glob(os.path.join(HERE, "raw_v2", "epoch_*.json"))):
    d = json.load(open(path))
    vals = sorted(d["validators"], key=lambda v: v["index"])
    n = len(vals)
    power = sum(v["voting_power"] for v in vals)
    share = [v["voting_power"] / power for v in vals]
    smax = max(smax, max(share))
    for e in d["events"]:
        hx = e["data"]["previous_block_votes_bitvec"]
        bits = int(hx[2:], 16)
        wd = 4 * (len(hx) - 2)
        signed = sum(share[i] for i in range(n) if (bits >> (wd - 1 - i)) & 1)
        if signed <= 0:
            continue
        total += 1
        b = int((signed - lo) / width)
        if 0 <= b < nbins:
            hist[b] += 1
out["hist"] = " ".join(f"({lo + (i + 0.5) * width:.3f},{100 * c / total:.3f})" for i, c in enumerate(hist))
out["hist_total"] = total
out["hist_in_bins"] = sum(hist)
out["smax"] = smax

# per-epoch schedule-implied pi
per = sorted(json.load(open(os.path.join(HERE, "V2_RESULTS.json")))["per_epoch"], key=lambda r: r["epoch"])
out["epoch_pi"] = " ".join(f"({i + 1},{r['pi_schedule_implied']:.5f})" for i, r in enumerate(per))
out["epoch_pred"] = " ".join(f"({i + 1},{r['pi_stake_predicted']:.5f})" for i, r in enumerate(per))
out["epoch_generic"] = " ".join(f"({i + 1},{r['pi_generic_n21']:.5f})" for i, r in enumerate(per))

# held-out residual of each expression against votes lost per view (E3d)
runs = sorted(json.load(open(os.path.join(HERE, "e3", "E3D_RESULTS.json")))["runs"], key=lambda r: r["mu_a"] + r["mu_o"])
# eq. (11) as printed counts the votes lost by g with those of a: the three-role form of E3D_POSTHOC_ROLES.json.
# pi_role in E3D_RESULTS.json is the form first stated (g weighted one), which the pre-specified numbers in the text use.
role3 = {r["tag"]: r["pi_role3"] for r in json.load(open(os.path.join(HERE, "e3", "E3D_POSTHOC_ROLES.json")))["runs"]}
for name, key in (("role_full", "pi_full"), ("role_pip", "pi_p"), ("role_role", "pi_role3")):
    out[name] = " ".join(f"({r['mu_a'] + r['mu_o']:.4f},{r['pi_meas'] - (role3[r['tag']] if key == 'pi_role3' else r[key]):.5f})" for r in runs)

# E3c cell means
cells = json.load(open(os.path.join(HERE, "e3", "E3C_RESULTS.json")))["verdicts"]["P2_full_participation_theory"]["cells"]
out["e3c_cells"] = " ".join(f"({n},{v['pi_happy_mean']:.4f})" for n, v in cells.items())

json.dump(out, open(os.path.join(HERE, "FIGURE_DATA.json"), "w"), indent=1)
for k, v in out.items():
    if isinstance(v, str) and len(v) > 150:
        v = v[:150] + " ..."
    print(k, ":", v)
