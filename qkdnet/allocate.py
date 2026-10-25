"""Pre-arm selection policies."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .consensus import Pair
from .forecast import Forecast


@dataclass
class UtilityModel:
    """Expected benefit of pre-arming one pair, in units of avoided latency
    (s)."""
    lambda_bit: float = 4.0e-7
    hoard_gamma: float = 0.0
    max_bits_per_entry: float = 1.0e6

    def utility(self, pair: Pair, bits: float, conf: float, hops: int) -> float:
        gain = conf * bits * self.lambda_bit
        waste = (1.0 - conf) * bits * hops * self.hoard_gamma
        return gain - waste


@dataclass
class Candidate:
    pair: Pair
    bits: float
    conf: float
    hops: int
    utility: float

    @property
    def weight(self) -> int:
        """Map entries consumed: one forwarding entry per relay hop."""
        return max(1, self.hops)

    @property
    def density(self) -> float:
        return self.utility / self.weight


def build_candidates(forecast: Forecast, net, um: UtilityModel) -> list[Candidate]:
    out = []
    for pair, (bits, conf) in forecast.items():
        bits = min(bits, um.max_bits_per_entry)
        if bits <= 0:
            continue
        h = net.hops(pair[0], pair[1])
        if h == 0:
            continue
        u = um.utility(pair, bits, conf, h)
        if u <= 0:
            continue
        out.append(Candidate(pair, bits, conf, h, u))
    return out


class Policy:
    name = "base"

    def select(self, cands: list[Candidate], budget, resident: dict[Pair, float],
               net) -> dict[Pair, float]:
        raise NotImplementedError


class ReactivePolicy(Policy):
    """Pre-arm nothing. Every request takes the userspace slow path."""
    name = "reactive"

    def select(self, cands, budget, resident, net):
        return {}


class DensityGreedyPolicy(Policy):
    """The proposal's rule: order by u/(c+m), admit until a budget is
    exhausted."""
    name = "greedy"

    def select(self, cands, budget, resident, net):
        chosen: dict[Pair, float] = {}
        used = 0
        for c in sorted(cands, key=lambda c: -c.density):
            if used + c.weight > budget.max_entries:
                continue
            if not net.can_reserve(c.pair[0], c.pair[1], c.bits):
                continue
            chosen[c.pair] = c.bits
            used += c.weight
        return chosen


class ExactDPPolicy(Policy):
    """Exact per-round optimum by dynamic programming over map entries."""
    name = "exact_dp"

    def select(self, cands, budget, resident, net):
        cands = [c for c in cands if net.can_reserve(c.pair[0], c.pair[1], c.bits)]
        C = int(budget.max_entries)
        if not cands or C <= 0:
            return {}
        n = len(cands)
        dp = np.zeros((n + 1, C + 1))
        for i, c in enumerate(cands, start=1):
            w, u = c.weight, c.utility
            dp[i, :w] = dp[i - 1, :w]
            dp[i, w:] = np.maximum(dp[i - 1, w:], dp[i - 1, :C + 1 - w] + u)
        chosen: dict[Pair, float] = {}
        cap = C
        for i in range(n, 0, -1):
            if dp[i, cap] > dp[i - 1, cap] + 1e-15:
                c = cands[i - 1]
                chosen[c.pair] = c.bits
                cap -= c.weight
        return chosen


class HystereticSwapPolicy(Policy):
    """Switching-cost-aware online selection under a per-round update budget."""
    name = "hysteretic"

    def __init__(self, mu: float = 0.0, mu_auto: float = 0.35):
        self.mu = mu
        self.mu_auto = mu_auto

    def select(self, cands, budget, resident, net):
        feasible = [c for c in cands if net.can_reserve(c.pair[0], c.pair[1], c.bits)]
        by_pair = {c.pair: c for c in feasible}
        # switching cost, in objective units: a fraction of the median utility,
        # so hysteresis scales with the workload instead of needing hand-tuning
        mu = self.mu
        if mu <= 0.0 and feasible:
            mu = self.mu_auto * float(np.median([c.utility for c in feasible]))

        # start from the incumbent set, keeping only entries still forecast useful
        keep: dict[Pair, float] = {}
        used = 0
        incumbents = []
        for p, bits in resident.items():
            c = by_pair.get(p)
            if c is None:
                continue           # no longer forecast: candidate for eviction
            if used + c.weight <= budget.max_entries:
                keep[p] = c.bits
                used += c.weight
                incumbents.append(c)

        challengers = sorted((c for c in feasible if c.pair not in keep),
                             key=lambda c: -c.density)
        incumbents.sort(key=lambda c: c.density)

        swaps = 0
        limit = budget.max_updates_per_round
        ci = 0
        # phase 1: free admissions into spare capacity
        while ci < len(challengers) and swaps < limit:
            c = challengers[ci]
            if used + c.weight <= budget.max_entries:
                keep[c.pair] = c.bits
                used += c.weight
                swaps += 1
                ci += 1
            else:
                break
        # phase 2: paid exchanges, best-gain-first, only when they clear 2*mu
        ii = 0
        while ci < len(challengers) and swaps + 1 < limit and ii < len(incumbents):
            c = challengers[ci]
            inc = incumbents[ii]
            if inc.pair not in keep:
                ii += 1
                continue
            gain = c.utility - inc.utility - 2.0 * mu
            if gain <= 0:
                break                      # densities are sorted: no later swap wins
            del keep[inc.pair]
            used -= inc.weight
            if used + c.weight <= budget.max_entries:
                keep[c.pair] = c.bits
                used += c.weight
                swaps += 2
                ci += 1
            ii += 1
        return keep


class LagrangianLinkPolicy(Policy):
    """Density-greedy with dual prices on contended link key pools."""
    name = "lagrangian"

    def __init__(self, iterations: int = 12, step: float = 0.5):
        self.iterations = iterations
        self.step = step

    def select(self, cands, budget, resident, net):
        feasible = [c for c in cands if net.hops(*c.pair) > 0]
        if not feasible:
            return {}
        paths = {c.pair: net.path_links(c.pair[0], c.pair[1]) for c in feasible}
        prices: dict[tuple[int, int], float] = {}

        def lkey(lk):
            return (lk.u, lk.v) if lk.u < lk.v else (lk.v, lk.u)

        chosen: dict[Pair, float] = {}
        for _ in range(self.iterations):
            scored = []
            for c in feasible:
                pen = sum(prices.get(lkey(lk), 0.0) for lk in paths[c.pair])
                adj = c.utility - pen * c.bits
                if adj > 0:
                    scored.append((adj / c.weight, adj, c))
            scored.sort(key=lambda t: -t[0])
            chosen, used = {}, 0
            load: dict[tuple[int, int], float] = {}
            for _, _, c in scored:
                if used + c.weight > budget.max_entries:
                    continue
                chosen[c.pair] = c.bits
                used += c.weight
                for lk in paths[c.pair]:
                    load[lkey(lk)] = load.get(lkey(lk), 0.0) + c.bits
            # subgradient step: price up the links whose pools are oversubscribed
            viol = 0.0
            for k, dem in load.items():
                lk = net.links[k]
                excess = dem - lk.free_bits
                if excess > 0:
                    prices[k] = prices.get(k, 0.0) + self.step * excess / max(lk.free_bits, 1.0)
                    viol += excess
                else:
                    prices[k] = max(0.0, prices.get(k, 0.0) - self.step * 0.1)
            if viol <= 0:
                break
        return {p: b for p, b in chosen.items() if net.can_reserve(p[0], p[1], b)}


# --------------------------------------------------------------------------
# Contribution: atomic group coverage under a deadline
# --------------------------------------------------------------------------

class AtomicCoveragePolicy(Policy):
    """Pre-arm whole demand groups or not at all."""
    name = "atomic"

    def __init__(self, slow_s: float = 4.5e-3, fast_s: float = 50e-6,
                 min_prob: float = 0.05):
        self.slow_s = slow_s
        self.fast_s = fast_s
        self.min_prob = min_prob

    def select(self, cands, budget, resident, net, groups=None):
        if not groups:
            return DensityGreedyPolicy().select(cands, budget, resident, net)
        chosen: dict[Pair, float] = {}
        used = 0
        updates = 0
        remaining = [g for g in groups if g.prob >= self.min_prob]

        def marginal(g):
            """Marginal cost of finishing group g, given what is already
            chosen."""
            need_entries, need_updates, bits = 0, 0, {}
            for p, b in g.pairs.items():
                h = net.hops(p[0], p[1])
                if h == 0:
                    continue
                total = chosen.get(p, 0.0) + b
                bits[p] = total
                already = chosen.get(p) is not None
                if already:
                    need_updates += 1          # rewrite with the larger reservation
                elif not (p in resident and abs(resident[p] - total) < 1e-9):
                    need_updates += 1
                    need_entries += max(1, h)
            return need_entries, need_updates, bits

        while remaining:
            best, best_score, best_plan = None, 0.0, None
            for g in remaining:
                ne, nu, bits = marginal(g)
                if not bits:
                    continue
                if used + ne > budget.max_entries:
                    continue
                if updates + nu > budget.max_updates_per_round:
                    continue
                if not all(net.can_reserve(p[0], p[1], b) or p in resident
                           for p, b in bits.items()):
                    continue
                # value paid out only if the whole group lands
                value = g.prob * (self.slow_s - self.fast_s)
                score = value / max(ne + nu, 1)
                if score > best_score:
                    best, best_score, best_plan = g, score, (ne, nu, bits)
            if best is None:
                break
            ne, nu, bits = best_plan
            chosen.update(bits)
            used += ne
            updates += nu
            remaining.remove(best)
        return chosen


class QuorumCoveragePolicy(Policy):
    """Cover the cheapest quorum of each demand group, not the whole group."""
    name = "quorum"

    def __init__(self, slack: int = 2, min_prob: float = 0.05,
                 slow_s: float = 4.5e-3, fast_s: float = 50e-6):
        self.slack = slack
        self.min_prob = min_prob
        self.slow_s = slow_s
        self.fast_s = fast_s

    def select(self, cands, budget, resident, net, groups=None):
        if not groups:
            return DensityGreedyPolicy().select(cands, budget, resident, net)
        chosen: dict[Pair, float] = {}
        used = 0
        updates = 0

        def plan(g):
            """Cheapest live quorum for g: sort its pairs by relay cost, take
            q + slack, and charge only the entries not already resident."""
            ranked = sorted(
                ((net.hops(p[0], p[1]), p, b) for p, b in g.pairs.items()),
                key=lambda t: (t[0], t[1]))
            ranked = [t for t in ranked if t[0] > 0]
            need = min(g.need() + self.slack, len(ranked))
            ne, nu, bits = 0, 0, {}
            for h, p, b in ranked[:need]:
                total = chosen.get(p, 0.0) + b
                bits[p] = total
                if p in chosen:
                    nu += 1
                elif not (p in resident and abs(resident[p] - total) < 1e-9):
                    nu += 1
                    ne += max(1, h)
            return ne, nu, bits

        remaining = [g for g in groups if g.prob >= self.min_prob]
        while remaining:
            best, best_score, best_plan = None, 0.0, None
            for g in remaining:
                ne, nu, bits = plan(g)
                if not bits:
                    continue
                if used + ne > budget.max_entries:
                    continue
                if updates + nu > budget.max_updates_per_round:
                    continue
                if not all(net.can_reserve(p[0], p[1], b) or p in resident
                           for p, b in bits.items()):
                    continue
                value = g.prob * (self.slow_s - self.fast_s)
                score = value / max(ne + nu, 1)
                if score > best_score:
                    best, best_score, best_plan = g, score, (ne, nu, bits)
            if best is None:
                break
            ne, nu, bits = best_plan
            chosen.update(bits)
            used += ne
            updates += nu
            remaining.remove(best)
        return chosen
