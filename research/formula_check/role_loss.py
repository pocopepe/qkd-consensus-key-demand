"""eq:pip (role-blind) and Proposition 2 (eq:role): chained rotation, round-robin leaders,
complete proposal stars, each vote of view t (sender v -> next leader c) lost independently
with a probability that depends on v's role in view t (a=prev leader, b=current, g=leader after c,
o=other).  Computes, for given role loss probabilities:
  R_exp  = E[carried]/E[total]   exact (enumeration over the relevant indicators)
  A_exp  = E[carried/total]      exact (= time average of pi_t, Definition 1)
  eq:role first-order value, and the first-order difference formula of the text.
Cross-checked against a direct Monte Carlo of the message sets (support/demand built from
messages, pi_t from Definition 1), so the hand-derived carried-count expression is not trusted."""
from fractions import Fraction as F
from itertools import product
import random

def exact(n, pa, pb, pg, po):
    """Carried count in view t (derived from the definitions, verified by MC below):
    N = 1 + #{v not in {a,b}, v != b : vote of v in t-1 kept} + (1-l_t(a)) + (1-l_t(b))(1-l_{t-1}(c))
    D = (n-1) + #{v != c : vote of v in t kept}.
    Roles in view t-1: a'=prev(a) (role a), a (role b), b (role c, receiver), c (role g), others."""
    q = dict(a=pa, b=pb, g=pg, o=po)
    # view t-1 voters other than b (receiver) and a (role b of t-1, excluded from proposal count):
    # prev(a) role a ; c role g ; n-4 others role o.  (c's indicator also appears in the vote term)
    # view t voters: a, b, g, and n-4 others.
    no = n - 4
    # distribution of #kept among the n-4 'other' voters of view t and of t-1
    def binom(k, p, N):
        from math import comb
        return comb(N, k) * p**k * (1-p)**(N-k)
    Rnum = Rden = A = F(0)
    for la_t, lb_t, lg_t, lap_prev, lc_prev in product((0, 1), repeat=5):
        pr = 1
        for l, p in ((la_t, q['a']), (lb_t, q['b']), (lg_t, q['g']), (lap_prev, q['a']), (lc_prev, q['g'])):
            pr *= p if l else 1 - p
        for ko_t in range(no+1):           # kept 'other' votes in view t
            pt = binom(ko_t, 1-q['o'], no)
            D = (n-1) + (1-la_t) + (1-lb_t) + (1-lg_t) + ko_t
            # E[N | ...]: other voters of t-1 are independent of view t -> use expectation (linear in them)
            EN = 1 + (1-lap_prev) + (1-lc_prev) + no*(1-q['o']) + (1-la_t) + (1-lb_t)*(1-lc_prev)
            w = pr * pt
            Rnum += w*EN; Rden += w*D; A += w*EN/D
    return Rnum/Rden, A

def eq_role(n, pa, pb, pg, po):
    mu2 = pa + pg; mu1 = pb + (n-4)*po
    return F(n+1) - 2*mu2 - mu1, 2*(n-1) - mu2 - mu1

def eq_pip(n, phi):
    return (1 + phi*(n-2) + phi*(1+phi)) / ((n-1)*(1+phi))

def mc(n, pa, pb, pg, po, views=200000, seed=0):
    rng = random.Random(seed)
    prob = lambda t, v: (pa if v == (t-1) % n else pb if v == t % n else pg if v == (t+2) % n else po)
    def view(t):
        b, c = t % n, (t+1) % n
        d = {}
        for v in range(n):
            if v != b: d[frozenset((b, v))] = d.get(frozenset((b, v)), 0) + 1
        for v in range(n):
            if v != c and rng.random() >= prob(t, v):
                d[frozenset((v, c))] = d.get(frozenset((v, c)), 0) + 1
        return d
    prev = view(0); s_num = s_den = 0; s_ratio = 0.0
    for t in range(1, views+1):
        cur = view(t)
        D = sum(cur.values()); N = sum(x for p, x in cur.items() if p in prev)
        s_num += N; s_den += D; s_ratio += N/D; prev = cur
    return s_num/s_den, s_ratio/views

