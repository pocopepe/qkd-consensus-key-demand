#!/usr/bin/env python3
"""Discrete-event simulation of a QKD-secured validator ring.

Time-stepped models hide the thing that actually hurts a key-supply layer: key
does not arrive in per-view lumps, it trickles in as individual sifted blocks
whose arrival is a point process, and a request that misses by one block waits
for the next one. This engine is event-driven so that ordering, contention and
partial arrivals are represented rather than averaged away.

Events carry (time, seq, kind, payload); seq breaks ties deterministically so a
run is reproducible from its seed alone.
"""
from __future__ import annotations

import heapq
import itertools
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import IntEnum

import numpy as np


class Kind(IntEnum):
    KEY_BLOCK = 0        # a sifted key block completes on a link
    VIEW_START = 1       # a consensus view begins
    KEY_REQUEST = 2      # a validator pair needs key
    REQUEST_DONE = 3     # a request completed (fast, slow, or after waiting)
    LEASE_EXPIRY = 4     # a pre-arm lease times out and rolls back
    JAM_START = 5
    JAM_END = 6
    CONTROL_TICK = 7     # control plane recomputes and commits


@dataclass(order=True)
class Event:
    time: float
    seq: int
    kind: int = field(compare=False)
    payload: object = field(compare=False, default=None)


class Engine:
    """Minimal deterministic event loop."""

    def __init__(self, seed: int = 0):
        self.now = 0.0
        self._q: list[Event] = []
        self._seq = itertools.count()
        self._handlers: dict[int, list] = defaultdict(list)
        self.rng = np.random.default_rng(seed)
        self.stopped = False

    def at(self, t: float, kind: int, payload=None) -> None:
        heapq.heappush(self._q, Event(t, next(self._seq), kind, payload))

    def after(self, dt: float, kind: int, payload=None) -> None:
        self.at(self.now + max(0.0, dt), kind, payload)

    def on(self, kind: int, fn) -> None:
        self._handlers[kind].append(fn)

    def run(self, until: float) -> None:
        while self._q and not self.stopped:
            ev = heapq.heappop(self._q)
            if ev.time > until:
                self.now = until
                break
            self.now = ev.time
            for fn in self._handlers[ev.kind]:
                fn(ev)


# ---------------------------------------------------------------------------
# Physical layer
# ---------------------------------------------------------------------------

ALPHA_DB_PER_KM = 0.2


@dataclass
class QKDLink:
    """A trusted-relay hop with a stochastic secret-key generation process.

    Sifted blocks complete as a Poisson process whose rate is set by the
    channel's transmittance. Modelling arrivals rather than a smooth rate is
    what lets a request miss by one block and have to wait, which is the
    starvation mode a rate model cannot express.
    """
    u: int
    v: int
    distance_km: float
    block_bits: int = 1024
    pool_capacity_bits: float = 2.0e6
    r0_bps: float = 2.0e7
    # multiplicative degradation from jamming, in [0, 1]
    impairment: float = 1.0

    stored_bits: float = 0.0
    reserved_bits: float = 0.0
    blocks_generated: int = 0
    blocks_dropped_full: int = 0

    @property
    def nominal_bps(self) -> float:
        eta = 10.0 ** (-ALPHA_DB_PER_KM * self.distance_km / 10.0)
        return self.r0_bps * eta

    @property
    def effective_bps(self) -> float:
        return self.nominal_bps * self.impairment

    @property
    def free_bits(self) -> float:
        return max(0.0, self.stored_bits - self.reserved_bits)

    def next_block_delay(self, rng) -> float:
        """Exponential inter-arrival for the next sifted block."""
        rate = self.effective_bps / self.block_bits
        if rate <= 1e-9:
            return float("inf")
        return float(rng.exponential(1.0 / rate))

    def deposit(self) -> bool:
        if self.stored_bits + self.block_bits > self.pool_capacity_bits:
            self.blocks_dropped_full += 1
            return False
        self.stored_bits += self.block_bits
        self.blocks_generated += 1
        return True


