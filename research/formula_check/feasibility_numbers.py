"""Feasibility and budget numbers: Table keyrate, Table qkd, text around them, ring routing
(8R/N^2 by shortest paths, cut bound, 4R/[N(N-1)] ratio), Table chains, floor numbers."""
import os
import json
from fractions import Fraction as F

tau, v = 128, 26.8
def r(x, nd): return round(x, nd)

print("== Table keyrate ==")
paper = {16: (30, 13, 255, 102.9, 44.6, 0.87), 32: (62, 29, 1023, 212.6, 99.5, 3.51), 64: (126, 61, 4095, 432.1, 209.2, 14.04),
         84: (166, 81, 7055, 569.3, 277.8, 24.20), 100: (198, 97, 9999, 679.1, 332.7, 34.29)}
for n, row in paper.items():
    All, Fr, Br = 2*(n-1), n-3, (n+1)*(n-1)
    mine = (All, Fr, Br, r(All*tau*v/1e3, 1), r(Fr*tau*v/1e3, 1), r(Br*tau*v/1e6, 2))
    print(n, mine, "OK" if mine == row else f"MISMATCH paper {row}")
n = 84; pairs = n*(n-1)//2
print("pairs", pairs, "per-pair bit/s", r(166*tau*v/pairs, 1), r(7055*tau*v/pairs, 1), "ratio", 7055/166, (n+1)/2)

print("\n== ring routing ==")
def ring_shortest_load(N):
    """uniform demand 1 per unordered pair, shortest paths, antipodal pairs split 1/2-1/2; max link load"""
    load = [F(0)]*N
    for i in range(N):
        for j in range(i+1, N):
            cw = (j - i) % N; ccw = N - cw
            paths = []
            if cw <= ccw: paths.append([(i+s) % N for s in range(cw)])          # link k = (k,k+1)
            if ccw <= cw: paths.append([(j+s) % N for s in range(ccw)])
            for pth in paths:
                for k in pth: load[k] += F(1, len(paths))
    return max(load), min(load)
for N in (4, 6, 16, 84, 100):
    mx, mn = ring_shortest_load(N)
    assert mx == mn == F(N*N, 8)
    # per-pair rate x = R / max load  -> 8R/N^2 ; cut bound: 2R / (N/2)^2 = 8R/N^2
    print(f"N={N}: shortest-path load per link = N^2/8 = {mx}; x = 8R/N^2 equals cut bound 2R/(N^2/4); "
          f"ratio to 4R/[N(N-1)] = {F(8, N*N)/F(4, N*(N-1))} = 2(N-1)/N")

print("\n== Table qkd: v_max = 2R/(128 D) ==")
qk = {16: (1156, 136, 158, 18.6, 42.6, 5.01), 32: (559, 33.9, 76.6, 4.64, 20.6, 1.25), 64: (275, 8.47, 37.7, 1.16, 10.1, 0.31), 100: (175, 3.47, 24.0, 0.48, 6.45, 0.13)}
def sig3(x):
    from math import log10, floor
    d = 3 - 1 - floor(log10(abs(x))); return round(x, max(d, 0)) if d > 0 else round(x, d)
for n, row in qk.items():
    vals = []
    for R in (2.22e6, 304e3, 81.7e3):
        for D in (2*(n-1), (n+1)*(n-1)): vals.append(2*R/(tau*D))
    print(n, [f"{x:.4g}" for x in vals], "paper", row)
    for x, p in zip(vals, row):
        if abs(x - p) > 0.5*10**(len(str(p).split('.')[-1]) * -1 if '.' in str(p) else 0.5) and abs(x-p)/p > 0.006:
            print("   CHECK", x, p)
# 256-bit tags, 1.8 kbit/s, ceilings and the 'undecided' cells
print("256-bit: n=100 unicast", 2*2.22e6/(256*198), " n=32 broadcast", 2*2.22e6/(256*33*31))
print("1.8 kbit/s unicast n=16:", 2*1800/(tau*30), " n=100:", 2*1800/(tau*198))
print("ceiling broadcast n=64 2.22M:", 2*2.22e6/(tau*65*63)*2*63/64)
for R, n_, D, lab in [(304e3, 16, 17*15, 'bcast 304k n=16'), (304e3, 100, 198, 'uni 304k n=100'), (81.7e3, 32, 62, 'uni 81.7k n=32'),
                       (304e3, 32, 33*31, 'bcast 304k n=32'), (81.7e3, 16, 17*15, 'bcast 81.7k n=16'), (81.7e3, 64, 126, 'uni 81.7k n=64')]:
    g = 2*R/(tau*D); c = g*2*(n_-1)/n_
    print(f"{lab}: guaranteed {g:.2f}, shortest-path/ceiling {c:.2f}  (Aptos 26.8)")
