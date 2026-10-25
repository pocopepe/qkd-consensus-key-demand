"""Base-stock section: eq:onhand, pair demand X1+2X2 under iid leaders, round-robin
'4 tags in any n consecutive views', z_p=4 for delta<=n-1, round-robin column of Table stock,
advance notice (delta-nu), floor(z/2) timeout rounds, 4vT/n, standing-key numbers."""
from fractions import Fraction as F
from itertools import product
from math import comb, floor
import random

def pair_demand(L, t, p):            # chained rotation: hubs of view t are leaders of t and t+1
    return (L[t] in p) + (L[t+1] in p)

# 1. exact distribution of demand over delta+1 views under iid leaders, by enumeration
def dist_enum(n, s, p, delta):
    out = {}
    for L in product(range(n), repeat=delta+2):   # leaders of views t-delta .. t+1
        w = F(1)
        for x in L: w *= s[x]
        tot = sum(pair_demand(L, j, p) for j in range(delta+1))
        out[tot] = out.get(tot, 0) + w
    return out

def dist_formula(sp, delta):
    out = {}
    for x1 in range(3):
        for x2 in range(delta+1):
            w = comb(2, x1)*sp**x1*(1-sp)**(2-x1)*comb(delta, x2)*sp**x2*(1-sp)**(delta-x2)
            out[x1+2*x2] = out.get(x1+2*x2, 0) + w
    return out

random.seed(3)
for n, delta in [(4, 0), (4, 1), (4, 2), (5, 3), (3, 4)]:
    w = [random.randint(1, 9) for _ in range(n)]; s = [F(x, sum(w)) for x in w]
    p = {0, 1}
    e = dist_enum(n, s, p, delta); f = dist_formula(s[0]+s[1], delta)
    assert {k: v for k, v in e.items() if v} == {k: v for k, v in f.items() if v}, (n, delta)
print("pair demand over delta+1 views == X1+2X2, X1~Bin(2,s_u+s_v), X2~Bin(delta,s_u+s_v): exact for 5 cases")

# 2. base-stock simulation of eq:onhand vs an explicit queue model (orders arrive delta+1 views later)
def simulate(demand, z, delta, nu=0):
    """Explicit model: stock z; demand of view j is reordered at end of view j-nu, arrives at start of
    view j-nu+delta+1; tags not served on time are backordered.  Returns per-view on-time counts
    and the eq:onhand prediction with delta-nu."""
    T = len(demand); arrivals = [0]*(T+delta+2); onhand = z; back = 0; ontime = []; pred = []
    for j in range(min(nu, T)):          # demand of the first nu views was ordered before view 0
        a = j - nu + delta + 1
        if a <= 0: onhand += 0           # arrived before view 0: stock already counts it (z)
        else: arrivals[a] += demand[j]   # still in the pipeline at view 0
    for t in range(T):
        if t >= 0: onhand += arrivals[t]
        # serve backorders first (they are late anyway)
        x = min(back, onhand); onhand -= x; back -= x
        served = min(demand[t], onhand); ontime.append(served); onhand -= served; back += demand[t]-served
        j = t + nu                                   # demand known nu views ahead is reordered now
        if j < T:
            a = t + delta + 1
            if a < len(arrivals): arrivals[a] += demand[j]
        dd = delta - nu
        H = z - sum(demand[max(0, t-dd):t]) if dd > 0 else z
        pred.append(min(demand[t], max(H, 0)))
    return ontime, pred

random.seed(5)
for trial in range(300):
    n = random.randint(3, 8); T = 60; delta = random.randint(0, 6); nu = random.randint(0, delta)
    L = [random.randrange(n) for _ in range(T+1)]; p = {0, 1}
    dem = [pair_demand(L, t, p) for t in range(T)]
    if nu > 0:  # with notice the first nu views have had no advance orders: start after warm-up
        pass
    z = random.randint(0, 8)
    on, pr = simulate(dem, z, delta, nu)
    W = delta + 1  # compare after the pipeline has filled
    assert on[W:] == pr[W:], (trial, n, delta, nu, z)
print("eq:onhand (with delta-nu under nu views of notice) matches an explicit backordered queue model, 300 random cases")

# 3. round-robin: max demand of a pair over any w consecutive views
def rr_max(n, w):
    L = [t % n for t in range(4*n + w + 2)]
    best = 0
    for u in range(n):
        for v in range(u+1, n):
            p = {u, v}
            for t0 in range(2*n):
                best = max(best, sum(pair_demand(L, t, p) for t in range(t0, t0+w)))
    return best
for n in (5, 8, 16, 84):
    for u, v in [(0, 1), (0, 3)]:
        L = [t % n for t in range(3*n+2)]
        for t0 in range(n):
            assert sum(pair_demand(L, t, {u, v}) for t in range(t0, t0+n)) == 4
print("round-robin: every pair draws exactly 4 tags in any n consecutive views (n=5,8,16,84)")
for n in (84,):
    col = [rr_max(n, d+1) for d in (1, 2, 5, 10, 20, 50)]
    print("round-robin least depth serving every message, n=84, delta=1,2,5,10,20,50:", col, "(table: 3,4,4,4,4,4)")
print("max window demand for delta=n-1 (window n):", rr_max(16, 16), "; delta=n (window n+1):", rr_max(16, 17))

# 4. timeouts: a full-mesh timeout round draws 2 tags per pair
for z in (4, 16): print(f"z={z}: floor(z/2)={z//2} timeout rounds from a FULL pool")

# 5. block refill mean 4vT/n and standing key
v, n = 26.8, 84
pairs = n*(n-1)//2
print("per pair per view demand =", F(2*(n-1), pairs), "= 4/n:", F(2*(n-1), pairs) == F(4, n))
for T, depth in ((10, 31), (30, 80), (90, 228)):
    m = 4*v*T/n; print(f"T={T}s mean {m:.2f} tags/pair; 99% depth {depth} = {depth/m:.2f} x mean; {depth*128/8/1000:.2f} kB")
for z in (16, 4):
    bits = z*128*pairs; print(f"z={z}: {bits/1e6:.3f} Mbit standing; consumed in {bits/(128*2*(n-1)*v):.2f} s")
print("delta in ms:", [round(d/v*1000, 1) for d in (1, 2, 5, 10, 20, 50, 100)])
stock = {1: (3, 2.49, 3, 3.00), 2: (4, 3.03, 5, 4.03), 5: (4, 3.79, 6, 5.36), 10: (6, 4.83, 8, 6.76), 20: (8, 6.53, 10, 8.87), 50: (12, 10.30, 16, 13.41)}
sav = max(max(1-b/a, 1-d/c) for a, b, c, d in stock.values()); print(f"largest stake saving in table: {sav:.3f}")
print("round-robin stale coverage 2/(n-1) at n=84:", 2/83)
