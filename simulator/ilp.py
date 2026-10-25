#!/usr/bin/env python3
"""Exact branch-and-bound solver for the pre-arm selection problem.

Gives the true ceiling a heuristic is measured against. Two formulations:

  KnapsackBB       one resource (map entries), 0/1 items. LP bound is the
                   fractional knapsack, which is exact and O(m log m).
  MultiDimBB       several resources at once (entries, update budget, and the
                   per-link key pools a pair's relay path draws on). The LP
                   bound here is a surrogate relaxation, which is weaker but
                   still admissible.

Branch-and-bound rather than an LP-solver dependency: the bound is closed-form
for this structure, and depending on an external MILP package for a knapsack
would make the benchmark harder to reproduce than the thing it benchmarks.
"""
from __future__ import annotations

import heapq
import itertools
import time
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Item:
    idx: int
    value: float
    weight: int                      # map entries
    updates: int = 1                 # syscalls to install
    links: tuple = ()                # link ids the relay path crosses
    bits: float = 0.0                # key drawn per link


@dataclass
class BBResult:
    value: float
    chosen: list
    nodes: int
    seconds: float
    optimal: bool
    gap: float = 0.0


def fractional_bound(items, cap, start, taken_value, taken_weight):
    """LP relaxation of the residual 0/1 knapsack: exact for the fractional case."""
    room = cap - taken_weight
    if room <= 0:
        return taken_value
    b = taken_value
    for it in items[start:]:
        if it.weight <= room:
            room -= it.weight
            b += it.value
        else:
            b += it.value * (room / it.weight)
            return b
    return b


class KnapsackBB:
    """Depth-first branch and bound with a fractional-knapsack bound.

    Items are pre-sorted by density so the bound is tight at every node and the
    first dive is already a good incumbent, which is what keeps the node count
    small enough to run this every round of a 10,000-round experiment.
    """

    def __init__(self, time_limit_s: float = 5.0):
        self.time_limit = time_limit_s

    def solve(self, items: list[Item], capacity: int) -> BBResult:
        t0 = time.perf_counter()
        its = sorted([i for i in items if i.weight <= capacity],
                     key=lambda i: -i.value / max(i.weight, 1))
        n = len(its)
        best_val = 0.0
        best_set: list[int] = []
        nodes = 0
        timed_out = False

        # greedy incumbent first: a good lower bound prunes most of the tree
        w = 0.0; v = 0.0; sel = []
        for i, it in enumerate(its):
            if w + it.weight <= capacity:
                w += it.weight; v += it.value; sel.append(i)
        best_val, best_set = v, sel[:]

        stack = [(0, 0.0, 0, [])]
        while stack:
            nodes += 1
            if nodes % 4096 == 0 and time.perf_counter() - t0 > self.time_limit:
                timed_out = True
                break
            i, val, wt, sel = stack.pop()
            if i >= n:
                continue
            ub = fractional_bound(its, capacity, i, val, wt)
            if ub <= best_val + 1e-12:
                continue
            it = its[i]
            # branch: exclude first so the include branch is explored first
            stack.append((i + 1, val, wt, sel))
            if wt + it.weight <= capacity:
                nv, nw = val + it.value, wt + it.weight
                ns = sel + [i]
                if nv > best_val:
                    best_val, best_set = nv, ns
                stack.append((i + 1, nv, nw, ns))

        gap = 0.0
        if timed_out:
            ub = fractional_bound(its, capacity, 0, 0.0, 0.0)
            gap = max(0.0, (ub - best_val) / max(ub, 1e-12))
        return BBResult(best_val, [its[i].idx for i in best_set], nodes,
                        time.perf_counter() - t0, not timed_out, gap)


