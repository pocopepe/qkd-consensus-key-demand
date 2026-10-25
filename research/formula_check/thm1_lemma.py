"""Theorem 1 (eq:thmA), eq:thmA2, Cor chained, Cor volume (U), D_t=m(n-1), |S|=2n-3,
pair- vs demand-weighted persistence, Lemma 1 (cover recovery), Fig. 2 example.
Brute force from the definitions in paper.tex (hub-union support, d_t = #hubs in pair)."""
from fractions import Fraction as F
from itertools import combinations
import sympy as sp

def star_union(R, n):
    return {frozenset((r, v)) for r in R for v in range(n) if v != r}

def demand(R, n):
    d = {}
    for r in R:                      # R may be a list (multiset) -> counted once per role
        for v in range(n):
            if v != r:
                p = frozenset((r, v)); d[p] = d.get(p, 0) + 1
    return d

def pi_t(Rprev, Rcur, n):
    Sprev = star_union(Rprev, n); d = demand(Rcur, n)
    D = sum(d.values()); carried = sum(x for p, x in d.items() if p in Sprev)
    return F(carried, D), D, D - carried

def thm(n, m, k): return F(k*(n-1) + m*(m-k), m*(n-1))

# --- Theorem 1 brute force: every (n,m,k) with A5 (n>m), A7 (2m-k<=n), n<=9, every realisation
checked = 0
for n in range(2, 10):
    for m in range(1, n):
        for k in range(0, m+1):
            if 2*m - k > n: continue
            V = range(n)
            seen = set()
            for Rprev in combinations(V, m):
                for keep in combinations(Rprev, k):
                    rest = [v for v in V if v not in Rprev]
                    for new in combinations(rest, m-k):
                        Rcur = list(keep) + list(new)
                        p, D, U = pi_t(Rprev, Rcur, n)
                        assert p == thm(n, m, k), (n, m, k, Rprev, Rcur, p)
                        assert D == m*(n-1)
                        assert U == (m-k)*(n-1-m)
                        checked += 1
print("Theorem 1 / D_t / U verified on", checked, "realisations, n<=9 (A5,A7)")

# A5 dropped: n == m (then A7 forces k=m) -> formula still 1
for n in range(2, 8):
    assert pi_t(list(range(n)), list(range(n)), n)[0] == 1 == thm(n, n, n)
print("n=m (A5 violated, k=m) still gives pi=1: A5 not needed by Theorem 1")

# symbolic forms
n, m, k = sp.symbols('n m k', positive=True)
T = (k*(n-1) + m*(m-k))/(m*(n-1))
assert sp.simplify(T - (k/m + (m-k)/(n-1))) == 0
assert sp.simplify(m*(n-1)*(1-T) - (m-k)*(n-1-m)) == 0
assert sp.simplify(T.subs({m: 2, k: 1}) - (n+1)/(2*(n-1))) == 0
assert sp.simplify(T.subs({k: 0}) - m/(n-1)) == 0
assert sp.simplify((n+1)/(2*(n-1)) - sp.Rational(1, 2) - 1/(n-1)) == 0
print("symbolic: eq:thmA2, U, eq:chained, k=0 -> m/(n-1), excess over 1/2 = 1/(n-1): OK")
# monotone decreasing in n for k<m
print("d pi/dn =", sp.simplify(sp.diff(T, n)), "(negative iff k<m)")

# numeric claims
print("pi(4,2,1) finite term =", F(1, 3), " pi(16)=", float(thm(16, 2, 1)), "1-pi(16)=", float(1-thm(16, 2, 1)),
      "1-pi(84)=", float(1-thm(84, 2, 1)))
print("pi(16,2,0)=", float(thm(16, 2, 0)))
# Fig 2 example n=5, a=0,b=1,c=2
p, D, U = pi_t([0, 1], [1, 2], 5); print("Fig.2: pi=", p, "D=", D, "U=", U)

# pair-weighted vs demand-weighted for chained rotation
def pair_weighted(Rprev, Rcur, n):
    S0, S1 = star_union(Rprev, n), star_union(Rcur, n)
    return F(len(S1 & S0), len(S1)), len(S1)
for nn in range(3, 30):
    pw, size = pair_weighted([0, 1], [1, 2], nn)
    assert size == 2*nn - 3 and pw == F(nn, 2*nn-3)
    dw = thm(nn, 2, 1)
    if nn >= 4: assert pw != dw
    else: assert pw == dw
print("|S(t)|=2n-3, pair-weighted = n/(2n-3), equals demand-weighted only at n=3; n=5:", pair_weighted([0,1],[1,2],5)[0])

# silent proposers mixture
for f_, pred in [(1, 0.5378), (5, 0.3697)]:
    nn = 16
    mix = ((nn - 2*f_)*thm(nn, 2, 1) + f_*thm(nn, 2, 0)) / (nn - f_)
    print(f"silent f={f_}: mixture {float(mix):.4f} (paper {pred})")

# Table e2main / e3 predictions and residuals, finite-n ratio
for nn, meas, res in [(4, .833333, 3.3e-11), (7, .666657, 9.3e-6), (10, .611085, 2.6e-5), (16, .566645, 2.2e-5), (32, .531836, 4.2e-4)]:
    print(nn, f"{float(thm(nn,2,1)):.6f}", "resid from printed values", f"{float(thm(nn,2,1))-meas:.3g}", "paper", res,
          " excess ratio", f"{(meas-.5)*(nn-1):.4f}")
for nn in (8, 16, 32, 64): print("e3", nn, f"{float(thm(nn,2,1)):.4f}")

# --- Lemma 1: minimum vertex covers of a union of m complete stars
def min_covers(edges, n):
    for size in range(0, n+1):
        found = [set(C) for C in combinations(range(n), size) if all(e & set(C) for e in edges)]
        if found: return size, found
for nn in range(2, 9):
    for mm in range(1, nn):            # A5: n>m
        R = set(range(mm)); edges = star_union(R, nn)
        size, covers = min_covers(edges, nn)
        assert size == mm and R in covers
        uniq = (len(covers) == 1)
        assert uniq == (nn >= mm + 2), (nn, mm, covers)
print("Lemma 1: R is a minimum cover for all n>m<=8; unique iff n>=m+2 (n=m+1 gives n covers)")