class JammingSource:
    """Physical-layer optical jamming with a finite attack radius.

    A high-power in-band signal injected at one node leaks through the optical
    switches into neighbouring spans, degrading the secret-key rate on every
    link within `radius` hops by a distance-decayed factor. Following the attack
    model of Li et al., the damage is not confined to the injection point, which
    is what makes the reachable set -- rather than any single link -- the thing
    the routing layer has to keep small.
    """

    def __init__(self, engine: Engine, net: "QKDNetworkDE", node: int,
                 radius: int = 2, depth: float = 0.15,
                 mean_on_s: float = 0.4, mean_off_s: float = 6.0):
        self.e, self.net, self.node = engine, net, node
        self.radius, self.depth = radius, depth
        self.mean_on, self.mean_off = mean_on_s, mean_off_s
        self.active = False
        self.total_on_s = 0.0
        self._on_since = 0.0
        engine.on(Kind.JAM_START, self._start)
        engine.on(Kind.JAM_END, self._end)
        engine.after(float(engine.rng.exponential(mean_off_s)), Kind.JAM_START, self)

    def _affected(self) -> dict[tuple[int, int], float]:
        """Links within `radius` hops, with a decayed impairment factor."""
        out = {}
        frontier = {self.node}
        seen = {self.node}
        for hop in range(self.radius):
            nxt = set()
            for a in frontier:
                for b in self.net.neighbours(a):
                    k = self.net.key(a, b)
                    factor = self.depth ** (1.0 / (hop + 1))
                    out[k] = min(out.get(k, 1.0), factor)
                    if b not in seen:
                        seen.add(b); nxt.add(b)
            frontier = nxt
        return out

    def _start(self, ev):
        if ev.payload is not self or self.active:
            return
        self.active = True
        self._on_since = self.e.now
        for k, f in self._affected().items():
            self.net.links[k].impairment *= f
        self.e.after(float(self.e.rng.exponential(self.mean_on)), Kind.JAM_END, self)

    def _end(self, ev):
        if ev.payload is not self or not self.active:
            return
        self.active = False
        self.total_on_s += self.e.now - self._on_since
        for k, f in self._affected().items():
            self.net.links[k].impairment = min(1.0, self.net.links[k].impairment / f)
        self.e.after(float(self.e.rng.exponential(self.mean_off)), Kind.JAM_START, self)


