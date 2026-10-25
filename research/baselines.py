#!/usr/bin/env python3
"""Faithful reimplementation of the published predictive baseline.

Stan, Verchere, Vegas Olmos, Tafur Monroy and Rommel, "Dynamic-threshold-based
pre-relaying for enhanced key allocation in quantum-secured networks," JOCN
17(3), March 2025.

Comparing against "an EWMA" is not the same as comparing against their scheme,
and the difference matters: DT-VQKP is not a ranking rule, it is a hysteresis
controller over per-pair key pools. Its structure is

  * a virtual quantum key pool (VQKP) per source-destination pair, fed by
    trusted relay across the physical key pools (QKP) of the path;
  * an EWMA estimate of the next interval's application key demand per pair;
  * a lower and an upper threshold derived from that estimate, so a pool that
    drops below the lower threshold is pre-relayed up to the upper one;
  * thresholds that scale with predicted demand, which is what suppresses
    pre-relay requests at pairs with little traffic.

Reimplemented here against the same topology, demand and kernel budgets as
everything else, so the comparison is like for like.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class DTVQKP:
    """Dynamic-threshold virtual key pool controller.

    alpha       EWMA weight on observed per-pair demand
    k_low       lower threshold as a multiple of predicted demand
    k_high      refill target as a multiple of predicted demand
    floor_bits  absolute lower threshold, so a cold pair is still provisioned
    """
    alpha: float = 0.3
    k_low: float = 1.0
    k_high: float = 3.0
    floor_bits: float = 256.0

    dhat: dict = field(default_factory=dict)
    level: dict = field(default_factory=dict)
    name: str = "DT-VQKP"

    def observe(self, demand: dict) -> None:
        for p in set(self.dhat) | set(demand):
            obs = demand.get(p, 0.0)
            self.dhat[p] = self.alpha * obs + (1 - self.alpha) * self.dhat.get(p, obs)
            # consumption drains the virtual pool
            self.level[p] = max(0.0, self.level.get(p, 0.0) - obs)

    def thresholds(self, p):
        d = self.dhat.get(p, 0.0)
        return max(self.k_low * d, self.floor_bits), max(self.k_high * d,
                                                         self.floor_bits * 2)

    def select(self, cands, budget, resident, net, groups=None):
        """Pairs whose VQKP has fallen below its lower threshold, refilled to
        the upper one, ordered by deficit and truncated to the kernel budgets."""
        want = []
        for c in cands:
            p = c.pair
            lo, hi = self.thresholds(p)
            lvl = self.level.get(p, 0.0)
            if lvl < lo:
                want.append((hi - lvl, p, hi))
        want.sort(key=lambda t: -t[0])

        out, ent, upd = {}, 0, 0
        for deficit, p, target in want:
            c = next((x for x in cands if x.pair == p), None)
            if c is None:
                continue
            bits = min(target, c.bits if c.bits > 0 else target)
            if ent + c.weight > budget.max_entries:
                continue
            if p not in resident:
                if upd + 1 > budget.max_updates_per_round:
                    break
                upd += 1
            if not net.can_reserve(p[0], p[1], bits) and p not in resident:
                continue
            out[p] = bits
            self.level[p] = target
            ent += c.weight
        return out


@dataclass
class StaticThresholdVQKP(DTVQKP):
    """The pre-DT scheme: fixed thresholds for every pair, no demand estimate.

    Included because it isolates what the dynamic part of DT-VQKP actually buys
    -- if the two perform alike, the contribution is the pooling, not the
    prediction."""
    name: str = "static-threshold VQKP"
    fixed_low: float = 512.0
    fixed_high: float = 2048.0

    def thresholds(self, p):
        return self.fixed_low, self.fixed_high
