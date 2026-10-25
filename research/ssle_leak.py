#!/usr/bin/env python3
"""Does any leak survive once the traffic-only baseline is applied properly?

M1 showed that in a chained protocol pre-arming discloses nothing extra: the
vote phase is addressed to the next leader, so the wire already names it. That
kills the general claim. It does not kill every claim, because the reason the
baseline is so strong is specific to chained protocols.

Under secret leader election -- Ethereum's Whisk, homomorphic sortition -- the
proposer is unknown until it proposes, and attestations are gossiped to subnets
rather than addressed to the next proposer. So consensus traffic in view t
reveals L(t) after the fact and says nothing about L(t+1). That is the entire
point of the mechanism.

A predictive key-supply layer has to know L(t+1) in advance to pre-arm its star.
This experiment asks whether that advance knowledge becomes observable, and how
much it is worth against the correct baseline rather than against chance.

Two deployment models are distinguished, because they leak differently:

  central   a control plane that is told the schedule and arms every leader's
            star. Requires the schedule to be disclosed to the key layer, which
            is already a violation of the SSLE threat model.
  self-arm  the realistic one: each validator privately learns it will lead and
            arms its own star. No central disclosure -- but the arming is
            observable, which is the question.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def star(n, c):
    return {(min(c, j), max(c, j)) for j in range(n) if j != c}


def all_pairs(n):
    return {(i, j) for i in range(n) for j in range(i + 1, n)}


def rank(n, support, exclude=()):
    deg = np.zeros(n)
    for (a, b) in support:
        deg[a] += 1
        deg[b] += 1
    order = [int(x) for x in np.argsort(-deg)]
    return [v for v in order if v not in exclude]


def run(n=16, views=600, seed=1, attest_frac=1.0):
    """attest_frac: share of all-to-all attestation pairs actually gossiped."""
    rng = np.random.default_rng(seed)
    sched = [int(x) for x in rng.integers(0, n, views + 8)]   # secret, unpredictable
    ap = sorted(all_pairs(n))

    hits = {k: 0 for k in ("traffic_Lt", "traffic_Lt1",
                           "central_Lt1", "selfarm_Lt1")}
    for t in range(views):
        lt, lt1 = sched[t], sched[t + 1]

        # attestation gossip: leader-independent by construction
        m = max(1, int(round(attest_frac * len(ap))))
        idx = rng.choice(len(ap), size=m, replace=False)
        gossip = {ap[int(i)] for i in idx}

        traffic = star(n, lt) | gossip
        central = traffic | star(n, lt) | star(n, lt1)     # both stars armed
        selfarm = traffic | star(n, lt1)                    # only next leader arms

        hits["traffic_Lt"] += int(rank(n, traffic)[0] == lt)
        r_t = rank(n, traffic, exclude=(lt,))
        hits["traffic_Lt1"] += int(bool(r_t) and r_t[0] == lt1)
        r_c = rank(n, central, exclude=(lt,))
        hits["central_Lt1"] += int(bool(r_c) and r_c[0] == lt1)
        r_s = rank(n, selfarm, exclude=(lt,))
        hits["selfarm_Lt1"] += int(bool(r_s) and r_s[0] == lt1)

    return {k: v / views for k, v in hits.items()}


def main():
    n = 16
    base = 1.0 / n
    print("=" * 78)
    print("S1  Secret leader election: does pre-arming beat the traffic baseline?")
    print("=" * 78)
    print(f"  n = {n}, VRF schedule, attestations gossiped to all.")
    print(f"  Baseline for naming L(t+1) among the n-1 non-proposers = "
          f"{1/(n-1):.4f}\n")
    print(f"  {'attest frac':>12}{'traffic->L(t)':>15}{'traffic->L(t+1)':>17}"
          f"{'central arm':>13}{'self arm':>11}")
    rows = []
    for af in (1.0, 0.5, 0.25, 0.1):
        r = run(n=n, attest_frac=af)
        rows.append({"attest_frac": af, **r})
        print(f"  {af:>12.2f}{r['traffic_Lt']:>15.4f}{r['traffic_Lt1']:>17.4f}"
              f"{r['central_Lt1']:>13.4f}{r['selfarm_Lt1']:>11.4f}")

    r = rows[0]
    marg_c = r["central_Lt1"] - r["traffic_Lt1"]
    marg_s = r["selfarm_Lt1"] - r["traffic_Lt1"]
    print(f"\n  marginal over traffic, full gossip:")
    print(f"    central arming : {marg_c:+.4f}")
    print(f"    self arming    : {marg_s:+.4f}")

    print()
    print("=" * 78)
    print("S2  Scaling of the surviving leak")
    print("=" * 78)
    print("  Attestations gossiped to a subnet, not to every peer: Ethereum")
    print("  splits attesters across subnets, so the all-to-all case is not the")
    print("  deployed one. Full gossip saturates every degree and hides the")
    print("  proposer from traffic and from pre-arming alike.\n")
    print(f"  {'n':>5}{'baseline':>11}{'traffic':>10}{'self arm':>11}{'marginal':>11}")
    scal = []
    for nn in (7, 16, 31, 64, 128):
        r = run(n=nn, views=400, attest_frac=0.25)
        m = r["selfarm_Lt1"] - r["traffic_Lt1"]
        scal.append({"n": nn, **r, "marginal": m})
        print(f"  {nn:>5}{1/(nn-1):>11.4f}{r['traffic_Lt1']:>10.4f}"
              f"{r['selfarm_Lt1']:>11.4f}{m:>+11.4f}")

    rec = {"experiment_id": "S-ssle-leak-001",
           "utc": datetime.now(timezone.utc).isoformat(),
           "protocol": "SSLE / gossiped attestations",
           "attest_sweep": rows, "scaling": scal}
    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "S-ssle-leak-001.json"), "w") as f:
        json.dump(rec, f, indent=2)
    print("\nwrote research/results/S-ssle-leak-001.json")


if __name__ == "__main__":
    main()
