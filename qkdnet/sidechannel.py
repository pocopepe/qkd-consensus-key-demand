"""The pre-arm set is a side channel on the leader schedule."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .consensus import Pair


@dataclass
class LeakResult:
    top1_accuracy: float
    top2_accuracy: float
    baseline: float
    advantage: float
    mutual_info_bits: float


def infer_leader(prearm_set: set[Pair], n: int, k: int = 1) -> list[int]:
    """Rank validators by their degree in the observed pre-arm set."""
    deg = np.zeros(n)
    for (a, b) in prearm_set:
        if a < n:
            deg[a] += 1
        if b < n:
            deg[b] += 1
    return list(np.argsort(-deg)[:k])


def measure_leak(prearm_sets: list[set[Pair]], next_leaders: list[int],
                 n: int) -> LeakResult:
    """How well does the observed pre-arm set predict the next leader?"""
    if not prearm_sets:
        return LeakResult(0.0, 0.0, 1.0 / n, 0.0, 0.0)
    t1 = t2 = 0
    counts = np.zeros((n, n))     # predicted x actual, for the MI estimate
    for S, ell in zip(prearm_sets, next_leaders):
        ranked = infer_leader(S, n, k=2)
        if ranked and ranked[0] == ell:
            t1 += 1
        if ell in ranked:
            t2 += 1
        if ranked:
            counts[ranked[0], ell] += 1
    m = len(prearm_sets)
    p = counts / counts.sum() if counts.sum() else counts
    px = p.sum(axis=1, keepdims=True)
    py = p.sum(axis=0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        term = p * np.log2(p / (px * py))
    mi = float(np.nansum(np.where(p > 0, term, 0.0)))
    base = 1.0 / n
    acc1 = t1 / m
    return LeakResult(acc1, t2 / m, base,
                      (acc1 - base) / max(1.0 - base, 1e-9), mi)


class DecoyPrearmPolicy:
    """k-anonymity wrapper: hide the real stars among decoys."""

    def __init__(self, inner, n: int, decoys: int = 2, seed: int = 0):
        self.inner = inner
        self.n = n
        self.decoys = decoys
        self.rng = np.random.default_rng(seed)
        self.name = f"{getattr(inner, 'name', 'inner')}+decoy{decoys}"

    def select(self, cands, budget, resident, net, groups=None):
        base = (self.inner.select(cands, budget, resident, net, groups=groups)
                if groups is not None and
                getattr(self.inner, "name", "") in ("atomic", "quorum")
                else self.inner.select(cands, budget, resident, net))
        if self.decoys <= 0:
            return base
        bits = float(np.median(list(base.values()))) if base else 256.0
        used = sum(max(1, net.hops(a, b)) for (a, b) in base)
        centres = self.rng.choice(self.n, size=min(self.decoys, self.n),
                                  replace=False)
        for c in centres:
            for j in range(self.n):
                if j == c:
                    continue
                p = (int(min(c, j)), int(max(c, j)))
                if p in base:
                    continue
                w = max(1, net.hops(p[0], p[1]))
                if used + w > budget.max_entries:
                    break
                if not net.can_reserve(p[0], p[1], bits):
                    continue
                base[p] = bits
                used += w
        return base


def amplification_gain(n: int, tag_bits: float, msg_bits: float) -> float:
    """Key demand multiplier of a forced view change."""
    happy = 2.0 * (n - 1) * msg_bits
    vc = (n * (n - 1) / 2.0) * tag_bits
    return vc / happy


class UniformStarPolicy:
    """The defence that actually works: make the observable independent of the
    schedule by pre-arming every validator's star, not just the leaders'."""
    name = "uniform_quorum"

    def __init__(self, n: int, quorum: int, fraction: float = 1.0,
                 bits: float = 512.0, seed: int = 0, slack: int = 1):
        self.n = n
        self.quorum = quorum
        self.fraction = fraction
        self.bits = bits
        self.slack = slack
        self.rng = np.random.default_rng(seed)

    def select(self, cands, budget, resident, net, groups=None):
        k = max(1, int(round(self.fraction * self.n)))
        centres = self.rng.choice(self.n, size=k, replace=False) if k < self.n \
            else np.arange(self.n)
        # every star gets the same depth, so the observable carries no
        # information about which centre is the leader
        depth = min(self.quorum + self.slack, self.n - 1)
        chosen: dict[Pair, float] = {}
        used, updates = 0, 0
        order = list(centres)
        self.rng.shuffle(order)
        for c in order:
            ranked = sorted(
                ((net.hops(int(c), j), (int(min(c, j)), int(max(c, j))))
                 for j in range(self.n) if j != c),
                key=lambda t: (t[0], t[1]))
            ranked = [t for t in ranked if t[0] > 0]
            for h, p in ranked[:depth]:
                if p in chosen:
                    continue
                if used + max(1, h) > budget.max_entries:
                    break
                is_res = p in resident and abs(resident[p] - self.bits) < 1e-9
                if not is_res:
                    if updates + 1 > budget.max_updates_per_round:
                        break
                    if not net.can_reserve(p[0], p[1], self.bits):
                        continue
                    updates += 1
                    used += max(1, h)
                chosen[p] = self.bits
        return chosen


def measure_advance_leak(prearm_sets: list[set[Pair]], view_ids: list[int],
                         cons, n: int, offset: int) -> LeakResult:
    """Leakage about a leader `offset` views in the future."""
    if not prearm_sets:
        return LeakResult(0.0, 0.0, 1.0 / n, 0.0, 0.0)
    targets = [cons.leader(v + offset) for v in view_ids]
    return measure_leak(prearm_sets, targets, n)
