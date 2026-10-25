"""QKD network substrate: trusted-relay graph, per-link secret-key rates, key
pools."""
from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field

import numpy as np

ALPHA_DB_PER_KM = 0.2
R0_BPS = 2.0e7


def secret_key_rate(distance_km: float, r0: float = R0_BPS,
                    alpha: float = ALPHA_DB_PER_KM) -> float:
    """Asymptotic decoy-BB84 secret-key rate in bit/s over `distance_km` of fibre."""
    eta = 10.0 ** (-alpha * distance_km / 10.0)
    return r0 * eta


@dataclass
class Link:
    u: int
    v: int
    distance_km: float
    rate_bps: float
    capacity_bits: float
    stored_bits: float = 0.0
    # bits reserved by pre-arming but not yet consumed; released on TTL expiry
    reserved_bits: float = 0.0

    @property
    def free_bits(self) -> float:
        return max(0.0, self.stored_bits - self.reserved_bits)

    def replenish(self, dt_s: float) -> float:
        """Advance key generation by dt_s seconds; returns bits actually stored."""
        gained = self.rate_bps * dt_s
        before = self.stored_bits
        self.stored_bits = min(self.capacity_bits, self.stored_bits + gained)
        return self.stored_bits - before


@dataclass
class QKDNetwork:
    """Trusted-relay QKD network. Nodes 0..n_nodes-1; validators sit on a subset."""
    n_nodes: int
    links: dict[tuple[int, int], Link] = field(default_factory=dict)
    validators: list[int] = field(default_factory=list)
    _path_cache: dict[tuple[int, int], list[int]] = field(default_factory=dict, repr=False)

    @staticmethod
    def _key(u: int, v: int) -> tuple[int, int]:
        return (u, v) if u < v else (v, u)

    def add_link(self, u: int, v: int, distance_km: float,
                 pool_seconds: float = 30.0) -> Link:
        rate = secret_key_rate(distance_km)
        link = Link(u=u, v=v, distance_km=distance_km, rate_bps=rate,
                    capacity_bits=rate * pool_seconds,
                    stored_bits=rate * pool_seconds * 0.5)
        self.links[self._key(u, v)] = link
        self._path_cache.clear()
        return link

    def link(self, u: int, v: int) -> Link | None:
        return self.links.get(self._key(u, v))

    def neighbours(self, u: int) -> list[int]:
        return [b if a == u else a for (a, b) in self.links if u in (a, b)]

    def path(self, src: int, dst: int) -> list[int]:
        """Min-hop-cost relay path. Cost per hop is 1/rate: prefer fast links,
        and penalise hop count because every hop burns a full copy of the key."""
        if src == dst:
            return [src]
        ck = (src, dst)
        if ck in self._path_cache:
            return self._path_cache[ck]
        dist = {src: 0.0}
        prev: dict[int, int] = {}
        pq = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == dst:
                break
            if d > dist.get(u, float("inf")):
                continue
            for w in self.neighbours(u):
                lk = self.link(u, w)
                cost = d + 1.0 / max(lk.rate_bps, 1.0)
                if cost < dist.get(w, float("inf")):
                    dist[w] = cost
                    prev[w] = u
                    heapq.heappush(pq, (cost, w))
        if dst not in prev and dst != src:
            self._path_cache[ck] = []
            return []
        node, out = dst, [dst]
        while node != src:
            node = prev[node]
            out.append(node)
        out.reverse()
        self._path_cache[ck] = out
        return out

    def path_links(self, src: int, dst: int) -> list[Link]:
        p = self.path(src, dst)
        return [self.link(p[i], p[i + 1]) for i in range(len(p) - 1)]

    def hops(self, src: int, dst: int) -> int:
        return max(0, len(self.path(src, dst)) - 1)

    # ---- key accounting -------------------------------------------------

    def can_reserve(self, src: int, dst: int, bits: float) -> bool:
        lks = self.path_links(src, dst)
        return bool(lks) and all(lk.free_bits >= bits for lk in lks)

    def reserve(self, src: int, dst: int, bits: float) -> bool:
        """Hold `bits` on every hop of the path. Returns False if any hop is short."""
        if not self.can_reserve(src, dst, bits):
            return False
        for lk in self.path_links(src, dst):
            lk.reserved_bits += bits
        return True

    def release(self, src: int, dst: int, bits: float) -> None:
        """Give back an unconsumed reservation (TTL expiry / forecast revision)."""
        for lk in self.path_links(src, dst):
            lk.reserved_bits = max(0.0, lk.reserved_bits - bits)

    def consume(self, src: int, dst: int, bits: float, from_reservation: bool) -> bool:
        """Burn key on every hop. If from_reservation, the hold is converted."""
        lks = self.path_links(src, dst)
        if not lks:
            return False
        if from_reservation:
            for lk in lks:
                lk.reserved_bits = max(0.0, lk.reserved_bits - bits)
                lk.stored_bits = max(0.0, lk.stored_bits - bits)
            return True
        if not all(lk.free_bits >= bits for lk in lks):
            return False
        for lk in lks:
            lk.stored_bits -= bits
        return True

    def replenish(self, dt_s: float) -> None:
        for lk in self.links.values():
            lk.replenish(dt_s)

    def total_stored(self) -> float:
        return sum(lk.stored_bits for lk in self.links.values())

    def total_reserved(self) -> float:
        return sum(lk.reserved_bits for lk in self.links.values())


# ---- generators ---------------------------------------------------------

def ring_with_chords(n_validators: int, seed: int = 0, chord_prob: float = 0.25,
                     span_km: tuple[float, float] = (20.0, 60.0)) -> QKDNetwork:
    """Validators on a ring of trusted nodes plus a few chords. Realistic in that
    most validator pairs are NOT adjacent, so relaying dominates."""
    rng = np.random.default_rng(seed)
    net = QKDNetwork(n_nodes=n_validators)
    net.validators = list(range(n_validators))
    for i in range(n_validators):
        j = (i + 1) % n_validators
        net.add_link(i, j, float(rng.uniform(*span_km)))
    for i, j in itertools.combinations(range(n_validators), 2):
        if net.link(i, j) is None and rng.random() < chord_prob:
            net.add_link(i, j, float(rng.uniform(span_km[0], span_km[1] * 1.5)))
    return net


def metro_star(n_validators: int, seed: int = 0, n_hubs: int = 3,
               span_km: tuple[float, float] = (10.0, 40.0)) -> QKDNetwork:
    """Metro topology: validators hang off a small trusted-relay core. Every
    cross-hub pair is >=3 hops, which stresses relay key consumption."""
    rng = np.random.default_rng(seed)
    n_nodes = n_validators + n_hubs
    net = QKDNetwork(n_nodes=n_nodes)
    net.validators = list(range(n_validators))
    hubs = list(range(n_validators, n_nodes))
    for h1, h2 in itertools.combinations(hubs, 2):
        net.add_link(h1, h2, float(rng.uniform(30.0, 70.0)))
    for v in range(n_validators):
        net.add_link(v, hubs[v % n_hubs], float(rng.uniform(*span_km)))
    return net