if __name__ == '__main__':
    # 1. eq:pip vs exact ratio of expectations (role-blind: same phi for every voter)
    for n in (5, 8, 16):
        for phi in (F(1), F(9, 10), F(1, 2)):
            R, A = exact(n, 1-phi, 1-phi, 1-phi, 1-phi)
            assert R == eq_pip(n, phi), (n, phi, R, eq_pip(n, phi))
    print("eq:pip == exact E[carried]/E[total] for role-blind loss (n=5,8,16; phi=1,.9,.5)")
    # 2. MC cross-check of the carried-count expression
    for (n, pa, pb, pg, po) in [(8, .3, .1, .2, .05), (16, .05, .2, .1, .02), (8, 0, 0, 0, 0)]:
        R, A = exact(n, F(pa), F(pb), F(pg), F(po))
        r_mc, a_mc = mc(n, pa, pb, pg, po, views=100000, seed=n)
        print(f"MC n={n} p=({pa},{pb},{pg},{po}): ratio-of-exp exact {float(R):.5f} MC {r_mc:.5f} | avg-ratio exact {float(A):.5f} MC {a_mc:.5f}")
    # 3. Proposition 2 first-order claim: error of eq:role vs exact, scaling with mu^2
    print("\nn  loss-vector(a,b,g,o)        eq:role     R_exp       A_exp     |eqrole-R|  |eqrole-A|   mu_b*mu_g   (A-R)   firstorder(A-R)")
    for n in (8, 16, 32):
        for vec in [(.01, .01, .01, .01), (.1, 0, 0, 0), (0, .1, 0, 0), (0, 0, .1, 0), (0, .1, .1, 0), (.05, .05, .05, .05), (.2, .2, .2, .2)]:
            pa, pb, pg, po = map(F, map(str, vec))
            num, den = eq_role(n, pa, pb, pg, po); er = num/den
            R, A = exact(n, pa, pb, pg, po)
            mu = pa + pb + pg + (n-4)*po; D0 = 2*(n-1); pi0 = F(n+1, D0)
            fo = (pi0*mu - (pa + pb)) / (D0*(D0-1))
            # exact R including the omitted product term
            assert R == (num + pb*pg) / den
            print(f"{n:2d} {str(vec):26s} {float(er):.6f} {float(R):.6f} {float(A):.6f} {float(abs(er-R)):.2e} {float(abs(er-A)):.2e} {float(pb*pg):.2e} {float(A-R):+.2e} {float(fo):+.2e}")
    print("\n=> eq:role differs from E[N]/E[D] only by the omitted term mu_b*mu_g/den (exact identity asserted).")
    # 4. Paper's numeric claims: every sender loses 1% of its votes
    for n, claim in ((8, 1.4e-4), (16, 7.8e-5)):
        p = F(1, 100); R, A = exact(n, p, p, p, p)
        num, den = eq_role(n, p, p, p, p)
        mu = (n-1)*p; D0 = 2*(n-1); fo = (F(n+1, D0)*mu - 2*p)/(D0*(D0-1))
        print(f"1% loss n={n}: exact A-R = {float(A-R):.3e}; first-order formula {float(fo):.3e}; A - eq:role = {float(A-num/den):.3e}; paper {claim}")
        print(f"   effect of the loss pi0 - R = {float(F(n+1,D0)-R):.3e}, ratio diff/effect = {float((A-R)/(F(n+1,D0)-R)):.3f}")
    # 5. factor (2-pi)/(1-pi) at n=16, and per-vote marginal effects
    for n in (8, 16, 32, 84):
        pi0 = F(n+1, 2*(n-1)); print(f"n={n}: (2-pi)/(1-pi) = {float((2-pi0)/(1-pi0)):.4f}")
    # 6. Targeted-suppression Delta at nominal LAMBDA=0.2
    for n in (16, 32):
        L = F(1, 5); res = {}
        for arm, vec in dict(a=(L, 0, 0, 0), g=(0, 0, L, 0), b=(0, L, 0, 0), o=(0, 0, 0, L/(n-4))).items():
            num, den = eq_role(n, *vec); R, A = exact(n, *vec); res[arm] = (num/den, A)
        for j, name in ((0, 'eq:role'), (1, 'exact avg of pi_t')):
            Dl = (res['b'][j] + res['o'][j])/2 - (res['a'][j] + res['g'][j])/2
            print(f"n={n} nominal 0.2 votes/view: Delta via {name} = {float(Dl):.5f}")
        blind = {arm: eq_pip(n, 1 - L/(n-1)) for arm in 'abgo'}
        print(f"   role-blind eq:pip at equal total loss predicts Delta = 0 exactly (same phi in every arm)")

