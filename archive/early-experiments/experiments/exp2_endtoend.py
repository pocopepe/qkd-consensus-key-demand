"""Experiment 2 -- end-to-end: does better forecasting survive the kernel
budget?"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qkdnet.allocate import (AtomicCoveragePolicy, DensityGreedyPolicy, ExactDPPolicy,
                             HystereticSwapPolicy, LagrangianLinkPolicy,
                             QuorumCoveragePolicy, ReactivePolicy, UtilityModel)
from qkdnet.consensus import ConsensusConfig
from qkdnet.forecast import EWMAPairForecaster, HoltForecaster, StructuralForecaster
from qkdnet.kernel import KernelBudget
from qkdnet.sim import LatencyModel, run
from qkdnet.topology import metro_star, ring_with_chords

FCS = {
    "ewma":       lambda c: EWMAPairForecaster(alpha=0.3),
    "holt":       lambda c: HoltForecaster(),
    "structural": lambda c: StructuralForecaster(c),
}
POLS = {
    "reactive":   ReactivePolicy(),
    "greedy":     DensityGreedyPolicy(),
    "exact_dp":   ExactDPPolicy(),
    "hysteretic": HystereticSwapPolicy(),
    "lagrangian": LagrangianLinkPolicy(),
    "atomic":     AtomicCoveragePolicy(),
    "quorum":     QuorumCoveragePolicy(),
}

HDR = (f"{'forecaster':<12}{'policy':<12}{'hit':>7}{'starve':>8}{'p50 ms':>9}"
       f"{'p99 ms':>9}{'miss dl':>9}{'waste':>8}{'churn':>7}{'trunc':>7}")


def line(fname, pname, s):
    return (f"{fname:<12}{pname:<12}{s['hit_rate']:>7.3f}{s['starve_rate']:>8.3f}"
            f"{s['lat_p50_ms']:>9.3f}{s['lat_p99_ms']:>9.2f}"
            f"{s['deadline_miss_rate']:>9.3f}{s['key_waste_frac']:>8.3f}"
            f"{s['churn_mean']:>7.1f}{s['truncated_commits']:>7d}")


def scenario(title, builder, n, budget, ccfg_kw, views=400, seed=3):
    print(f"\n=== {title} ===")
    print(f"    M_max={budget.max_entries} entries "
          f"({budget.memory_bytes()/1024:.0f} KiB), U_max={budget.max_updates_per_round} updates/view")
    print(HDR)
    net0 = builder(n, seed=seed)
    lat = LatencyModel()
    ccfg = ConsensusConfig(n=n, seed=seed, **ccfg_kw)
    s = run(builder(n, seed=seed), ccfg, FCS["ewma"], POLS["reactive"],
            budget, lat=lat, views=views)
    base = s.summary()
    print(line("--", "reactive", base))
    for fname, fc in FCS.items():
        for pname, pol in POLS.items():
            if pname == "reactive":
                continue
            if pname in ("exact_dp", "lagrangian") and fname != "structural":
                continue
            st = run(builder(n, seed=seed), ccfg, fc, pol, budget,
                     lat=lat, views=views).summary()
            print(line(fname, pname, st))
    return base


def main():
    n = 16
    ccfg_kw = dict(schedule="round_robin", byzantine=(3, 11), timeout_prob=0.03,
                   view_period_s=0.25, deadline_s=0.25, tag_bits=256.0)

    # generous kernel: 64 KiB map, plenty of syscall headroom
    scenario("ring+chords, generous kernel budget", ring_with_chords, n,
             KernelBudget(max_entries=192, max_updates_per_round=192), ccfg_kw)

    # constrained kernel: this is where switching cost bites
    scenario("ring+chords, constrained update budget", ring_with_chords, n,
             KernelBudget(max_entries=192, max_updates_per_round=24), ccfg_kw)

    # metro star: every cross-hub pair is >=3 hops, so relay cost dominates
    scenario("metro star, constrained update budget", metro_star, n,
             KernelBudget(max_entries=192, max_updates_per_round=24), ccfg_kw)


if __name__ == "__main__":
    main()
