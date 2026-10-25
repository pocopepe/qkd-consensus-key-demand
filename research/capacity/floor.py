#!/usr/bin/env python3
# The key floor of pairwise (non-transferable) authentication, from THEOREM.md draft 2, against the seven chains of
# research/realworld/chains/CHAIN_BUDGET.json. Floor per view with latency L views in a deviation-free execution:
# n(f + 1)/L tags verified, f = floor((n-1)/3).
# T2: a party deciding on tags of k parties sampled without replacement from the n - 1 others, all corrupt for the
# T1 attack: error at least C(f, k)/C(n - 1, k); an alpha-of-k rule needs alpha corrupt among the k (hypergeometric
# tail). Reported for the model only, not applied to any chain. usage: floor.py [out.json]
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
B = json.load(open(os.path.join(HERE, "..", "realworld", "chains", "CHAIN_BUDGET.json")))
TAG = 128


def f_of(n):
    return (n - 1) // 3


def floor_tags(n, L=1):
    f = f_of(n)
    return n * (f + 1) / L


def hypergeom_tail(n, f, k, a):
    # P[at least a of k draws without replacement from n are among the f corrupt]
    tot = 0.0
    for j in range(a, k + 1):
        tot += math.comb(f, j) * math.comb(n - f, k - j) / math.comb(n, k)
    return tot


def selfcheck():
    assert floor_tags(84) == 84 * 28
    assert abs(hypergeom_tail(10, 3, 3, 3) - 1 / 120) < 1e-12
    assert abs(hypergeom_tail(590, 196, 1, 1) - 196 / 590) < 1e-12


if __name__ == "__main__":
    selfcheck()
    rows = []
    for r in B["rows"]:
        n = r["n"]
        f = f_of(n)
        fl = floor_tags(n)
        row = {"chain": r["chain"], "n": n, "f": f, "floor_tags_per_view_L1": fl, "tags_per_decision": r["tags_per_decision"],
               "ratio_to_floor_L1": r["tags_per_decision"] / fl,
               "max_L_at_which_pattern_is_below_floor": math.floor((fl / r["tags_per_decision"]) - 1e-12) if r["tags_per_decision"] < fl else 0}
        rows.append(row)
    t2 = {}
    for n in (84, 590):
        f = f_of(n)
        t2[str(n)] = {"f": f, "k20_all_corrupt": hypergeom_tail(n - 1, f, 20, 20), "k20_15_of_20_corrupt": hypergeom_tail(n - 1, f, 20, 15),
                      "k_for_1e-9": next(k for k in range(1, f + 1) if math.comb(f, k) / math.comb(n - 1, k) <= 1e-9)}
    stake = {"aptos": {"n": 84, "smallest_count_over_third": 14, "src": "raw_v3 epoch stakes, 10 epochs, all 14"},
             "solana": {"n": 672, "smallest_count_over_third": 18, "src": "chains/solana_stake.json (18 of 673 at the stake query; n = 672 as in the chain table, one validator fewer at the earlier query)"}}
    for c in stake.values():
        c["floor_L1"] = c["n"] * c["smallest_count_over_third"]
        c["hybrid_L_threshold"] = c["floor_L1"] / (2 * (c["n"] - 1))
    stake["aptos"]["broadcast_ratio_to_stake_floor"] = 14027 / stake["aptos"]["floor_L1"]
    out = {"tag_bits": TAG, "rows": rows, "t2_model_only": t2, "stake_weighted": stake,
           "n84": {"f": f_of(84), "floor_L1": floor_tags(84), "broadcast_ratio": 85 * 83 / floor_tags(84),
                   "hybrid_L_threshold": floor_tags(84) / (2 * 83), "ithotstuff_ratio": 8 * 83 / 28,
                   "limit_ratio_f_to_n_over_3": 3.0}}
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "FLOOR_RESULTS.json"), "w"), indent=1)
    for r in rows:
        print(f"{r['chain']:11} n={r['n']:7d} f={r['f']:6d} floor(L=1)={r['floor_tags_per_view_L1']:14.0f} pattern={r['tags_per_decision']:10.0f} ratio={r['ratio_to_floor_L1']:8.3f} below-floor up to L={r['max_L_at_which_pattern_is_below_floor']}")
    print("t2 (model only)", json.dumps(t2))
    print("n84", json.dumps(out["n84"]))
    print("stake", json.dumps(stake))
