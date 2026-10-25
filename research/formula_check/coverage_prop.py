"""Proposition 3 (coverage of RWC predictors): randomized test of the three cases, and EWMA condition."""
import random, sympy as sp
random.seed(7)
for trial in range(3000):
    E = list(range(random.randint(3, 15)))
    hist = [set(random.sample(E, random.randint(1, len(E)))) for _ in range(random.randint(2, 8))]
    w2 = [random.random() for _ in range(len(hist)-1)]
    w1 = sum(w2) + random.random() + 1e-9
    w = [w1] + w2                       # w[l-1] = weight of lag l
    Sm = hist[-1]
    score = {p: sum(w[l]*(p in hist[-1-l]) for l in range(len(hist))) for p in E}
    d = {p: random.randint(0, 3) for p in E}
    if sum(d.values()) == 0: continue
    B = random.randint(1, len(E))
    P = set(sorted(E, key=lambda p: (-score[p], p))[:B])
    gam = sum(d[p] for p in P)/sum(d.values()); pi = sum(d[p] for p in Sm)/sum(d.values())
    if len(Sm) == B: assert P == Sm and gam == pi
    elif len(Sm) > B: assert P < Sm and gam <= pi
    else: assert Sm < P and gam >= pi
print("Proposition 3: 3000 random histories/weights/budgets, all three cases hold")
a, l = sp.symbols('alpha l', positive=True)
tail = sp.summation(a*(1-a)**(l-1), (l, 2, sp.oo))
print("EWMA sum_{l>=2} w_l =", sp.simplify(tail.args[0][0] if isinstance(tail, sp.Piecewise) else tail), "-> dominance iff alpha > 1 - alpha iff alpha > 1/2")