print("fresh share U/D at 84:", 81/166)

print("\n== Table chains (recomputed from pattern, n, rate, 128-bit tags, ring 8R/n^2) ==")
chains = [
    ("Aptos", 84, lambda n: (2*n+1)*(n-1), 26.8, (14027, 26.8, '48.1M', '12.2M', 4.89, 0.0040)),
    ("Cosmos", 180, lambda n: (2*n+1)*(n-1), 1/5.9, (64619, 0.169, '1.4M', '352k', 1.07, 0.00087)),
    ("Polkadot", 599, lambda n: 2*n*(n-1)+(n-1), None, (717002, None, None, None, 0.0966, 0.000078)),
    ("Sui", 127, lambda n: n*(n-1), None, (16002, None, None, None, 4.3, 0.0035)),
    ("Solana", 672, lambda n: 2*(n-1), 4.54, (1342, 4.54, '779k', '195k', 51.6, 0.042)),
    ("Avalanche", 590, lambda n: 2*n*20*20, 1.01, (472000, 1.01, '60.8M', '15.2M', 0.147, 0.00012)),
    ("Ethereum", 846377, lambda n: n+64*16*32, 1/384, (879145, 0.0026, '293k', '73.3k', 0.0789, 0.000064)),
]
cb = {row['chain']: row for row in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'realworld', 'chains', 'CHAIN_BUDGET.json')))['rows']}
for name, n, pat, rate, paper_row in chains:
    T = pat(n); P = n*(n-1)/2
    dem = T*tau*rate if rate else None
    link = dem/P*n*n/8 if rate else None
    sus = lambda R: (8*R/(n*n))*P/(T*tau)           # decisions/s with per-pair rate 8R/n^2
    s_mega, s_kilo = sus(2.22e6), sus(1800)
    s_mega_g = (4*R/(n*(n-1)) if (R := 2.22e6) else 0)*P/(T*tau)   # under the guaranteed 4R/[n(n-1)]
    print(f"{name:9s} tags {T} (paper {paper_row[0]}) demand {dem and dem/1e6:.4g} Mbit/s link {link and link/1e3:.4g} kbit/s "
          f"sustained {s_mega:.4g} / {s_kilo:.3g} (paper {paper_row[4]} / {paper_row[5]}); under 4R/[n(n-1)]: {s_mega_g:.4g}"
          if rate else
          f"{name:9s} tags {T} (paper {paper_row[0]}) sustained {s_mega:.4g} / {s_kilo:.3g} (paper {paper_row[4]} / {paper_row[5]}); under 4R/[n(n-1)]: {s_mega_g:.4g}")
    j = cb['Cosmos Hub' if name == 'Cosmos' else name]
    assert j['tags_per_decision'] == T
    print(f"           JSON sustained {j['sustainable_decisions_per_s_megabit']:.4g}, JSON rate {j['rate_per_s']}")
print("margins: Solana", 51.618/4.535, "Cosmos", 1.0676/0.16949, "Aptos short", 26.795/4.887, "Avalanche short", 1.0057/0.14673,
      "Polkadot s/round", 1/0.096596, "Solana kilobit s/slot", 1/0.041853)
print("Ethereum pairs", 846377*846376//2, "Tbit", 846377*846376/2*128/1e12, "kbit/s", 879145*128/384/1e3)

print("\n== floor numbers ==")
for n in (84,):
    f = (n-1)//3
    print("f", f, "n(f+1)", n*(f+1), "broadcast/floor", (n+1)*(n-1)/(n*(f+1)), "ITHS 8(n-1)/(f+1)", 8*(n-1)/(f+1),
          "L* = n(f+1)/(2(n-1))", n*(f+1)/(2*(n-1)), "stake f+1=14:", n*14/(2*(n-1)))
for name, n, T, fp1 in [("Aptos", 84, 14027, None), ("Cosmos", 180, 64619, None), ("Polkadot", 599, 717002, None), ("Sui", 127, 16002, None), ("Avalanche", 590, 472000, None)]:
    f = (n-1)//3; print(name, "ratio to n(f+1):", round(T/(n*(f+1)), 3))
print("Aptos stake floor 84*14 =", 84*14, "ratio", 14027/1176, "; Solana floor 672*18 =", 672*18, "L* =", 672*18/1342)
print("ML-DSA-44 certificate n-f signatures at n=84:", (84-27)*2420, "bytes")
