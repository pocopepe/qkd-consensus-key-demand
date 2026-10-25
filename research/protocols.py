#!/usr/bin/env python3
"""Consensus protocols as key-demand generators, across the complexity spectrum.

The question this module exists to answer: is the rotation blindspot a property
of chained HotStuff, or a property of a whole class of protocols? Each protocol
below is reduced to the only thing a key-supply layer sees -- which validator
pairs exchange an authenticated message in view t, and how much key that costs.

Protocols are grouped by the steady-state message complexity that the literature
uses to classify them, because that is the variable H1 claims is doing the work.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import numpy as np

Pair = tuple[int, int]


def pk(a: int, b: int) -> Pair:
    return (a, b) if a < b else (b, a)


class Protocol:
    """A protocol is a map from view index to pairwise key demand."""
    name = "base"
    complexity = "?"

    def __init__(self, n: int, tag_bits: float = 256.0, seed: int = 0):
        self.n = n
        self.tag = tag_bits
        self.rng = np.random.default_rng(seed)
        self.f = (n - 1) // 3

    def leader(self, view: int) -> int | None:
        return view % self.n

    def demand(self, view: int) -> dict[Pair, float]:
        raise NotImplementedError

    def star(self, c: int) -> dict[Pair, float]:
        return {pk(c, j): self.tag for j in range(self.n) if j != c}

    def all_to_all(self, mult: float = 1.0) -> dict[Pair, float]:
        return {(i, j): self.tag * mult
                for i in range(self.n) for j in range(i + 1, self.n)}

    @staticmethod
    def _merge(*ds):
        out: dict[Pair, float] = {}
        for d in ds:
            for p, b in d.items():
                out[p] = out.get(p, 0.0) + b
        return out


# ---------------------------------------------------------------------------
# O(n^2) steady state: every replica speaks to every replica, every view
# ---------------------------------------------------------------------------

class PBFT(Protocol):
    """PRE-PREPARE (leader -> all), PREPARE (all-to-all), COMMIT (all-to-all)."""
    name = "PBFT"
    complexity = "O(n^2)"

    def demand(self, view):
        ld = self.leader(view)
        return self._merge(self.star(ld), self.all_to_all(2.0))


class Tendermint(Protocol):
    """Proposal (leader -> all), PREVOTE and PRECOMMIT both all-to-all."""
    name = "Tendermint"
    complexity = "O(n^2)"

    def demand(self, view):
        ld = self.leader(view)
        return self._merge(self.star(ld), self.all_to_all(2.0))


class NarwhalDAG(Protocol):
    """Mempool DAG: every validator broadcasts its batch and certifies others.

    There is no leader on the data path at all -- ordering is derived from the
    DAG after the fact -- so the key demand is leader-independent by
    construction."""
    name = "Narwhal/DAG"
    complexity = "O(n^2)"

    def leader(self, view):
        return None                      # no leader in the data path

    def demand(self, view):
        return self.all_to_all(2.0)


# ---------------------------------------------------------------------------
# O(n) steady state: a rotating leader is the hub of every view
# ---------------------------------------------------------------------------

class ChainedHotStuff(Protocol):
    """Propose star at L(t), vote fan-in star at L(t+1). Threshold signatures
    collapse the quadratic phases into two stars."""
    name = "chained HotStuff"
    complexity = "O(n)"

    def demand(self, view):
        return self._merge(self.star(self.leader(view)),
                           self.star(self.leader(view + 1)))


class HotStuff2(Protocol):
    """Two-phase linear HotStuff: one proposal star and one vote star per view,
    same support as chained but a single round trip."""
    name = "HotStuff-2"
    complexity = "O(n)"

    def demand(self, view):
        return self._merge(self.star(self.leader(view)),
                           self.star(self.leader(view + 1)))


class Simplex(Protocol):
    """Leader multicasts the proposal; votes are all-to-all.

    Sits deliberately between the classes: one leader-dependent star on top of a
    leader-independent quadratic base. If H1 is right its persistence should
    land between the O(n) and O(n^2) groups rather than at either."""
    name = "Simplex"
    complexity = "O(n) + O(n^2) votes"

    def demand(self, view):
        return self._merge(self.star(self.leader(view)), self.all_to_all(1.0))


# ---------------------------------------------------------------------------
# Committee sortition: the support is a random subset, not a star
# ---------------------------------------------------------------------------

class AlgorandCommittee(Protocol):
    """A VRF-sampled committee of size c speaks each view.

    Committee membership is re-sampled every view and, under secret sortition,
    is not public in advance. This is the case where the demand support is
    neither persistent nor schedule-derivable, so both forecaster families
    should struggle -- which is the control H1 needs."""
    name = "Algorand committee"
    complexity = "O(c^2), c << n"

    def __init__(self, n, tag_bits=256.0, seed=0, committee_frac=0.25):
        super().__init__(n, tag_bits, seed)
        self.c = max(3, int(round(committee_frac * n)))
        self._cache: dict[int, list[int]] = {}

    def committee(self, view):
        if view not in self._cache:
            r = np.random.default_rng(hash((view, 0xC0FFEE)) % (2 ** 32))
            self._cache[view] = sorted(r.choice(self.n, size=self.c, replace=False))
        return self._cache[view]

    def leader(self, view):
        return int(self.committee(view)[0])

    def demand(self, view):
        cm = self.committee(view)
        return {pk(a, b): self.tag * 2.0 for a, b in itertools.combinations(cm, 2)}


PROTOCOLS = [PBFT, Tendermint, NarwhalDAG, Simplex, ChainedHotStuff, HotStuff2,
             AlgorandCommittee]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def support_persistence(proto: Protocol, views: int = 200, warm: int = 20) -> float:
    """Share of view t's demand carried by pairs already hot at t-1."""
    out = []
    prev = set(p for p, b in proto.demand(warm - 1).items() if b > 0)
    for t in range(warm, warm + views):
        d = proto.demand(t)
        tot = sum(d.values())
        if tot > 0:
            out.append(sum(b for p, b in d.items() if p in prev) / tot)
        prev = set(p for p, b in d.items() if b > 0)
    return float(np.mean(out)) if out else 0.0


