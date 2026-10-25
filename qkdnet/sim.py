"""Round-by-round simulation harness: consensus -> forecast -> pre-arm ->
serve."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .allocate import Candidate, Policy, UtilityModel, build_candidates
from .consensus import BFTConsensus, ConsensusConfig, Pair
from .forecast import Forecaster, forecast_error
from .kernel import KernelBudget, XDPMap


@dataclass
class LatencyModel:
    t_fast_s: float = 50e-6       # XDP map lookup + Wegman-Carter tag
    t_kme_s: float = 3.0e-3       # ETSI GS QKD 014 REST round trip to the KME
    t_hop_s: float = 1.5e-3       # per trusted-relay hop on the slow path
    t_starve_cap_s: float = 2.0

    def slow(self, hops: int) -> float:
        return self.t_kme_s + hops * self.t_hop_s

    def calibrate_lambda(self, hops_mean: float, bits_per_msg: float) -> float:
        """lambda_bit: seconds of latency avoided per bit served from the fast
        path. This is the calibration the proposal leaves unspecified."""
        return (self.slow(hops_mean) - self.t_fast_s) / max(bits_per_msg, 1.0)


@dataclass
class RunMetrics:
    views: int = 0
    hits: int = 0
    misses: int = 0
    starved: int = 0
    round_latency: list[float] = field(default_factory=list)
    deadline_misses: int = 0
    churn: list[int] = field(default_factory=list)
    truncated_commits: int = 0
    occupancy: list[int] = field(default_factory=list)
    bits_wasted: float = 0.0
    bits_demanded: float = 0.0
    bits_fast: float = 0.0
    fc_jaccard: list[float] = field(default_factory=list)
    fc_recall: list[float] = field(default_factory=list)
    fc_mae: list[float] = field(default_factory=list)
    fc_wasted_mass: list[float] = field(default_factory=list)
    prearm_sets: list[set] = field(default_factory=list)
    fast_pairs: list[set] = field(default_factory=list)
    leaders: list[int] = field(default_factory=list)
    next_leaders: list[int] = field(default_factory=list)
    leader_seq: list[int] = field(default_factory=list)
    view_ids: list[int] = field(default_factory=list)

    def summary(self) -> dict:
        rl = np.array(self.round_latency) if self.round_latency else np.array([0.0])
        tot = self.hits + self.misses
        return {
            "views": self.views,
            "hit_rate": self.hits / tot if tot else 0.0,
            "starve_rate": self.starved / tot if tot else 0.0,
            "lat_mean_ms": float(rl.mean() * 1e3),
            "lat_p50_ms": float(np.percentile(rl, 50) * 1e3),
            "lat_p99_ms": float(np.percentile(rl, 99) * 1e3),
            "deadline_miss_rate": self.deadline_misses / max(self.views, 1),
            "churn_mean": float(np.mean(self.churn)) if self.churn else 0.0,
            "truncated_commits": self.truncated_commits,
            "occupancy_mean": float(np.mean(self.occupancy)) if self.occupancy else 0.0,
            "key_waste_frac": self.bits_wasted / max(self.bits_demanded, 1.0),
            "fast_bits_frac": self.bits_fast / max(self.bits_demanded, 1.0),
            "fc_coverage": float(np.mean(self.fc_jaccard)) if self.fc_jaccard else 0.0,
            "fc_precision": float(np.mean(self.fc_recall)) if self.fc_recall else 0.0,
            "fc_mae": float(np.mean(self.fc_mae)) if self.fc_mae else 0.0,
            "fc_wasted_mass": float(np.mean(self.fc_wasted_mass)) if self.fc_wasted_mass else 0.0,
        }


def run(net, ccfg: ConsensusConfig, forecaster_factory, policy: Policy,
        budget: KernelBudget, um: UtilityModel | None = None,
        lat: LatencyModel | None = None, views: int = 400,
        ttl_views: int = 2, warmup: int = 20, seed: int = 0) -> RunMetrics:
    lat = lat or LatencyModel()
    cons = BFTConsensus(ccfg)
    fc: Forecaster = forecaster_factory(cons)
    kmap = XDPMap(budget, net=net)

    if um is None:
        hs = [net.hops(a, b) for a in net.validators for b in net.validators if a < b]
        um = UtilityModel(
            lambda_bit=lat.calibrate_lambda(float(np.mean(hs)), ccfg.tag_bits),
            hoard_gamma=0.0)

    m = RunMetrics()
    for v in range(views):
        net.replenish(ccfg.view_period_s)
        kmap.expire(v)

        pred = fc.predict(v)
        cands = build_candidates(pred, net, um)
        resident = {p: e.bits for p, e in kmap.entries.items()}
        pname = getattr(policy, "name", "")
        if any(t in pname for t in ("atomic", "quorum")):
            target = policy.select(cands, budget, resident, net,
                                   groups=fc.groups(v))
        else:
            target = policy.select(cands, budget, resident, net)

        # reserve key on every hop before installing; drop what cannot be backed
        installable = {}
        for p, bits in target.items():
            if p in resident and abs(resident[p] - bits) < 1e-9:
                installable[p] = bits
            elif net.reserve(p[0], p[1], bits):
                installable[p] = bits
        res = kmap.commit(installable, v, ttl_views)
        # Snapshot the installed set *before* serving. This is what an adversary
        # timing consensus responses during view v actually observes; reading it
        installed_snapshot = set(kmap.entries)

        out = cons.step()
        actual = out.demand

        # per-pair service, then per-block completion at the quorum order
        # statistic, then round latency as the max over blocks
        pair_lat: dict = {}
        fast_observed: set = set()
        for pair, bits in actual.items():
            hops = net.hops(pair[0], pair[1])
            m.bits_demanded += bits
            if kmap.lookup(pair, bits, v):
                net.consume(pair[0], pair[1], bits, from_reservation=True)
                m.hits += 1
                m.bits_fast += bits
                pair_lat[pair] = lat.t_fast_s
                fast_observed.add(pair)
            else:
                m.misses += 1
                if net.consume(pair[0], pair[1], bits, from_reservation=False):
                    pair_lat[pair] = lat.slow(hops)
                else:
                    m.starved += 1
                    lks = net.path_links(pair[0], pair[1])
                    if lks:
                        deficit = max(bits - min(lk.free_bits for lk in lks), 0.0)
                        rate = min(lk.rate_bps for lk in lks)
                        wait = min(deficit / max(rate, 1.0), lat.t_starve_cap_s)
                    else:
                        wait = lat.t_starve_cap_s
                    pair_lat[pair] = lat.slow(hops) + wait

        worst = 0.0
        for blk in out.blocks:
            ls = sorted(pair_lat.get(p, lat.slow(1)) for p in blk.pairs)
            if not ls:
                continue
            q = min(max(blk.quorum, 1), len(ls))
            worst = max(worst, ls[q - 1])

        if v >= warmup:
            m.views += 1
            m.round_latency.append(worst)
            if worst > out.deadline_s:
                m.deadline_misses += 1
            m.churn.append(res["spent"])
            m.truncated_commits += int(res["truncated"])
            m.occupancy.append(res["installed"])
            e = forecast_error(pred, actual, topk=budget.max_entries)
            m.fc_jaccard.append(e["coverage"])
            m.fc_recall.append(e["precision"])
            m.fc_mae.append(e["mae"])
            m.fc_wasted_mass.append(e["wasted_mass"])
            m.prearm_sets.append(installed_snapshot)
            m.fast_pairs.append(fast_observed)
            m.leaders.append(out.leader)
            m.next_leaders.append(out.next_leader)
            m.view_ids.append(v)
            m.leader_seq.append(cons.leader(v))

        fc.observe(v, actual, {"leader": out.leader,
                               "view_change": out.phase.value == "view_change"})

    m.bits_wasted = kmap.stats.bits_wasted
    return m


def fresh_net(builder, *args, **kwargs):
    return builder(*args, **kwargs)
