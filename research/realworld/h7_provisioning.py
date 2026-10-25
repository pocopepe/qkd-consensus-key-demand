#!/usr/bin/env python3
"""H7: the frozen E4 provisioning loop (research/e4_operational.py::run,
unmodified) driven by real Aptos leader sequences instead of synthetic hub
sets. Only the schedule source is swapped (hub_sequence is monkeypatched to
return the real hubs {L(t), L(t+1)}); pools, reservations, TTL, hit accounting
are the frozen code. Usage: h7_provisioning.py <raw_dir|SYNTH> <out_json>"""
from __future__ import annotations

import glob, json, os, random, statistics as st, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, ".."))
import e4_operational as e4
from v2_analyze import consecutive_runs, load_epoch, stake_predicted_pi

RATES = (256, 1024, 4096, 16384, 65536)     # the frozen Q1 sweep, 256x
VIEWS, WARM = 300, 40                        # the frozen Q1 settings
EPOCHS = 10                                  # first ten held-out epochs by number
FLAT_TOL = 0.005                             # locked: max-min hit rate over the sweep
CEIL_TOL = 0.02                              # locked: pair_carry_rate - 0.02 <= ceiling <= pair_carry_rate
# (the frozen loop arms only the first K_t pairs when the support shrinks, so
#  budget truncation can lose hits relative to the schedule-implied rate, never add)


def pair_carry_rate(n, leaders):
    """What the schedule alone implies for a last-observation pre-armer, with no
    pools or rates involved: a pair of view t is served from a reservation iff it
    was active in t-1 with at least as many incident hubs (a carried reservation
    sized for one hub cannot cover a pair that now joins two)."""
    def dem(t):
        d = {}
        for h in {leaders[t], leaders[t + 1]}:
            for j in range(n):
                if j != h:
                    q = (min(h, j), max(h, j)); d[q] = d.get(q, 0) + 1
        return d
    hit = tot = 0
    prev = {}
    for t in range(VIEWS):
        d = dem(t)
        hit += sum(1 for q, u in d.items() if prev.get(q, 0) >= u)
        tot += len(d)
        prev = d
    return hit / tot


def drive(n, leaders, R, predictor):
    seq = [sorted({leaders[t], leaders[t + 1]}) for t in range(VIEWS + 3)]
    e4.hub_sequence = lambda *_a, **_k: seq
    return e4.run(n, 2, 1, float(R), predictor, views=VIEWS, warm=WARM, seed=0)["hit_rate"]


def main():
    src, dst = sys.argv[1], sys.argv[2]
    eps = []
    if src == "SYNTH":   # development only: i.i.d. stake-weighted leaders, real stake vector
        ep = load_epoch(sorted(glob.glob(os.path.join(HERE, "sampleA_v2fmt", "epoch_*.json")))[0])
        rng = random.Random(5)
        eps = [(f"synth{i}", ep["n"], ep["share"], rng.choices(range(ep["n"]), weights=ep["share"], k=VIEWS + 4)) for i in range(2)]
    else:
        for p in sorted(glob.glob(os.path.join(src, "epoch_*.json")))[:EPOCHS]:
            ep = load_epoch(p)
            eps.append((ep["epoch"], ep["n"], ep["share"], max(consecutive_runs(ep), key=len)[:VIEWS + 4]))
    rows = []
    for name, n, share, leaders in eps:
        carry = [drive(n, leaders, R, "carry") for R in RATES]
        structural = drive(n, leaders, RATES[-1], "structural")
        rows.append({"epoch": name, "n": n, "carry_by_R": carry, "ceiling": max(carry), "spread": max(carry) - min(carry),
                     "structural_at_max_R": structural, "pair_carry_rate": pair_carry_rate(n, leaders),
                     "pi_stake": stake_predicted_pi(n, share)})
        print(rows[-1], flush=True)
    flat = max(r["spread"] for r in rows)
    ceil_err = max(abs(r["ceiling"] - r["pair_carry_rate"]) for r in rows)
    above = max(r["ceiling"] - r["pair_carry_rate"] for r in rows)
    V = {"max_spread_over_256x": flat, "max_abs_ceiling_minus_pair_carry_rate": ceil_err,
         "mean_pair_carry_rate": st.mean(r["pair_carry_rate"] for r in rows),
         "mean_ceiling": st.mean(r["ceiling"] for r in rows), "mean_pi_stake": st.mean(r["pi_stake"] for r in rows),
         "min_structural": min(r["structural_at_max_R"] for r in rows),
         "verdict_flat": "SUPPORTED" if flat <= FLAT_TOL else "REFUTED",
         "max_ceiling_above_schedule_rate": above,
         "verdict_ceiling": "SUPPORTED" if ceil_err <= CEIL_TOL and above <= 1e-9 else "REFUTED",
         "verdict_structural": "SUPPORTED" if min(r["structural_at_max_R"] for r in rows) >= 0.999 else "REFUTED"}
    print(json.dumps(V, indent=1))
    json.dump({"rows": rows, "verdicts": V}, open(dst, "w"), indent=1)


if __name__ == "__main__":
    main()
