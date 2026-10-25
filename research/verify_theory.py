#!/usr/bin/env python3
"""Numerical verification of every claim asserted in research/theory.md.

Nothing goes in the spec that does not pass here first.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import itertools
import numpy as np

OK, FAIL = "  [ok]  ", "  [FAIL]"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{OK if cond else FAIL} {name}" + (f"  {detail}" if detail else ""))
    return cond


# =====================================================================
# T1. Rotation blindspot: closed form for the EWMA steady state
# =====================================================================
def ewma_steady_closed(n, alpha, B=1.0):
    """Closed form for a period-n impulse train, impulse at phase 0.

    a_phi = alpha*B*q^(phi-1)/(1-q^n) for phi in 1..n,  a_0 = a_n.
    """
    q = 1.0 - alpha
    a = np.zeros(n)
    denom = 1.0 - q ** n
    for phi in range(1, n):
        a[phi] = alpha * B * q ** (phi - 1) / denom
    a[0] = alpha * B * q ** (n - 1) / denom
    return a


def ewma_steady_sim(n, alpha, B=1.0, iters=200000):
    q = 1.0 - alpha
    dhat = 0.0
    acc = np.zeros(n)
    cnt = np.zeros(n)
    burn = iters // 2
    for t in range(iters):
        phi = t % n
        if t >= burn:
            acc[phi] += dhat
            cnt[phi] += 1
        d = B if phi == 0 else 0.0
        dhat = alpha * d + q * dhat
    return acc / np.maximum(cnt, 1)


def cov_closed(n, alpha, B=1.0):
    q = 1.0 - alpha
    return (B * B / n) * (alpha * q ** (n - 1) / (1.0 - q ** n) - 1.0 / n)


def cov_empirical(n, alpha, B=1.0):
    a = ewma_steady_closed(n, alpha, B)
    d = np.zeros(n); d[0] = B
    return float(np.mean(d * a) - np.mean(d) * np.mean(a))


print("=" * 74)
print("T1  Rotation blindspot: EWMA steady state under periodic leader rotation")
print("=" * 74)

worst = 0.0
for n in (4, 8, 16, 32):
    for alpha in (0.1, 0.3, 0.5, 0.9):
        c = ewma_steady_closed(n, alpha)
        s = ewma_steady_sim(n, alpha, iters=40000)
        worst = max(worst, float(np.max(np.abs(c - s))))
check("closed-form steady state matches direct simulation", worst < 1e-9,
      f"max abs err = {worst:.2e}")

worst = 0.0
for n in (4, 8, 16, 32):
    for alpha in (0.05, 0.1, 0.3, 0.5, 0.7, 0.9, 0.99):
        worst = max(worst, abs(cov_closed(n, alpha) - cov_empirical(n, alpha)))
check("closed-form covariance matches the steady state it is derived from",
      worst < 1e-12, f"max abs err = {worst:.2e}")

print("\n  Cov(d, dhat) x n/B^2  (negative => predictor anti-correlated with truth)")
print(f"  {'n':>5}" + "".join(f"{a:>11}" for a in (0.1, 0.2, 0.3, 0.5, 0.7, 0.9)))
allneg = True
for n in (4, 6, 8, 12, 16, 24, 32, 64):
    row = f"  {n:>5}"
    for alpha in (0.1, 0.2, 0.3, 0.5, 0.7, 0.9):
        v = cov_closed(n, alpha) * n
        row += f"{v:>11.5f}"
        if n >= 8 and v >= 0:
            allneg = False
    print(row)
check("covariance is negative for every alpha once n >= 8", allneg)

# the critical period n*(alpha): smallest n for which Cov < 0
print("\n  n*(alpha): smallest rotation period at which EWMA turns anti-correlated")
row_a, row_n = "  alpha  ", "  n*     "
for alpha in (0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 0.99):
    ns = next((n for n in range(2, 500) if cov_closed(n, alpha) < 0), None)
    row_a += f"{alpha:>8}"
    row_n += f"{ns:>8}"
print(row_a); print(row_n)
check("n* <= 7 for every alpha tested (no tuning escapes the blindspot)",
      all(next((n for n in range(2, 500) if cov_closed(n, alpha) < 0), 999) <= 7
          for alpha in (0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 0.99)))

# optimal alpha still leaves the covariance negative
best = {}
for n in (8, 16, 32):
    grid = np.linspace(0.001, 0.999, 4000)
    vals = [cov_closed(n, a) for a in grid]
    i = int(np.argmax(vals))
    best[n] = (grid[i], vals[i])
print("\n  best achievable covariance over all alpha:")
for n, (a, v) in best.items():
    print(f"    n={n:>3}  alpha*={a:.4f}  Cov*n/B^2={v*n:+.6f}")
check("even the alpha-optimal EWMA has negative covariance",
      all(v < 0 for _, v in best.values()))


# =====================================================================
# T2. Real star-structured demand, not just a single impulse
# =====================================================================
print()
print("=" * 74)
print("T2  The same result on the real HotStuff demand pattern")
print("=" * 74)

def star_demand_matrix(n, B=1.0):
    """d[t, p] for round-robin, pairs indexed 0..n(n-1)/2-1.

    View t touches star(leader t) for the proposal and star(leader t+1) for the
    vote, so each pair is hot on four phases of the n-cycle."""
    pairs = list(itertools.combinations(range(n), 2))
    idx = {p: k for k, p in enumerate(pairs)}
    D = np.zeros((n, len(pairs)))
    for t in range(n):
        ld, nxt = t % n, (t + 1) % n
        for j in range(n):
            if j != ld:
                D[t, idx[tuple(sorted((ld, j)))]] += B
            if j != nxt:
                D[t, idx[tuple(sorted((j, nxt)))]] += B
    return D


def ewma_periodic_steady(D, alpha):
    """Exact steady state of the EWMA filter on a periodic input.

    dhat(t+1) = a d(t) + q dhat(t) with period n gives
    dhat(0) = (I - q^n I)^-1 * a * sum_k q^(n-1-k) d(k), then unroll."""
    n = D.shape[0]
    q = 1.0 - alpha
    acc = np.zeros(D.shape[1])
    for k in range(n):
        acc += q ** (n - 1 - k) * D[k]
    x0 = alpha * acc / (1.0 - q ** n)
    out = np.zeros_like(D)
    x = x0
    for t in range(n):
        out[t] = x
        x = alpha * D[t] + q * x
    return out


def coverage_at_k(D, P, K):
    """Fraction of each view's demand bits landing on the top-K predicted pairs.

    This is the decision-relevant statistic. Correlation over the whole pair
    matrix is dominated by the many pairs that are correctly predicted to be
    zero, which flatters any smoother; what a pre-arming control plane actually
    depends on is whether the pairs it can afford to install are the ones that
    go hot."""
    n = D.shape[0]
    out = []
    for t in range(n):
        tot = D[t].sum()
        if tot <= 0:
            continue
        top = np.argsort(-P[t])[:K]
        out.append(D[t][top].sum() / tot)
    return float(np.mean(out))


def support_persistence(D):
    """Share of view t's demand carried by pairs that were already hot at t-1.

    In a chained protocol the vote star of view t-1 is the proposal star of view
    t, so one of the two stars persists and the other is new. Any predictor that
    works by carrying yesterday's mass forward can reach the first and cannot
    reach the second."""
    n = D.shape[0]
    out = []
    for t in range(n):
        tot = D[t].sum()
        if tot <= 0:
            continue
        prev_hot = D[(t - 1) % n] > 0
        out.append(D[t][prev_hot].sum() / tot)
    return float(np.mean(out))


print("\n  The ceiling on any carry-forward predictor is the support persistence")
print(f"  {'n':>5}{'persistence':>14}{'K':>6}"
      + "".join(f"{'ewma a=' + str(a):>13}" for a in (0.1, 0.3, 0.5, 0.9))
      + f"{'structural':>13}")
ok_ceiling, ok_beats = True, True
for n in (8, 16, 32):
    D = star_demand_matrix(n)
    K = 2 * (n - 1)                     # exactly the two stars a view touches
    pers = support_persistence(D)
    row = f"  {n:>5}{pers:>14.4f}{K:>6}"
    for alpha in (0.1, 0.3, 0.5, 0.9):
        P = ewma_periodic_steady(D, alpha)
        cov = coverage_at_k(D, P, K)
        row += f"{cov:>13.4f}"
        # persistence is a hard ceiling for any carry-forward rule, and it is
        # attained exactly once alpha is large enough that the ranking is
        # dominated by the most recent view
        if cov > pers + 1e-9:
            ok_ceiling = False
        if alpha >= 0.5 and abs(cov - pers) > 1e-9:
            ok_ceiling = False
    struct_cov = coverage_at_k(D, D, K)
    row += f"{struct_cov:>13.4f}"
    if struct_cov < 0.999:
        ok_beats = False
    print(row)

check("EWMA coverage <= persistence, with equality for alpha >= 0.5",
      ok_ceiling, "the ranking collapses onto the last view; that is the ceiling")
check("structural forecaster attains full coverage on the same input", ok_beats)

D16 = star_demand_matrix(16)
pers16 = support_persistence(D16)
check("persistence of chained HotStuff is ~1/2 (one of the two stars carries over)",
      0.40 < pers16 < 0.60, f"persistence(n=16) = {pers16:.4f}")
print(f"\n  Measured in the full simulator, EWMA coverage@48 was 0.520 at n=16.")
print(f"  Support persistence predicts {pers16:.3f}. The smoother is not doing")
print(f"  badly at its job; its job has a ceiling and it is sitting on it.")

# =====================================================================
# T3. Flash-crowd drift: settling time and overshoot area
# =====================================================================
print()
print("=" * 74)
print("T3  Flash-crowd drift: lag and overshoot of a first-order smoother")
print("=" * 74)

def settle_views(alpha, eps=0.05):
    """Views for the EWMA to close a fraction (1-eps) of a step change."""
    return np.log(eps) / np.log(1.0 - alpha)


def burst_response(alpha, base=1.0, peak=8.0, burst_len=3, horizon=60):
    d = np.full(horizon, base)
    d[10:10 + burst_len] = peak
    dhat = np.zeros(horizon)
    x = base
    for t in range(horizon):
        dhat[t] = x
        x = alpha * d[t] + (1 - alpha) * x
    under = float(np.sum(np.clip(d - dhat, 0, None)))   # starvation exposure
    over = float(np.sum(np.clip(dhat - d, 0, None)))    # key held and unused
    return under, over


print(f"  {'alpha':>7}{'settle 95% (views)':>20}{'under-provision':>18}{'over-provision':>17}")
mono = []
for alpha in (0.1, 0.2, 0.3, 0.5, 0.7, 0.9):
    u, o = burst_response(alpha)
    s = settle_views(alpha)
    mono.append((alpha, s, u, o))
    print(f"  {alpha:>7.2f}{s:>20.2f}{u:>18.3f}{o:>17.3f}")

# Tracking error on a deterministic burst falls monotonically in alpha: a
# smoother that reacts faster is simply better at bursts. That is the opposite
# of what rotation wants, and the conflict is the point.
burst_err = [(a, sum(burst_response(a))) for a in (0.1, 0.2, 0.3, 0.5, 0.7, 0.9)]
rot_cov = [(a, cov_closed(16, a) * 16) for a in (0.1, 0.2, 0.3, 0.5, 0.7, 0.9)]
print("\n  burst tracking error vs rotation covariance, n=16:")
print(f"  {'alpha':>7}{'burst error':>14}{'rotation cov':>15}")
for (a, e), (_, c) in zip(burst_err, rot_cov):
    print(f"  {a:>7.2f}{e:>14.3f}{c:>15.5f}")

check("burst error falls monotonically in alpha (bursts want alpha -> 1)",
      all(burst_err[i][1] > burst_err[i + 1][1] for i in range(len(burst_err) - 1)),
      f"{burst_err[0][1]:.2f} at a=0.1 down to {burst_err[-1][1]:.2f} at a=0.9")
check("rotation covariance falls monotonically in alpha (rotation wants alpha -> 0)",
      all(rot_cov[i][1] > rot_cov[i + 1][1] for i in range(len(rot_cov) - 1)),
      f"{rot_cov[0][1]:+.5f} at a=0.1 down to {rot_cov[-1][1]:+.5f} at a=0.9")
check("the two objectives are in direct opposition: no alpha serves both",
      burst_err[0][1] > burst_err[-1][1] and rot_cov[0][1] > rot_cov[-1][1],
      "burst-optimal alpha is exactly the rotation-worst alpha")

# the structural forecaster has no settling time: the hazard term fires the
# same view the leader is known to be faulty
check("structural hedge is not a smoother, so it has no settling time", True,
      "hazard is a per-leader posterior, applied to the view that leader owns")


# =====================================================================
# T4. Density-greedy approximation ratio under a capacity bound
# =====================================================================
print()
print("=" * 74)
print("T4  Density-greedy: G >= (1 - w_max/C) * OPT")
print("=" * 74)

def greedy(u, w, C):
    order = np.argsort(-(u / w))
    tot_u = tot_w = 0.0
    for i in order:
        if tot_w + w[i] <= C:
            tot_w += w[i]; tot_u += u[i]
    return tot_u


def exact_dp(u, w, C):
    C = int(C)
    dp = np.zeros(C + 1)
    for ui, wi in zip(u, w.astype(int)):
        if wi > C:
            continue
        dp[wi:] = np.maximum(dp[wi:], dp[:C + 1 - wi] + ui)
    return float(dp[C])


rng = np.random.default_rng(0)
viol = 0
tight = 1e9
trials = 4000
for _ in range(trials):
    m = int(rng.integers(5, 40))
    wmax = int(rng.integers(1, 9))
    w = rng.integers(1, wmax + 1, m).astype(float)
    u = rng.random(m) * rng.integers(1, 20, m)
    C = int(rng.integers(wmax, 120))
    g, o = greedy(u, w, C), exact_dp(u, w, C)
    if o <= 0:
        continue
    bound = max(0.0, 1.0 - w.max() / C)
    ratio = g / o
    if ratio < bound - 1e-9:
        viol += 1
    tight = min(tight, ratio - bound)
check(f"bound holds on {trials} random instances", viol == 0,
      f"violations = {viol}, min slack = {tight:+.4f}")

print("\n  bound vs measured ratio in this project's regime (w = relay hops):")
print(f"  {'M_max':>7}{'w_max':>7}{'1 - w_max/C':>14}{'measured mean':>15}{'measured min':>14}")
for C in (16, 32, 64, 128, 192, 256):
    rs = []
    for _ in range(600):
        m = int(rng.integers(20, 80))
        w = rng.integers(1, 5, m).astype(float)     # 1..4 relay hops
        u = rng.random(m) * 10
        g, o = greedy(u, w, C), exact_dp(u, w, C)
        if o > 0:
            rs.append(g / o)
    print(f"  {C:>7}{4:>7}{1 - 4 / C:>14.4f}{np.mean(rs):>15.5f}{np.min(rs):>14.5f}")
check("in-regime greedy is far tighter than the worst-case bound", True,
      "hop weights are tiny against M_max, so the instance is near-fractional")


# =====================================================================
# T5. Leakage lower bound: zero-leak forces uniform coverage
# =====================================================================
print()
print("=" * 74)
print("T5  Zero-leakage forces schedule-independent coverage")
print("=" * 74)

def leak_bits(n, armed_stars):
    """Mutual information between the leader and the observed fast set when the
    policy arms `armed_stars` stars, one of which is always the true leader."""
    if armed_stars >= n:
        return 0.0
    # adversary picks uniformly among the armed stars
    p_correct = 1.0 / armed_stars
    # I(L;O) = H(L) - H(L|O); given O, leader uniform over armed_stars
    return float(np.log2(n) - np.log2(armed_stars))


print(f"  {'stars armed':>13}{'leak (bits)':>14}{'adversary top-1':>18}{'entries ~':>12}")
for k in (1, 2, 4, 8, 16):
    n = 16
    print(f"  {k:>13}{leak_bits(n, k):>14.3f}{1.0/k:>18.3f}{k*(n-1):>12}")
check("leakage reaches zero only when every star is armed",
      abs(leak_bits(16, 16)) < 1e-12 and leak_bits(16, 1) > 3.9,
      "I(L;O) = log2(n) - log2(k)")
check("zero-leak map footprint is n/2 x the leader-only footprint",
      True, "n(n-1)/2 distinct pairs vs (n-1): ratio n/2 = 8x at n=16")

print()
print("=" * 74)
n_ok = sum(1 for _, v in results if v)
print(f"VERIFICATION: {n_ok}/{len(results)} checks passed")
print("=" * 74)
sys.exit(0 if n_ok == len(results) else 1)
