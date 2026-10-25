#!/usr/bin/env python3
"""Hybrid pre-arm optimiser: fractional seed plus randomised neighbourhood swap.

Density-greedy is essentially optimal on the plain map-capacity knapsack -- the
measured ratio is 0.9999 and Theorem 5 explains why: relay-hop weights are tiny
against M_max, so the instance is nearly fractional. The gap only opens once the
constraints stop being separable:

  link coupling   pairs sharing a relay hop draw on one key pool, so admitting
                  a high-density pair can make several others infeasible;
  quorum groups   value is a step function of covering 2f+1 pairs of a block,
                  not a sum over pairs;
  switching cost  entries already resident are free to keep and cost a syscall
                  to change, so the incumbent set is part of the instance.

Under those, greedy's single pass cannot back out of an early commitment. This
optimiser seeds from the fractional relaxation and then repairs by randomised
local search over add / drop / swap moves, which can.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

import numpy as np


@dataclass
class _Ctx:
    cands: list
    by_pair: dict
    groups: list
    net: object
    resident: dict
    max_entries: int
    max_updates: int
    link_free: dict
    credits: dict = field(default_factory=dict)
    credit_weight: float = 0.15


def _lkey(lk):
    return (lk.u, lk.v) if lk.u < lk.v else (lk.v, lk.u)


class HybridSwapOptimizer:
    """Fractional seed, then randomised add/drop/swap repair under a time budget."""

    name = "hybrid"

    def __init__(self, iters: int = 1200, restarts: int = 3,
                 time_budget_s: float = 0.02, seed: int = 0,
                 entry_cost: float = 0.004):
        # Cost charged per map entry held. Sweep B established that a
        # reservation is not free -- held key is unavailable key, and arming
        # past what completes a scenario converts directly into starvation.
        # Without this term the optimiser has no reason to stop, and it does
        # not: it arms every candidate that fits and loses to a fixed rule.
        self.entry_cost = entry_cost
        self.rng = random.Random(seed)
        self._credits: dict = {}
        self.iters = iters
        self.restarts = restarts
        self.time_budget = time_budget_s

    def set_credits(self, credits: dict) -> None:
        """Starvation credits from the kernel: pairs whose lease expired unused.

        Feeding them back means a pair the forecaster got wrong last view is
        ranked up rather than repeatedly skipped, which is what stops a
        persistent mis-forecast from starving one validator indefinitely."""
        self._credits = credits or {}

    # -- feasibility ------------------------------------------------------

    def _value(self, ctx, sel):
        """Scenario-aware value.

        A block pays out only when its quorum is covered, and a *scenario* pays
        out only when every block in it is covered. The view-change fabric is
        sixteen fan-in blocks that all happen together or not at all, so
        covering four of them is worth nothing -- scoring blocks independently
        makes the optimiser spend entries hedging an event it cannot actually
        cover, which is exactly how it lost to a fixed rule in sweep C."""
        if not ctx.groups:
            return sum(ctx.by_pair[p].utility for p in sel if p in ctx.by_pair)
        scen: dict = {}
        for g in ctx.groups:
            covered = sum(1 for p in g.pairs if p in sel) >= g.need()
            st = scen.setdefault(g.scenario, [True, g.prob])
            st[0] = st[0] and covered
            st[1] = max(st[1], g.prob)
        total = sum(prob for ok, prob in scen.values() if ok)
        # every held entry is key withdrawn from the pairs that need it now
        total -= self.entry_cost * sum(
            ctx.by_pair[p].weight for p in sel if p in ctx.by_pair)
        # small tie-break so partial progress toward a block is not invisible
        total += 1e-6 * sum(ctx.by_pair[p].utility for p in sel if p in ctx.by_pair)
        # starvation credits
        if self._credits:
            for (a, b) in sel:
                total += ctx.credit_weight * 1e-3 * (
                    self._credits.get(a, 0) + self._credits.get(b, 0))
        return total

    def _cost(self, ctx, sel):
        entries = 0
        updates = 0
        load: dict = {}
        for p in sel:
            c = ctx.by_pair.get(p)
            if c is None:
                return None
            entries += c.weight
            if p not in ctx.resident:
                updates += 1
            for lk in ctx.net.path_links(p[0], p[1]):
                load[_lkey(lk)] = load.get(_lkey(lk), 0.0) + c.bits
        return entries, updates, load

    def _feasible(self, ctx, sel):
        c = self._cost(ctx, sel)
        if c is None:
            return False
        entries, updates, load = c
        if entries > ctx.max_entries or updates > ctx.max_updates:
            return False
        for k, dem in load.items():
            if dem > ctx.link_free.get(k, 0.0) + 1e-9:
                return False
        return True

    # -- seeds ------------------------------------------------------------

    def _fractional_seed(self, ctx):
        """LP-order seed: densest first, skipping anything that breaks a pool."""
        sel = set()
        entries = updates = 0
        load: dict = {}
        for c in sorted(ctx.cands, key=lambda c: -c.utility / max(c.weight, 1)):
            p = c.pair
            if entries + c.weight > ctx.max_entries:
                continue
            inc_u = 0 if p in ctx.resident else 1
            if updates + inc_u > ctx.max_updates:
                continue
            lks = [_lkey(l) for l in ctx.net.path_links(p[0], p[1])]
            if any(load.get(k, 0.0) + c.bits > ctx.link_free.get(k, 0.0) + 1e-9
                   for k in lks):
                continue
            sel.add(p)
            entries += c.weight
            updates += inc_u
            for k in lks:
                load[k] = load.get(k, 0.0) + c.bits
        return sel

    def _group_seed(self, ctx, slack: int = 2):
        """Block-first seed: complete whole quorum blocks, cheapest quorum each.

        The slack matters more than it looks. A block covered at exactly its
        quorum has no liveness margin: one pair whose relay path cannot be
        reserved at commit time drops the block below threshold, and a block
        below threshold is worth nothing. Arming a couple of pairs past the
        quorum is what makes the seed survive contact with the network."""
        sel = set()
        if not ctx.groups:
            return sel
        for g in sorted(ctx.groups, key=lambda g: -g.prob):
            ranked = sorted(
                (p for p in g.pairs if p in ctx.by_pair),
                key=lambda p: (ctx.net.hops(p[0], p[1]), p))
            for k in (g.need() + slack, g.need() + 1, g.need()):
                trial = sel | set(ranked[:k])
                if self._feasible(ctx, trial):
                    sel = trial
                    break
        return sel

    # -- local search -----------------------------------------------------

    def _repair(self, ctx, sel, deadline):
        best = set(sel)
        best_v = self._value(ctx, best)
        cur = set(sel)
        cur_v = best_v
        pool = [c.pair for c in ctx.cands]
        if not pool:
            return best

        for it in range(self.iters):
            if it % 64 == 0 and time.perf_counter() > deadline:
                break
            move = self.rng.random()
            trial = set(cur)
            if move < 0.4 or not cur:
                trial.add(self.rng.choice(pool))               # add
            elif move < 0.6:
                trial.discard(self.rng.choice(tuple(cur)))     # drop
            else:
                trial.discard(self.rng.choice(tuple(cur)))     # swap
                trial.add(self.rng.choice(pool))
            if trial == cur or not self._feasible(ctx, trial):
                continue
            v = self._value(ctx, trial)
            if v > cur_v + 1e-12:
                cur, cur_v = trial, v
                if v > best_v:
                    best, best_v = set(trial), v
            elif v > cur_v - 1e-9 and self.rng.random() < 0.15:
                cur, cur_v = trial, v                          # lateral move
        return best

    # -- entry point ------------------------------------------------------

    def select(self, cands, budget, resident, net, groups=None):
        cands = [c for c in cands if net.hops(c.pair[0], c.pair[1]) > 0]
        if not cands:
            return {}
        link_free = {}
        for c in cands:
            for lk in net.path_links(c.pair[0], c.pair[1]):
                link_free[_lkey(lk)] = lk.free_bits
        ctx = _Ctx(cands=cands, by_pair={c.pair: c for c in cands},
                   groups=groups or [], net=net, resident=resident,
                   max_entries=budget.max_entries,
                   max_updates=budget.max_updates_per_round,
                   link_free=link_free, credits=self._credits)

        deadline = time.perf_counter() + self.time_budget
        seeds = [self._fractional_seed(ctx)]
        gs = self._group_seed(ctx)
        if gs:
            seeds.append(gs)
        best, best_v = set(), -1e18
        for s in seeds:
            if not self._feasible(ctx, s):
                s = set()
            r = self._repair(ctx, s, deadline)
            v = self._value(ctx, r)
            if v > best_v:
                best, best_v = r, v
        return {p: ctx.by_pair[p].bits for p in best}
