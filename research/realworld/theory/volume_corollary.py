#!/usr/bin/env python3
# Corollary 3 checked by enumeration: with m hubs of which k persist, a view demands D = m(n-1) tags,
# k(n-1) + m(m-k) of them on pairs used in the previous view, so U = (m-k)(n-1-m) are not.
from fractions import Fraction
from itertools import combinations


def U(n, m, k):
    return (m - k) * (n - 1 - m)


def star(R, n):
    return {frozenset((r, v)) for r in R for v in range(n) if v != r}


def brute(n, m, k):
    prev = set(range(m))
    cur = set(range(m - k, 2 * m - k))
    S_prev = star(prev, n)
    D = 0
    N = 0
    for p in star(cur, n):
        d = len(p & cur)
        D += d
        if p in S_prev:
            N += d
    return D, N


def check():
    for n in range(3, 21):
        for m in range(1, n):
            for k in range(0, m + 1):
                if 2 * m - k > n:
                    continue
                D, N = brute(n, m, k)
                assert D == m * (n - 1) and N == k * (n - 1) + m * (m - k), (n, m, k)
                assert D - N == U(n, m, k)
                assert Fraction(N, D) == Fraction(k * (n - 1) + m * (m - k), m * (n - 1))
    for n in range(4, 200):
        assert U(n, 2, 1) == n - 3 and U(n, n - 1, n - 1) == 0
    print("volume corollary verified by enumeration for every realizable (n, m, k) with n <= 20")


if __name__ == "__main__":
    check()
    print(" n   unicast D   unicast U   broadcast msgs   ratio broadcast/unicast")
    for n in (4, 16, 32, 64, 84, 100, 180):
        print(f"{n:4d}   {2 * (n - 1):8d}   {n - 3:8d}   {(n + 1) * (n - 1):12d}      {(n + 1) / 2:6.1f}")
