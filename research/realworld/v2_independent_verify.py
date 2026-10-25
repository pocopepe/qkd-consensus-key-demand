#!/usr/bin/env python3
"""Independent recomputation of the campaign-v2 per-epoch statistics.

Imports NOTHING from v2_analyze.py, fetch_aptos_bitvecs.py or the predictor
zoo. Written and hashed before the locked analysis was run on held-out data.
Different mechanisms on purpose: integer bit arithmetic instead of string
decoding, an analytic (a,b,c) case formula for per-view persistence instead of
building edge dictionaries, exact rational closed form via fractions.

Usage: v2_independent_verify.py <raw_dir> [<v2_analyze_output.json>]
"""
from __future__ import annotations

import glob
import json
import os
import sys
from fractions import Fraction


def signer_set(hexstr: str, n: int) -> frozenset[int]:
    x = int(hexstr[2:], 16)
    width = 4 * (len(hexstr) - 2)
    return frozenset(i for i in range(n) if (x >> (width - 1 - i)) & 1)  # MSB-first


def per_view_pi(a: int, b: int, c: int, n: int) -> Fraction:
    if b == c or a == c:
        return Fraction(1)
    if a == b:
        return Fraction(n, 2 * (n - 1))
    return Fraction(n + 1, 2 * (n - 1))


def recompute(path: str) -> dict:
    raw = json.load(open(path))
    vals = {v["index"]: v for v in raw["validators"]}
    n = len(vals)
    total = sum(v["voting_power"] for v in vals.values())
    share = [Fraction(vals[i]["voting_power"], total) for i in range(n)]
    idx = {v["addr"]: i for i, v in vals.items()}
    evs = sorted(raw["events"], key=lambda e: int(e["data"]["height"]))
    rnd = [int(e["data"]["round"]) for e in evs]
    prop = [idx.get(e["data"]["proposer"]) for e in evs]
    sig = [signer_set(e["data"]["previous_block_votes_bitvec"], n) for e in evs]
    T = len(evs)

    # H1: distinct proposer over pairs of consecutive round numbers
    pairs = [(prop[i], prop[i + 1]) for i in range(T - 1) if rnd[i + 1] == rnd[i] + 1]
    distinct = sum(1 for x, y in pairs if x != y) / len(pairs)

    # H1q / H3 closed form, exact rationals
    q = sum(s * s for s in share)
    r3 = sum(s ** 3 for s in share)
    pred = q + (q - r3) + (q - r3) * Fraction(n, 2 * (n - 1)) + (1 - 3 * q + 2 * r3) * Fraction(n + 1, 2 * (n - 1))

    # longest run of consecutive rounds with known proposers (first on ties)
    best, cur = [], []
    for i in range(T):
        if prop[i] is None or (i > 0 and rnd[i] != rnd[i - 1] + 1):
            if len(cur) > len(best):
                best = cur
            cur = []
        if prop[i] is not None:
            cur.append(prop[i])
    if len(cur) > len(best):
        best = cur
    terms = [per_view_pi(best[t - 1], best[t], best[t + 1], n) for t in range(1, len(best) - 1)]
    implied = sum(terms) / len(terms)

    # H8: signed stake inside [2/3, 2/3 + s_max]
    smax = max(share)
    nonempty = [s for s in sig if s]
    inband = sum(1 for s in nonempty if Fraction(2, 3) - Fraction(1, 10**9) <= sum(share[i] for i in s) <= Fraction(2, 3) + smax + Fraction(1, 10**9))

    # H2R: v1 semantics. bitvec on own round R describes votes for R-1;
    # absent(r) excludes the proposer of round r; pairs need r+1 == next.
    by_round = {rnd[i] - 1: sig[i] for i in range(T)}
    proposer_of = {rnd[i]: prop[i] for i in range(T)}
    ordered = sorted(by_round)
    everyone = frozenset(range(n))
    num = den = 0
    for j in range(len(ordered) - 1):
        r0, r1 = ordered[j], ordered[j + 1]
        if r1 != r0 + 1:
            continue
        ab0 = everyone - by_round[r0]
        p0 = proposer_of.get(r0)
        if p0 is not None:
            ab0 = ab0 - {p0}
        num += len(ab0 & (everyone - by_round[r1]))
        den += len(ab0)
    mean_p = sum(len(by_round[r]) / max(1, n - 1) for r in ordered) / len(ordered)

    # H2b: first-half absence rates predict second-half recurrence
    absent = [everyone - s for s in sig]
    h = T // 2
    rate = [sum(1 for A in absent[:h] if i in A) / h for i in range(n)]
    h2b_pred = sum(x * x for x in rate) / sum(rate)
    n2 = sum(len(absent[t] & absent[t + 1]) for t in range(h, T - 1))
    d2 = sum(len(absent[t]) for t in range(h, T - 1))

    # H9 / H10
    live = set().union(*sig) | {p for p in prop if p is not None}
    failed = sum(1 for e in evs if e["data"]["failed_proposer_indices"]) / T

    return {"epoch": raw["epoch"], "distinct": distinct, "sum_s2": float(q),
            "pi_pred": float(pred), "pi_implied": float(implied),
            "h8": inband / len(nonempty), "rec": num / den, "iid": 1 - mean_p,
            "h2b_obs": n2 / d2, "h2b_pred": h2b_pred,
            "live_stake": float(sum(share[i] for i in live)), "failed": failed}


def main() -> int:
    raw_dir = sys.argv[1]
    mine = {r["epoch"]: r for r in (recompute(p) for p in sorted(glob.glob(os.path.join(raw_dir, "epoch_*.json"))))}
    print(f"independently recomputed {len(mine)} epochs")
    if len(sys.argv) < 3:
        for e, r in mine.items():
            print(e, {k: round(v, 6) for k, v in r.items() if k != "epoch"})
        return 0
    theirs = {r["epoch"]: r for r in json.load(open(sys.argv[2]))["per_epoch"]}
    fields = {
        "distinct": lambda t: t["h1"]["distinct_proposer_rate"],
        "sum_s2": lambda t: t["sum_s2"],
        "pi_pred": lambda t: t["pi_stake_predicted"],
        "pi_implied": lambda t: t["pi_schedule_implied"],
        "h8": lambda t: t["h8_fraction_in_band"],
        "rec": lambda t: t["h2"]["absence_recurrence_rate"],
        "iid": lambda t: t["h2"]["predicted_iid_recurrence"],
        "h2b_obs": lambda t: t["h2b_observed"],
        "h2b_pred": lambda t: t["h2b_predicted"],
        "live_stake": lambda t: t["h9_live_stake_fraction"],
        "failed": lambda t: t["h10_failed_round_fraction"],
    }
    worst = {}
    for e, m in mine.items():
        for f, getter in fields.items():
            worst[f] = max(worst.get(f, 0.0), abs(m[f] - getter(theirs[e])))
    bad = False
    for f, d in worst.items():
        ok = d < 1e-9
        bad |= not ok
        print(f"  {f:11s} max |independent - primary| over {len(mine)} epochs = {d:.2e}  {'MATCH' if ok else 'MISMATCH'}")
    print("RESULT:", "ANY MISMATCH IS A FINDING -- trace it, do not reconcile by preference" if bad else "exact agreement on every statistic")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