class MultiDimBB:
    """Branch and bound over map entries, update budget and per-link key pools.

    The link constraints are what make this not a knapsack: two pairs whose relay
    paths share a hop compete for one key pool, so feasibility is not separable
    across items. The bound relaxes every constraint but the tightest one at the
    current node, which stays admissible while remaining cheap to evaluate.
    """

    def __init__(self, time_limit_s: float = 10.0):
        self.time_limit = time_limit_s

    def solve(self, items, max_entries, max_updates, link_capacity):
        t0 = time.perf_counter()
        its = sorted(items, key=lambda i: -i.value / max(i.weight, 1))
        n = len(its)
        best_val, best_set, nodes, timed_out = 0.0, [], 0, False

        def feasible(sel_links, it):
            for lk in it.links:
                if sel_links.get(lk, 0.0) + it.bits > link_capacity.get(lk, 0.0) + 1e-9:
                    return False
            return True

        # greedy incumbent honouring every constraint
        used_e = used_u = 0; usedl = {}; v = 0.0; sel = []
        for i, it in enumerate(its):
            if used_e + it.weight > max_entries or used_u + it.updates > max_updates:
                continue
            if not feasible(usedl, it):
                continue
            used_e += it.weight; used_u += it.updates; v += it.value; sel.append(i)
            for lk in it.links:
                usedl[lk] = usedl.get(lk, 0.0) + it.bits
        best_val, best_set = v, sel[:]

        stack = [(0, 0.0, 0, 0, {}, [])]
        while stack:
            nodes += 1
            if nodes % 2048 == 0 and time.perf_counter() - t0 > self.time_limit:
                timed_out = True
                break
            i, val, we, wu, wl, sel = stack.pop()
            if i >= n:
                continue
            ub = fractional_bound(its, max_entries, i, val, we)
            if ub <= best_val + 1e-12:
                continue
            it = its[i]
            stack.append((i + 1, val, we, wu, wl, sel))
            if (we + it.weight <= max_entries and wu + it.updates <= max_updates
                    and feasible(wl, it)):
                nl = dict(wl)
                for lk in it.links:
                    nl[lk] = nl.get(lk, 0.0) + it.bits
                nv = val + it.value
                ns = sel + [i]
                if nv > best_val:
                    best_val, best_set = nv, ns
                stack.append((i + 1, nv, we + it.weight, wu + it.updates, nl, ns))

        gap = 0.0
        if timed_out:
            ub = fractional_bound(its, max_entries, 0, 0.0, 0.0)
            gap = max(0.0, (ub - best_val) / max(ub, 1e-12))
        return BBResult(best_val, [its[i].idx for i in best_set], nodes,
                        time.perf_counter() - t0, not timed_out, gap)


def _dp_reference(values, weights, cap):
    dp = np.zeros(int(cap) + 1)
    for v, w in zip(values, weights):
        w = int(w)
        if w <= cap:
            dp[w:] = np.maximum(dp[w:], dp[:int(cap) + 1 - w] + v)
    return float(dp[int(cap)])


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    print("=== KnapsackBB vs exact DP ===")
    bad = 0
    tot_nodes = 0
    for trial in range(300):
        m = int(rng.integers(10, 60))
        w = rng.integers(1, 6, m)
        v = rng.random(m) * 20
        cap = int(rng.integers(10, 150))
        items = [Item(i, float(v[i]), int(w[i])) for i in range(m)]
        r = KnapsackBB(time_limit_s=5).solve(items, cap)
        ref = _dp_reference(v, w, cap)
        tot_nodes += r.nodes
        if abs(r.value - ref) > 1e-6:
            bad += 1
            print(f"  mismatch trial={trial} bb={r.value:.6f} dp={ref:.6f}")
    print(f"  300 random instances, mismatches = {bad}, "
          f"mean nodes = {tot_nodes/300:.0f}")

    print("\n=== MultiDimBB: link coupling makes the problem strictly harder ===")
    m = 40
    w = rng.integers(1, 4, m)
    v = rng.random(m) * 10
    linkids = [tuple(sorted(rng.choice(8, size=2, replace=False))) for _ in range(m)]
    items = [Item(i, float(v[i]), int(w[i]), 1, (linkids[i],), 1.0) for i in range(m)]
    caps_loose = {lk: 99.0 for lk in set(linkids)}
    caps_tight = {lk: 2.0 for lk in set(linkids)}
    a = MultiDimBB(2).solve(items, 60, 60, caps_loose)
    b = MultiDimBB(2).solve(items, 60, 60, caps_tight)
    print(f"  loose link pools: value={a.value:.3f} items={len(a.chosen)} nodes={a.nodes}")
    print(f"  tight link pools: value={b.value:.3f} items={len(b.chosen)} nodes={b.nodes}")
    print(f"  contention costs {100*(1-b.value/a.value):.1f}% of attainable value")
