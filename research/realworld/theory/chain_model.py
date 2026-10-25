#!/usr/bin/env python3
"""Chained rotation under vote loss: exact per-view accounting, an exact expectation
under independent per-role loss, and a general simulator for any leader sequence and
any loss process (used with real Cosmos Hub absence sequences).

Model (paper, Sections III-IV): in view t the leader L(t) sends its proposal to every
other validator (complete proposal star); every validator v != L(t+1) sends its vote
to L(t+1) unless the vote is lost. Demand counts messages; pi_t is the demand of view t
carried on pairs active in view t-1, divided by the demand of view t.

Exact per-view identity (distinct a=L(t-1), b=L(t), c=L(t+1); l_t(v) = 1 if v's vote in
view t is lost):
  D_t = 2(n-1) - sum_{v != c} l_t(v)
  N_t = (n+1) - sum_{v not in {a,b}} l_{t-1}(v) - l_{t-1}(c) - l_t(a) - l_t(b) + l_t(b) l_{t-1}(c)
Self-check: python3 chain_model.py  (asserts; seconds)."""
import random

def pbin_dist(ps):
    """Poisson-binomial distribution of a sum of independent Bernoulli(p) variables."""
    dist = [1.0]
    for p in ps:
        nxt = [0.0] * (len(dist) + 1)
        for k, q in enumerate(dist):
            nxt[k] += q * (1 - p); nxt[k + 1] += q * p
        dist = nxt
    return dist

def exact_expected_pi(n, pa, pb, pg, po):
    """E[pi_t] for round-robin chained rotation with independent loss, per-sender
    probabilities pa (L(t-1)), pb (L(t)), pg (L(t+2)), po (each of the n-4 others)."""
    # view-t senders (all but c): a, b, g, and n-4 others
    senders = [pa, pb, pg] + [po] * (n - 4)
    E_invD = sum(q / (2 * (n - 1) - x) for x, q in enumerate(pbin_dist(senders)))
    wo_a = pbin_dist([pb, pg] + [po] * (n - 4)); wo_b = pbin_dist([pa, pg] + [po] * (n - 4))
    E_la_invD = pa * sum(q / (2 * (n - 1) - 1 - x) for x, q in enumerate(wo_a))
    E_lb_invD = pb * sum(q / (2 * (n - 1) - 1 - x) for x, q in enumerate(wo_b))
    # view t-1 senders excluding b: L(t-2) (role a there, pa), a (role b there, pb; costs nothing next view),
    # c (role g there, pg), and n-4 others (po)
    EA = (n + 1) - (pa + pg + (n - 4) * po) - pg          # c's lost vote in t-1 costs twice
    return EA * E_invD - E_la_invD - (1 - pg) * E_lb_invD

def first_order(n, pa, pb, pg, po):
    """Complete first-order expansion of E[pi_t] (the per-view average of Definition 4):
    pi0 - (2 mu2 + mu1)/D0 + [N0 (mu2 + mu1) - (pa + pb)] / (D0 (D0 - 1)),
    N0 = n + 1, D0 = 2(n - 1), mu2 = pa + pg, mu1 = pb + (n - 4) po. Proposition 1 (a ratio of
    expectations) omits the variance-of-demand part of the last term, which is first order in
    the loss but smaller than the leading effect by a factor of order 1/n."""
    N0, D0 = n + 1, 2 * (n - 1); mu2, mu1 = pa + pg, pb + (n - 4) * po
    return N0 / D0 - (2 * mu2 + mu1) / D0 + (N0 * (mu2 + mu1) - (pa + pb)) / (D0 * (D0 - 1))

def prop1(n, mu2, mu1):
    return (n + 1 - 2 * mu2 - mu1) / (2 * (n - 1) - mu2 - mu1)

def simulate(leaders, lost, n):
    """Mean over views of pi_t. leaders[t] in 0..n-1 (repeats allowed); lost(t, v) -> bool.
    Returns (mean_pi, per-role missing counts over counted views, counted views)."""
    prev = None; pis = []; miss = {"a": 0, "b": 0, "g": 0, "other": 0}
    T = len(leaders) - 2
    for t in range(T):
        b, c = leaders[t], leaders[t + 1]
        msgs = {}
        for v in range(n):
            if v != b:
                p = (b, v) if b < v else (v, b); msgs[p] = msgs.get(p, 0) + 1
        for v in range(n):
            if v == c: continue
            if lost(t, v):
                if t >= 1:
                    a, g = leaders[t - 1], leaders[t + 2]
                    miss["a" if v == a else "b" if v == b else "g" if v == g else "other"] += 1
                continue
            p = (c, v) if c < v else (v, c); msgs[p] = msgs.get(p, 0) + 1
        if prev is not None:
            pis.append(sum(k for p, k in msgs.items() if p in prev) / sum(msgs.values()))
        prev = set(msgs)
    return sum(pis) / len(pis), miss, len(pis)

def _check():
    rng = random.Random(7)
    n = 16; rr = [t % n for t in range(40_002)]
    # 1. no loss reproduces Corollary 1 exactly
    m, _, _ = simulate(rr, lambda t, v: False, n); assert abs(m - (n + 1) / (2 * (n - 1))) < 1e-12
    assert abs(exact_expected_pi(n, 0, 0, 0, 0) - (n + 1) / (2 * (n - 1))) < 1e-15
    # 2. exact expectation matches simulation under independent per-role loss (several mixes)
    for pa, pb, pg, po in ((0.2, 0, 0, 0), (0, 0.2, 0, 0), (0, 0, 0.2, 0), (0, 0, 0, 0.02), (0.1, 0.05, 0.15, 0.01), (0.3, 0.3, 0.3, 0.1)):
        rnd = {}
        def lost(t, v, pa=pa, pb=pb, pg=pg, po=po):
            key = (t, v)
            if key not in rnd:
                role = "a" if v == rr[t - 1] else "b" if v == rr[t] else "g" if v == rr[t + 2] else "o"
                rnd[key] = rng.random() < {"a": pa, "b": pb, "g": pg, "o": po}[role]
            return rnd[key]
        sim, miss, T = simulate(rr, lost, n)
        ex = exact_expected_pi(n, pa, pb, pg, po)
        assert abs(sim - ex) < 6e-4, (pa, pb, pg, po, sim, ex)
    # 3. first_order() leaves a second-order remainder (shrinks ~x4 when the loss halves) for every
    #    role mix; Proposition 1 (ratio of expectations) differs from E[pi_t] at first order, by O(loss/n^2)
    for mix in ((1, 1, 1, 1), (1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1), (3, 1, 2, 0.5)):
        rem = []
        for eps in (0.02, 0.01, 0.005):
            pa, pb, pg, po = (eps * m for m in mix)
            rem.append(abs(exact_expected_pi(n, pa, pb, pg, po) - first_order(n, pa, pb, pg, po)))
        if max(rem) < 1e-14: continue      # one lossy sender: E[pi_t] is exactly linear in its loss
        assert rem[0] / rem[1] > 3.5 and rem[1] / rem[2] > 3.7, (mix, rem)
    for eps in (0.01, 0.05):
        gap = exact_expected_pi(n, eps, eps, eps, eps) - prop1(n, 2 * eps, (n - 3) * eps)
        fo_gap = first_order(n, eps, eps, eps, eps) - prop1(n, 2 * eps, (n - 3) * eps)
        assert abs(gap - fo_gap) < 3 * eps ** 2, (eps, gap, fo_gap)
    print("chain_model self-check OK")

if __name__ == "__main__":
    _check()