def brute(n, pa, pb, pg, po):
    """Exact E[N]/E[D] and E[N/D] by enumerating every loss pattern of views t-1 and t,
    support and demand rebuilt from the message sets (no hand-derived carried count)."""
    from itertools import product as P
    t = 1  # view t-1 = 0, view t = 1; leaders L_j = j mod n
    def probs(view):
        b, c = view % n, (view+1) % n
        voters = [v for v in range(n) if v != c]
        pr = [pa if v == (view-1) % n else pb if v == b else pg if v == (view+2) % n else po for v in voters]
        return b, c, voters, pr
    def msgs(view, kept):
        b, c, voters, _ = probs(view); d = {}
        for v in range(n):
            if v != b: d[frozenset((b, v))] = d.get(frozenset((b, v)), 0) + 1
        for v, k in zip(voters, kept):
            if k: d[frozenset((v, c))] = d.get(frozenset((v, c)), 0) + 1
        return d
    _, _, v0, p0 = probs(0); _, _, v1, p1 = probs(1)
    EN = ED = A = F(0)
    for k0 in P((0, 1), repeat=len(v0)):
        w0 = F(1)
        for k, p in zip(k0, p0): w0 *= (1-p) if k else p
        if w0 == 0: continue
        S0 = set(msgs(0, k0))
        for k1 in P((0, 1), repeat=len(v1)):
            w = w0
            for k, p in zip(k1, p1): w *= (1-p) if k else p
            if w == 0: continue
            d = msgs(1, k1); D = sum(d.values()); N = sum(x for p_, x in d.items() if p_ in S0)
            EN += w*N; ED += w*D; A += w*F(N, D)
    return EN/ED, A

if __name__ == '__main__':
    for n, vec in [(6, ('0.3', '0.1', '0.2', '0.05')), (7, ('0.01',)*4), (8, ('0.01',)*4), (8, ('0.1', '0', '0.2', '0.03'))]:
        v = tuple(map(F, vec)); Rb, Ab = brute(n, *v); Re, Ae = exact(n, *v)
        assert Rb == Re and Ab == Ae, (n, vec, Rb, Re, Ab, Ae)
    print("\nbrute-force enumeration of all loss patterns (n=6,7,8) == exact(): carried-count expression confirmed")
    # role-blind vs role-dependent cost per arm (targeted suppression, nominal 0.2 votes/view)
    for n in (16, 32):
        L = F(1, 5); pi0 = F(n+1, 2*(n-1))
        blind = pi0 - eq_pip(n, 1 - L/(n-1))
        for arm, vec in dict(a=(L, 0, 0, 0), g=(0, 0, L, 0), b=(0, L, 0, 0), o=(0, 0, 0, L/(n-4))).items():
            num, den = eq_role(n, *vec); cost = pi0 - num/den
            print(f"n={n} arm {arm}: role-dependent drop {float(cost):.5f}, role-blind drop {float(blind):.5f}, blind/actual {float(blind/cost):.2f}")
