#!/usr/bin/env python3
"""Closed forms for the duality, checked against the measured study.

The study output is not a scatter that happens to correlate. Every quantity in
it has an exact expression, and this file checks each one.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from research.duality_study import study
from research.protocols import (PBFT, AlgorandCommittee, ChainedHotStuff,
                                NarwhalDAG, Simplex, Tendermint)

ok = []


def check(name, cond, detail=""):
    ok.append(bool(cond))
    print(f"  [{'ok' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


NS = [4, 7, 16, 31, 64, 128, 256]

print("=" * 74)
print("D1  pi for a rotating-leader linear protocol is (n+1)/(2(n-1))")
print("=" * 74)
print("""
  View t touches star(L(t)) for the proposal and star(L(t+1)) for the vote,
  2(n-1) pair-messages in total. View t-1 touched star(L(t-1)) and star(L(t)).
  The whole proposal star of view t was already hot -- it was view t-1's vote
  star -- contributing (n-1) messages. From view t's vote star only two pairs
  were hot before: {L(t+1),L(t-1)} and {L(t+1),L(t)}. So

      pi(n) = ((n-1) + 2) / (2(n-1)) = (n+1) / (2(n-1))  ->  1/2.
""")
print(f"  {'n':>6}{'predicted':>12}{'measured':>12}{'abs err':>12}")
worst = 0.0
for n in NS:
    pred = (n + 1) / (2 * (n - 1))
    meas = study(ChainedHotStuff, n)["pi"]
    worst = max(worst, abs(pred - meas))
    print(f"  {n:>6}{pred:>12.6f}{meas:>12.6f}{abs(pred-meas):>12.2e}")
check("closed form matches measurement for every n", worst < 1e-12,
      f"max err {worst:.2e}")
check("pi -> 1/2 from above", abs((257) / (2 * 255) - 0.5) < 0.005)

print()
print("=" * 74)
print("D2  EWMA coverage equals pi exactly, for every protocol and every n")
print("=" * 74)
print(f"  {'protocol':<20}{'n':>5}{'pi':>10}{'ewma':>10}{'diff':>12}")
worst = 0.0
for P in (PBFT, Tendermint, NarwhalDAG, Simplex, ChainedHotStuff):
    for n in (7, 16, 64):
        r = study(P, n)
        d = abs(r["pi"] - r["ewma"])
        worst = max(worst, d)
        print(f"  {P(n).name:<20}{n:>5}{r['pi']:>10.6f}{r['ewma']:>10.6f}{d:>12.2e}")
check("Theorem 2 generalises across the protocol space", worst < 1e-9,
      f"max |pi - ewma| = {worst:.2e}")

print()
print("=" * 74)
print("D3  Structural gain equals 1 - pi")
print("=" * 74)
worst = 0.0
for P in (PBFT, NarwhalDAG, Simplex, ChainedHotStuff):
    for n in (7, 16, 64, 128):
        r = study(P, n)
        worst = max(worst, abs(r["gain"] - (1.0 - r["pi"])))
check("gain = 1 - pi holds identically", worst < 1e-9, f"max err {worst:.2e}")
print("  A schedule-aware forecaster reaches coverage 1 by construction, so the")
print("  gain it holds over any carry-forward rule is exactly the share of demand")
print("  that does not persist. Nothing is left for tuning to recover.")

print()
print("=" * 74)
print("D4  Leader leakage from the pre-armed support")
print("=" * 74)
print(f"  {'protocol':<20}{'n':>5}{'top1':>10}{'predicted':>12}{'MI bits':>10}{'H(L)':>8}")
worst_l = 0.0
for P in (PBFT, ChainedHotStuff):
    for n in (16, 64, 128):
        r = study(P, n)
        # a star-shaped support names its centre; an all-to-all support does not
        pred = (n - 1) / n if P is ChainedHotStuff else 1.0 / n
        worst_l = max(worst_l, abs(r["top1"] - pred))
        print(f"  {P(n).name:<20}{n:>5}{r['top1']:>10.4f}{pred:>12.4f}"
              f"{r['mi_bits']:>10.4f}{np.log2(n):>8.4f}")
check("top-1 leakage is (n-1)/n for linear, 1/n for quadratic", worst_l < 1e-9,
      f"max err {worst_l:.2e}")

r128 = study(ChainedHotStuff, 128)
frac = r128["mi_bits"] / np.log2(128)
check("linear protocols leak essentially all leader entropy", frac > 0.99,
      f"{r128['mi_bits']:.3f} of {np.log2(128):.0f} bits = {100*frac:.1f}%")

print()
print("=" * 74)
print("D5  Gain-Leak Duality: the same quantity, measured twice")
print("=" * 74)
rows = []
for P in (PBFT, Tendermint, NarwhalDAG, Simplex, ChainedHotStuff, AlgorandCommittee):
    for n in (7, 16, 31, 64):
        r = study(P, n)
        rows.append((P(n).name, n, r["gain"], r["advantage"], r["mi_bits"]))
g = np.array([x[2] for x in rows])
a = np.array([x[3] for x in rows])
print(f"  corr(gain, leak advantage) over {len(rows)} points = "
      f"{np.corrcoef(g, a)[0,1]:+.4f}")
zero = [x for x in rows if x[2] < 0.01]
big = [x for x in rows if x[2] > 0.2]
print(f"  gain < 0.01 ({len(zero):>2} pts): mean advantage = "
      f"{np.mean([x[3] for x in zero]):.4f}")
print(f"  gain > 0.20 ({len(big):>2} pts): mean advantage = "
      f"{np.mean([x[3] for x in big]):.4f}")
check("no protocol has high forecasting gain and low leakage",
      not any(x[2] > 0.2 and x[3] < 0.5 for x in rows))
check("no protocol has low forecasting gain and high leakage",
      not any(x[2] < 0.01 and x[3] > 0.5 for x in rows))

print()
print("=" * 74)
print("D6  Sortition: the leak survives even when prediction does not")
print("=" * 74)
def committee_recovery(n, views=200, warm=20):
    """How much of the committee does the pre-armed support disclose?

    The support of a sortition view is the complete graph on that view's
    committee, so any vertex with non-zero degree is a member. This is not an
    inference -- it is a read-off."""
    p = AlgorandCommittee(n)
    prec, rec = [], []
    for t in range(warm, warm + views):
        sup = [q for q, b in p.demand(t).items() if b > 0]
        seen = set()
        for (a, b) in sup:
            seen.add(a); seen.add(b)
        truth = set(p.committee(t))
        if not truth:
            continue
        prec.append(len(seen & truth) / max(len(seen), 1))
        rec.append(len(seen & truth) / len(truth))
    return float(np.mean(prec)), float(np.mean(rec))


print(f"  {'n':>6}{'c':>5}{'gain':>9}{'leader top1':>13}{'baseline':>10}"
      f"{'committee prec':>16}{'committee recall':>18}")
cr_min = 1.0
for n in (16, 31, 64, 128):
    p = AlgorandCommittee(n)
    r = study(AlgorandCommittee, n)
    pr, rc = committee_recovery(n)
    cr_min = min(cr_min, pr, rc)
    print(f"  {n:>6}{p.c:>5}{r['gain']:>9.4f}{r['top1']:>13.4f}{1.0/n:>10.4f}"
          f"{pr:>16.4f}{rc:>18.4f}")
check("sortition hides the leader from the pre-arm channel",
      all(study(AlgorandCommittee, n)["advantage"] < 0.4 for n in (31, 64, 128)))
check("but discloses committee membership exactly", cr_min > 0.999,
      f"min precision/recall = {cr_min:.4f}")
print("\n  Secret sortition defeats the forecaster -- gain is zero, there is no")
print("  schedule to read -- and it defeats leader identification too. What it")
print("  does not defeat is membership disclosure: the pre-armed support IS the")
print("  committee's clique, so every member is named. The duality holds for the")
print("  leader; the residual leak is one level coarser and does not vanish.")



# ---------------------------------------------------------------------------
# D7  The duality is an identity, not a correlation
# ---------------------------------------------------------------------------
print()
print("=" * 74)
print("D7  Exact duality for rotating-leader linear protocols")
print("=" * 74)
print("""
  pi(n)      = (n+1) / (2(n-1))                        [Theorem 7]
  gain(n)    = 1 - pi = (n-3) / (2(n-1))               [Corollary 9]
  top1(n)    = (n-1)/n                                 [Theorem 10]
  adv(n)     = (top1 - 1/n)/(1 - 1/n) = (n-2)/(n-1)

  adv - gain = [2(n-2) - (n-3)] / (2(n-1)) = (n-1)/(2(n-1)) = 1/2.

  The leak advantage exceeds the forecasting gain by exactly one half, for
  every n. The two are not merely correlated across a protocol space; for this
  class they are the same function offset by a constant.
""")
print(f"  {'n':>6}{'gain':>12}{'advantage':>12}{'adv - gain':>13}")
worst_id = 0.0
for n in (4, 7, 16, 31, 64, 128, 256):
    r = study(ChainedHotStuff, n)
    diff = r["advantage"] - r["gain"]
    worst_id = max(worst_id, abs(diff - 0.5))
    print(f"  {n:>6}{r['gain']:>12.6f}{r['advantage']:>12.6f}{diff:>13.6f}")
check("adv - gain = 1/2 identically", worst_id < 1e-9,
      f"max deviation {worst_id:.2e}")
check("closed forms match measurement", all(
    abs(study(ChainedHotStuff, n)["gain"] - (n - 3) / (2 * (n - 1))) < 1e-9
    for n in (7, 16, 64, 128)))

print()
print("=" * 74)
print(f"DUALITY VERIFICATION (with D7): {sum(ok)}/{len(ok)} checks passed")
print("=" * 74)
sys.exit(0 if all(ok) else 1)
