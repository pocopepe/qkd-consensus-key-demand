"""Experiment 3 -- what the kernel budgets actually do, and what they don't."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from qkdnet.allocate import (DensityGreedyPolicy, ExactDPPolicy,
                             HystereticSwapPolicy, QuorumCoveragePolicy,
                             UtilityModel, build_candidates)
from qkdnet.consensus import ConsensusConfig
from qkdnet.forecast import StructuralForecaster
from qkdnet.kernel import KernelBudget
from qkdnet.sim import LatencyModel, run
from qkdnet.topology import ring_with_chords


def objective(sel, cands):
    u = {c.pair: c.utility for c in cands}
    return sum(u.get(p, 0.0) for p in sel)


def part_a():
    """Greedy vs exact optimum on the per-round selection problem."""
    from qkdnet.consensus import BFTConsensus
    n = 16
    net = ring_with_chords(n, seed=3)
    ccfg = ConsensusConfig(n=n, seed=3, byzantine=(3, 11), timeout_prob=0.03)
    lat = LatencyModel()
    hs = [net.hops(a, b) for a in net.validators for b in net.validators if a < b]
    um = UtilityModel(lambda_bit=lat.calibrate_lambda(float(np.mean(hs)), 256.0))
    cons = BFTConsensus(ccfg)
    fc = StructuralForecaster(cons)

    print("=== (a) density-greedy vs exact optimum, per-round selection ===")
    print(f"{'M_max':>7}{'greedy/opt':>12}{'worst round':>13}{'#rounds tied':>14}")
    for M in (16, 32, 64, 128, 192, 256):
        budget = KernelBudget(max_entries=M, max_updates_per_round=10**6)
        ratios = []
        c2 = BFTConsensus(ccfg)
        f2 = StructuralForecaster(c2)
        for v in range(120):
            pred = f2.predict(v)
            cands = build_candidates(pred, net, um)
            if not cands:
                continue
            g = DensityGreedyPolicy().select(cands, budget, {}, net)
            o = ExactDPPolicy().select(cands, budget, {}, net)
            og = objective(g, cands)
            oo = objective(o, cands)
            if oo > 0:
                ratios.append(og / oo)
            out = c2.step()
            f2.observe(v, out.demand, {"leader": out.leader,
                                       "view_change": out.phase.value == "view_change"})
        r = np.array(ratios) if ratios else np.array([1.0])
        print(f"{M:>7}{r.mean():>12.5f}{r.min():>13.5f}"
              f"{int((r > 0.99999).sum()):>10}/{len(r):<4}")
    print("    The 1/2 worst-case bound for density-greedy is not approached in")
    print("    this regime: item weights (relay hop counts) are tiny next to the")
    print("    map, so the knapsack is effectively fractional and greedy is tight.")


def part_b():
    """Sweep the update budget -- the constraint the proposal does not have."""
    n = 16
    ccfg = ConsensusConfig(n=n, seed=3, byzantine=(3, 11), timeout_prob=0.03)
    pols = {"greedy": DensityGreedyPolicy(),
            "hysteretic": HystereticSwapPolicy(),
            "quorum": QuorumCoveragePolicy()}
    print("\n=== (b) per-round update budget U_max (M_max = 192) ===")
    print(f"{'U_max':>7}" + "".join(f"{p+' hit':>14}" for p in pols)
          + "".join(f"{p+' p50':>14}" for p in pols))
    for U in (8, 16, 24, 48, 96, 192):
        budget = KernelBudget(max_entries=192, max_updates_per_round=U)
        hits, lats = [], []
        for name, pol in pols.items():
            s = run(ring_with_chords(n, seed=3), ccfg,
                    lambda c: StructuralForecaster(c), pol, budget,
                    views=300).summary()
            hits.append(s["hit_rate"])
            lats.append(s["lat_p50_ms"])
        print(f"{U:>7}" + "".join(f"{h:>14.3f}" for h in hits)
              + "".join(f"{l:>14.3f}" for l in lats))


def part_c():
    """Sweep the hoarding penalty on reserved-but-unused key."""
    n = 16
    ccfg = ConsensusConfig(n=n, seed=3, byzantine=(3, 11), timeout_prob=0.03)
    budget = KernelBudget(max_entries=192, max_updates_per_round=48)
    lat = LatencyModel()
    net0 = ring_with_chords(n, seed=3)
    hs = [net0.hops(a, b) for a in net0.validators for b in net0.validators if a < b]
    lam = lat.calibrate_lambda(float(np.mean(hs)), 256.0)
    print("\n=== (c) hoarding penalty on reserved-but-unused key ===")
    print(f"    lambda_bit = {lam:.3e} s/bit (calibrated from the reactive baseline)")
    print(f"{'gamma/lambda':>14}{'hit':>8}{'p50 ms':>9}{'key waste':>11}{'entries':>9}")
    for ratio in (0.0, 0.1, 0.5, 1.0, 2.0, 5.0):
        um = UtilityModel(lambda_bit=lam, hoard_gamma=ratio * lam)
        s = run(ring_with_chords(n, seed=3), ccfg,
                lambda c: StructuralForecaster(c), DensityGreedyPolicy(),
                budget, um=um, lat=lat, views=300).summary()
        print(f"{ratio:>14.1f}{s['hit_rate']:>8.3f}{s['lat_p50_ms']:>9.3f}"
              f"{s['key_waste_frac']:>11.3f}{s['occupancy_mean']:>9.1f}")


if __name__ == "__main__":
    part_a()
    part_b()
    part_c()
