#!/usr/bin/env python3
# The QKD key budget of production chains under one 128-bit tag per consensus message per recipient. Inputs and
# sources in inputs.json. Supply side: a trusted-relay ring with one validator per node gives every pair 8R/n^2
# bit/s (even n; (n^2-1)/8 pairs per link for odd n), so the link rate a chain needs is its per-pair demand times
# n^2/8, and the decision rate a link of rate R sustains is 8R / (n^2 * tags per pair per decision * 128).
# usage: budget.py [out.json]
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
I = json.load(open(os.path.join(HERE, "inputs.json")))
TAG = I["tag_bits"]


def tags_per_decision(c):
    n = c["n"]
    env = {"n": n, "N": n, "K": I["K"], "BETA": I["BETA"]}
    return eval(c["pattern"].replace("^", "**"), {}, env)


def pairs_per_cut_link(n):
    return n * n / 8 if n % 2 == 0 else (n * n - 1) / 8


def selfcheck():
    assert tags_per_decision({"n": 84, "pattern": "(2n+1)(n-1)".replace("(2n+1)(n-1)", "(2*n+1)*(n-1)")}) == 169 * 83
    assert abs(8 * 2.22e6 / 84 ** 2 - 2 * 2.22e6 / pairs_per_cut_link(84) / 2) < 1e-9


if __name__ == "__main__":
    rows = []
    for c in I["chains"]:
        n = c["n"]
        c = dict(c)
        c["pattern_py"] = c["pattern"].replace("(2n+1)(n-1)", "(2*n+1)*(n-1)").replace("2n(n-1)+(n-1)", "2*n*(n-1)+(n-1)").replace("n(n-1)", "n*(n-1)").replace("2(n-1)", "2*(n-1)")
        T = eval(c["pattern_py"], {}, {"n": n, "N": n, "K": I["K"], "BETA": I["BETA"]})
        pairs = n * (n - 1) // 2
        per_pair = T / pairs
        row = {"chain": c["chain"], "protocol": c["protocol"], "n": n, "tags_per_decision": T, "pairs": pairs,
               "tags_per_pair_per_decision": per_pair, "key_bits_per_decision": T * TAG,
               "rate_per_s": c["rate_per_s"], "rate_src": c["rate_src"], "pattern": c["pattern"], "pattern_src": c["pattern_src"]}
        if c["rate_per_s"]:
            row["key_bit_per_s"] = T * TAG * c["rate_per_s"]
            row["ring_link_bit_per_s_needed"] = per_pair * TAG * c["rate_per_s"] * pairs_per_cut_link(n)
        for name, R in I["links"].items():
            row[f"sustainable_decisions_per_s_{name}"] = R / pairs_per_cut_link(n) / (per_pair * TAG)
        rows.append(row)
    out = {"note": I["note"], "tag_bits": TAG, "links": I["links"], "rows": rows}
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "CHAIN_BUDGET.json"), "w"), indent=1)
    print(f"{'chain':11} {'n':>7} {'tags/dec':>12} {'rate/s':>8} {'key bit/s':>12} {'link needed':>12} {'max dec/s @2.22M':>16} {'@1.8k':>10}")
    for r in rows:
        rate = f"{r['rate_per_s']:.3g}" if r["rate_per_s"] else "-"
        kb = f"{r['key_bit_per_s']:.3g}" if r.get("key_bit_per_s") else "-"
        ln = f"{r['ring_link_bit_per_s_needed']:.3g}" if r.get("ring_link_bit_per_s_needed") else "-"
        print(f"{r['chain']:11} {r['n']:7d} {r['tags_per_decision']:12.0f} {rate:>8} {kb:>12} {ln:>12} {r['sustainable_decisions_per_s_megabit']:16.3g} {r['sustainable_decisions_per_s_kilobit']:10.3g}")