def ewma_predict(hist: list[dict], alpha: float) -> dict[Pair, float]:
    dhat: dict[Pair, float] = {}
    for d in hist:
        for p in set(dhat) | set(d):
            dhat[p] = alpha * d.get(p, 0.0) + (1 - alpha) * dhat.get(p, 0.0)
    return dhat


def coverage_at(pred: dict[Pair, float], actual: dict[Pair, float], k: int) -> float:
    tot = sum(actual.values())
    if tot <= 0:
        return 1.0
    top = sorted((p for p in pred if pred[p] > 0), key=lambda p: -pred[p])[:k]
    return sum(actual.get(p, 0.0) for p in top) / tot


def evaluate(proto: Protocol, views: int = 220, warm: int = 20,
             alphas=(0.1, 0.3, 0.5, 0.7, 0.9)) -> dict:
    """Coverage of EWMA (best alpha) and of a schedule-aware structural
    forecaster, at a budget equal to the protocol's own support size."""
    supports = [len([p for p, b in proto.demand(t).items() if b > 0])
                for t in range(warm, warm + views)]
    K = int(np.ceil(np.mean(supports)))

    best_ewma, best_a = -1.0, None
    for a in alphas:
        hist, cov = [], []
        for t in range(warm + views):
            d = proto.demand(t)
            if t >= warm:
                cov.append(coverage_at(ewma_predict(hist[-24:], a), d, K))
            hist.append(d)
        m = float(np.mean(cov))
        if m > best_ewma:
            best_ewma, best_a = m, a

    # structural: the forecaster knows the schedule and the protocol, so it
    # predicts the exact support of view t. For secret sortition it cannot,
    # and falls back to the long-run marginal frequency of each pair.
    struct = []
    marg: dict[Pair, float] = {}
    for t in range(warm + views):
        d = proto.demand(t)
        if isinstance(proto, AlgorandCommittee):
            pred = dict(marg) if marg else {p: 1.0 for p in d}
        else:
            pred = d
        if t >= warm:
            struct.append(coverage_at(pred, d, K))
        for p, b in d.items():
            marg[p] = marg.get(p, 0.0) + b
    return {"K": K, "ewma": best_ewma, "alpha": best_a,
            "structural": float(np.mean(struct)),
            "gain": float(np.mean(struct)) - best_ewma}


def leakage(proto: Protocol, views: int = 220, warm: int = 20) -> dict:
    """Mutual information between the leader and the pre-armed support.

    The pre-arm set of a structural policy is the predicted support of the next
    view. An adversary ranks validators by their degree in that set. If the
    support is leader-independent the ranking is uninformative by construction;
    if it is a star, the ranking names the leader outright."""
    n = proto.n
    hits = 0
    trials = 0
    counts = np.zeros((n, n))
    for t in range(warm, warm + views):
        ld = proto.leader(t)
        if ld is None:
            continue
        S = [p for p, b in proto.demand(t).items() if b > 0]
        deg = np.zeros(n)
        for (a, b) in S:
            deg[a] += 1
            deg[b] += 1
        guess = int(np.argmax(deg + proto.rng.random(n) * 1e-9))
        counts[guess, ld] += 1
        hits += int(guess == ld)
        trials += 1
    if trials == 0:
        return {"top1": 1.0 / n, "baseline": 1.0 / n, "mi_bits": 0.0,
                "advantage": 0.0}
    p = counts / counts.sum()
    px, py = p.sum(1, keepdims=True), p.sum(0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        term = p * np.log2(p / (px * py))
    mi = float(np.nansum(np.where(p > 0, term, 0.0)))
    base = 1.0 / n
    acc = hits / trials
    return {"top1": acc, "baseline": base, "mi_bits": mi,
            "advantage": (acc - base) / max(1 - base, 1e-9)}
