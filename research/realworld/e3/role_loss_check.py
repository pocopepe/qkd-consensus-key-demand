#!/usr/bin/env python3
"""Brute-force check of the role-dependent vote-loss proposition (not a campaign).

Chained rotation, round-robin leaders, complete proposal stars. In view t the
proposer is L(t) and every validator except L(t+1) sends one vote to L(t+1).
A vote is dropped with a probability that depends on the sender's role in that
view: 'prev' = L(t-1), 'cur' = L(t), 'next2' = L(t+2), 'other' = the rest.
Measured pi is the mean over views of carried demand / total demand, computed
from the message sets alone. It is compared with

  two-role   (n+1-2*mu_prev-mu_rest)          / (2(n-1)-mu_prev-mu_rest)
  three-role (n+1-2*(mu_prev+mu_next2)-mu_1)  / (2(n-1)-mu_prev-mu_next2-mu_1)

Usage: role_loss_check.py [views]   (self-checks with asserts, prints a table)
"""
import random, sys
from collections import Counter

def simulate(n, loss, views, seed=1):
    rng = random.Random(seed)
    L = lambda t: t % n
    prev_support, num = None, Counter()
    ratios, missing = [], Counter()
    for t in range(views):
        a, b, c, d = L(t - 1), L(t), L(t + 1), L(t + 2)
        msgs = Counter(frozenset((b, v)) for v in range(n) if v != b)
        for v in range(n):
            if v == c: continue
            role = "prev" if v == a else "cur" if v == b else "next2" if v == d else "other"
            if rng.random() < loss.get(role, 0.0): missing[role] += 1
            else: msgs[frozenset((v, c))] += 1
        if prev_support is not None:
            ratios.append(sum(k for p, k in msgs.items() if p in prev_support) / sum(msgs.values()))
        prev_support = set(msgs)
    T = len(ratios) + 1
    return sum(ratios) / len(ratios), {r: missing[r] / T for r in ("prev", "cur", "next2", "other")}

def two_role(n, mu):
    rest = mu["cur"] + mu["next2"] + mu["other"]
    return (n + 1 - 2 * mu["prev"] - rest) / (2 * (n - 1) - mu["prev"] - rest)

def three_role(n, mu):
    two, one = mu["prev"] + mu["next2"], mu["cur"] + mu["other"]
    return (n + 1 - 2 * two - one) / (2 * (n - 1) - two - one)

def main():
    views = int(sys.argv[1]) if len(sys.argv) > 1 else 200_000
    n = 16
    print(f"n={n}, {views} views, about 0.05 votes lost per view, one role at a time")
    print(f"{'role':>6} {'measured':>10} {'two-role':>10} {'three-role':>11}")
    for role in ("prev", "cur", "next2", "other"):
        meas, mu = simulate(n, {role: 0.05 / (n - 3 if role == "other" else 1)}, views)
        t2, t3 = two_role(n, mu), three_role(n, mu)
        print(f"{role:>6} {meas:10.6f} {t2:10.6f} {t3:11.6f}")
        assert abs(meas - t3) < 3e-4, (role, meas, t3)          # three-role form holds for every role
        if role != "next2": assert abs(t2 - t3) < 1e-12           # and coincides with two-role elsewhere
    meas, mu = simulate(n, {"next2": 0.05}, views)
    assert abs(meas - two_role(n, mu)) > 1e-3                     # two-role form misses L(t+2)'s votes
    meas0, _ = simulate(n, {}, 2000)
    assert abs(meas0 - (n + 1) / (2 * (n - 1))) < 1e-12           # no loss: Corollary (chained rotation)
    print("OK")

if __name__ == "__main__":
    main()
