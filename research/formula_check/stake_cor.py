"""Corollary 2 (eq:stake): exhaustive enumeration over leader triples (a,b,c) with exact
rational stakes, pi_t computed from the definitions (hub multiset, d_t counted per role).
Also the Aptos cross-check of q=sum s_i^2, eta, eq:stake value and the stake count over 1/3."""
from fractions import Fraction as F
from itertools import product
import random, json, glob, os
from thm1_lemma import pi_t  # same definitions as the Theorem check

def eq_stake(s, n):
    q = sum(x*x for x in s); eta = sum(x**3 for x in s)
    return (2*q - eta) + (q - eta)*F(n, 2*(n-1)) + (1 - 3*q + 2*eta)*F(n+1, 2*(n-1))

random.seed(1)
for trial in range(12):
    n = random.randint(3, 7)
    w = [random.randint(1, 20) for _ in range(n)]
    if trial == 0: w = [1]*n
    if trial == 1: w = [50] + [1]*(n-1)
    s = [F(x, sum(w)) for x in w]
    E = sum(s[a]*s[b]*s[c]*pi_t([a, b], [b, c], n)[0] for a, b, c in product(range(n), repeat=3))
    assert E == eq_stake(s, n), (n, w, E, eq_stake(s, n))
print("eq:stake equals exhaustive E[pi_t] exactly for 12 stake vectors, n=3..7")

# Aptos cross-check from the repo's raw epoch files (not the paper's source of numbers)
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'realworld')
rows = []
for f in sorted(glob.glob(base + '/raw_v3/epoch_*.json')):
    d = json.load(open(f)); vp = [int(v['voting_power']) for v in d['validators']]
    tot = sum(vp); s = [F(x, tot) for x in vp]
    q = sum(x*x for x in s); eta = sum(x**3 for x in s)
    srt = sorted(vp, reverse=True); acc = 0; cnt_gt = cnt_ge = None
    for i, x in enumerate(srt, 1):
        acc += x
        if cnt_ge is None and 3*acc >= tot: cnt_ge = i
        if cnt_gt is None and 3*acc > tot: cnt_gt = i
    rows.append((d['epoch'], len(vp), float(q), float(eta), float(eq_stake(s, len(vp))), cnt_ge, cnt_gt))
for r in rows[:5]: print(r)
qs = [r[2] for r in rows]; es = [r[4] for r in rows]
print(f"raw_v3: {len(rows)} epochs, n in {sorted(set(r[1] for r in rows))}, q mean {sum(qs)/len(qs):.4f} [{min(qs):.4f},{max(qs):.4f}], "
      f"eq:stake mean {sum(es)/len(es):.4f}, count>=1/3 {sorted(set(r[5] for r in rows))}, count>1/3 {sorted(set(r[6] for r in rows))}")
# equal-stake edge case for the 'exceeds' wording
for n in (84, 85, 86):
    f = (n-1)//3
    gt = next(c for c in range(1, n+1) if 3*c > n); ge = next(c for c in range(1, n+1) if 3*c >= n)
    print(f"equal stakes n={n}: f+1={f+1}, smallest count with stake >1/3 = {gt}, >=1/3 = {ge}")

import sympy as sp
q, e, n = sp.symbols('q eta n', positive=True)
E = (2*q - e) + (q - e)*n/(2*(n-1)) + (1 - 3*q + 2*e)*(n+1)/(2*(n-1))
diff = sp.simplify(E - (n+1)/(2*(n-1)))
print("E[pi_t] - pi_chained =", sp.factor(diff), "; with eta<=q: >=", sp.factor(diff.subs(e, q)), "(>=0 for n>=3)")