class QKDNetworkDE:
    """Trusted-relay topology whose links generate key as point processes."""

    def __init__(self, engine: Engine, n_validators: int, seed: int = 0,
                 chord_prob: float = 0.25, target_bps: tuple[float, float] = (1e6, 2e6)):
        self.e = engine
        self.n = n_validators
        self.links: dict[tuple[int, int], QKDLink] = {}
        self.validators = list(range(n_validators))
        rng = np.random.default_rng(seed)
        # choose distances so effective rates land in the 1-2 Mbit/s band the
        # proposal quotes for a deployed metro link
        def dist_for(bps):
            return -10.0 * math.log10(bps / 2.0e7) / ALPHA_DB_PER_KM
        for i in range(n_validators):
            j = (i + 1) % n_validators
            self.add(i, j, dist_for(rng.uniform(*target_bps)))
        for i, j in itertools.combinations(range(n_validators), 2):
            if self.key(i, j) not in self.links and rng.random() < chord_prob:
                self.add(i, j, dist_for(rng.uniform(*target_bps)))
        self._paths: dict[tuple[int, int], list[int]] = {}
        engine.on(Kind.KEY_BLOCK, self._on_block)
        for k in self.links:
            self._arm(k)

    @staticmethod
    def key(u, v): return (u, v) if u < v else (v, u)

    def add(self, u, v, d):
        lk = QKDLink(u, v, d)
        lk.stored_bits = lk.pool_capacity_bits * 0.35
        self.links[self.key(u, v)] = lk
        return lk

    def _arm(self, k):
        self.e.after(self.links[k].next_block_delay(self.e.rng), Kind.KEY_BLOCK, k)

    def _on_block(self, ev):
        k = ev.payload
        if k not in self.links:
            return
        self.links[k].deposit()
        self._arm(k)

    def neighbours(self, u):
        return [b if a == u else a for (a, b) in self.links if u in (a, b)]

    def path(self, s, d):
        if s == d:
            return [s]
        ck = (s, d)
        if ck in self._paths:
            return self._paths[ck]
        import heapq as hq
        dist, prev, pq = {s: 0.0}, {}, [(0.0, s)]
        while pq:
            c, u = hq.heappop(pq)
            if u == d:
                break
            if c > dist.get(u, 1e18):
                continue
            for w in self.neighbours(u):
                nc = c + 1.0 / max(self.links[self.key(u, w)].nominal_bps, 1.0)
                if nc < dist.get(w, 1e18):
                    dist[w] = nc; prev[w] = u; hq.heappush(pq, (nc, w))
        if d not in prev:
            self._paths[ck] = []
            return []
        out, x = [d], d
        while x != s:
            x = prev[x]; out.append(x)
        out.reverse()
        self._paths[ck] = out
        return out

    def path_links(self, s, d):
        p = self.path(s, d)
        return [self.links[self.key(p[i], p[i + 1])] for i in range(len(p) - 1)]

    def hops(self, s, d): return max(0, len(self.path(s, d)) - 1)

    def can_reserve(self, s, d, bits):
        ls = self.path_links(s, d)
        return bool(ls) and all(l.free_bits >= bits for l in ls)

    def reserve(self, s, d, bits):
        if not self.can_reserve(s, d, bits):
            return False
        for l in self.path_links(s, d):
            l.reserved_bits += bits
        return True

    def release(self, s, d, bits):
        for l in self.path_links(s, d):
            l.reserved_bits = max(0.0, l.reserved_bits - bits)

    def consume(self, s, d, bits, from_reservation):
        ls = self.path_links(s, d)
        if not ls:
            return False
        if from_reservation:
            for l in ls:
                l.reserved_bits = max(0.0, l.reserved_bits - bits)
                l.stored_bits = max(0.0, l.stored_bits - bits)
            return True
        if not all(l.free_bits >= bits for l in ls):
            return False
        for l in ls:
            l.stored_bits -= bits
        return True

    def time_to_afford(self, s, d, bits) -> float:
        """Seconds until every hop can cover `bits`, at current effective rates."""
        worst = 0.0
        for l in self.path_links(s, d):
            deficit = bits - l.free_bits
            if deficit > 0:
                worst = max(worst, deficit / max(l.effective_bps, 1.0))
        return worst

    def total_stored(self): return sum(l.stored_bits for l in self.links.values())
    def mean_impairment(self):
        return float(np.mean([l.impairment for l in self.links.values()]))


# ---------------------------------------------------------------------------
# Workload
# ---------------------------------------------------------------------------

@dataclass
class BurstyWorkload:
    """Consensus load with flash crowds.

    Between bursts the cluster runs its steady O(n) view pattern. A flash crowd
    -- a mempool spike, a coordinated submission, a partition healing -- raises
    the number of consensus messages per view and the probability that a view
    times out, which is the regime where a demand forecaster is asked to do
    something other than repeat itself.
    """
    n: int
    base_msgs_per_view: float = 1.0
    burst_multiplier: float = 6.0
    burst_mean_views: float = 4.0
    burst_prob: float = 0.02
    base_timeout_prob: float = 0.02
    burst_timeout_prob: float = 0.25

    _burst_left: int = 0

    def step(self, rng) -> tuple[float, float, bool]:
        """Returns (message multiplier, timeout probability, in_burst)."""
        if self._burst_left > 0:
            self._burst_left -= 1
            return self.burst_multiplier, self.burst_timeout_prob, True
        if rng.random() < self.burst_prob:
            self._burst_left = max(1, int(rng.exponential(self.burst_mean_views)))
            return self.burst_multiplier, self.burst_timeout_prob, True
        return self.base_msgs_per_view, self.base_timeout_prob, False


if __name__ == "__main__":
    e = Engine(seed=1)
    net = QKDNetworkDE(e, 16, seed=1)
    jam = JammingSource(e, net, node=4, radius=2, depth=0.15)
    e.run(until=5.0)
    rates = [l.effective_bps / 1e6 for l in net.links.values()]
    print(f"links={len(net.links)}  "
          f"effective rate: min={min(rates):.2f} mean={np.mean(rates):.2f} "
          f"max={max(rates):.2f} Mbit/s")
    print(f"blocks generated={sum(l.blocks_generated for l in net.links.values())}  "
          f"stored={net.total_stored()/1e6:.2f} Mbit  "
          f"mean impairment={net.mean_impairment():.3f}  "
          f"jam on for {jam.total_on_s:.2f}s of 5.0s")
