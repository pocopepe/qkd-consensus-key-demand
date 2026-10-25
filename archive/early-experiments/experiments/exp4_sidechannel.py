"""Experiment 4 -- the pre-arm set leaks the leader schedule."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from qkdnet.allocate import (DensityGreedyPolicy, HystereticSwapPolicy,
                             QuorumCoveragePolicy)
from qkdnet.consensus import ConsensusConfig
from qkdnet.forecast import EWMAPairForecaster, StructuralForecaster
from qkdnet.kernel import KernelBudget
from qkdnet.sidechannel import (DecoyPrearmPolicy, UniformStarPolicy,
                                amplification_gain, measure_advance_leak,
                                measure_leak)
from qkdnet.sim import run
from qkdnet.topology import ring_with_chords


def main():
    n = 16
    budget = KernelBudget(max_entries=192, max_updates_per_round=64)
    ccfg = ConsensusConfig(n=n, seed=5, schedule="vrf", lookahead=4,
                           byzantine=(), timeout_prob=0.02, tag_bits=256.0)

    print("=== (a) leader-schedule leakage from the observable pre-arm set ===")
    print("    schedule is VRF: the next leader is meant to be unknown to observers")
    print("    observable = which pairs were served fast during the view")
    print(f"{'forecaster/policy':<28}{'obs':>7}{'top-1':>8}{'top-2':>8}{'base':>8}"
          f"{'adv':>8}{'MI bits':>9}")
    combos = [
        ("ewma / greedy", lambda c: EWMAPairForecaster(0.3), DensityGreedyPolicy()),
        ("structural / greedy", lambda c: StructuralForecaster(c), DensityGreedyPolicy()),
        ("structural / hysteretic", lambda c: StructuralForecaster(c), HystereticSwapPolicy()),
        ("structural / quorum", lambda c: StructuralForecaster(c), QuorumCoveragePolicy()),
    ]
    for name, fc, pol in combos:
        m = run(ring_with_chords(n, seed=5), ccfg, fc, pol, budget, views=400)
        for obs_name, obs in (("map", m.prearm_sets), ("timing", m.fast_pairs)):
            lk = measure_leak(obs, m.next_leaders, n)
            print(f"{name:<28}{obs_name:>7}{lk.top1_accuracy:>8.3f}"
                  f"{lk.top2_accuracy:>8.3f}{lk.baseline:>8.3f}"
                  f"{lk.advantage:>8.3f}{lk.mutual_info_bits:>9.3f}")

    print("\n=== (b) what a correct guess buys the adversary ===")
    for nn in (7, 16, 31, 64, 100):
        g = amplification_gain(nn, 256.0, 256.0)
        print(f"    n={nn:>4}  view-change / happy-path key demand = {g:>6.1f}x")
    print("    Every silenced leader multiplies key demand by this factor against")
    print("    links whose secret-key rate is fixed by physics and cannot surge.")

    print("\n=== (c) decoy stars: the obvious defence, which does not work ===")
    print(f"{'decoys':>7}{'top-1':>8}{'adv':>8}{'hit':>8}{'p50 ms':>9}"
          f"{'entries':>9}{'key waste':>11}")
    for d in (0, 1, 2, 4, 8):
        pol = DecoyPrearmPolicy(QuorumCoveragePolicy(), n, decoys=d, seed=11)
        m = run(ring_with_chords(n, seed=5), ccfg,
                lambda c: StructuralForecaster(c), pol, budget, views=400)
        s = m.summary()
        lk = measure_leak(m.fast_pairs, m.next_leaders, n)
        print(f"{d:>7}{lk.top1_accuracy:>8.3f}{lk.advantage:>8.3f}"
              f"{s['hit_rate']:>8.3f}{s['lat_p50_ms']:>9.3f}"
              f"{s['occupancy_mean']:>9.1f}{s['key_waste_frac']:>11.3f}")




def part_d():
    """(d) uniform star coverage: the defence that does work, and its price."""
    n = 16
    budget = KernelBudget(max_entries=512, max_updates_per_round=256)
    ccfg = ConsensusConfig(n=n, seed=5, schedule="vrf", lookahead=4,
                           byzantine=(), timeout_prob=0.02, tag_bits=256.0)
    from qkdnet.consensus import BFTConsensus
    q = BFTConsensus(ccfg).quorum_pairs
    print("\n=== (d) uniform star coverage: privacy / overhead frontier ===")
    print(f"    n={n}, quorum pairs q={q}, map M_max={budget.max_entries}")
    print(f"{'stars covered':>14}{'bits/pair':>10}{'top-1':>8}{'top-2':>8}{'adv':>8}"
          f"{'hit':>8}{'p50 ms':>9}{'entries':>9}{'key waste':>11}")
    for frac, bits in [(0.125, 512.0), (0.25, 512.0), (0.5, 512.0),
                       (0.75, 512.0), (1.0, 256.0), (1.0, 512.0)]:
        pol = UniformStarPolicy(n, q, fraction=frac, bits=bits, seed=3)
        m = run(ring_with_chords(n, seed=5), ccfg,
                lambda c: StructuralForecaster(c), pol, budget, views=400)
        s = m.summary()
        lk = measure_leak(m.fast_pairs, m.next_leaders, n)
        print(f"{frac*n:>13.0f}{bits:>10.0f}{lk.top1_accuracy:>8.3f}"
              f"{lk.top2_accuracy:>8.3f}{lk.advantage:>8.3f}{s['hit_rate']:>8.3f}"
              f"{s['lat_p50_ms']:>9.3f}{s['occupancy_mean']:>9.1f}"
              f"{s['key_waste_frac']:>11.3f}")
    print(f"    baseline top-1 = {1/n:.3f}, top-2 = {2/n:.3f}")


def part_e():
    """(e) lead time is schedule secrecy, spent."""
    n = 16
    budget = KernelBudget(max_entries=384, max_updates_per_round=96)
    ccfg = ConsensusConfig(n=n, seed=5, schedule="vrf", lookahead=8,
                           byzantine=(), timeout_prob=0.02, tag_bits=256.0)
    from qkdnet.consensus import BFTConsensus
    print("\n=== (e) forecast horizon: lead time bought, secrecy sold ===")
    print(f"    n={n}, VRF schedule committed 8 views ahead, baseline accuracy {1/n:.3f}")
    print(f"{'horizon H':>10}{'hit':>8}{'p50 ms':>9}{'p99 ms':>9}{'entries':>9}"
          f"{'waste':>8}{'leak@1':>9}{'leak@2':>9}{'leak@3':>9}{'leak@4':>9}")
    for H in (1, 2, 3, 4, 6):
        pol = QuorumCoveragePolicy()
        m = run(ring_with_chords(n, seed=5), ccfg,
                lambda c, H=H: StructuralForecaster(c, horizon=H),
                pol, budget, views=400)
        s_ = m.summary()
        cons = BFTConsensus(ccfg)
        leaks = [measure_advance_leak(m.prearm_sets, m.view_ids, cons, n, k).top1_accuracy
                 for k in (1, 2, 3, 4)]
        print(f"{H:>10}{s_['hit_rate']:>8.3f}{s_['lat_p50_ms']:>9.3f}"
              f"{s_['lat_p99_ms']:>9.2f}{s_['occupancy_mean']:>9.1f}"
              f"{s_['key_waste_frac']:>8.3f}" + "".join(f"{x:>9.3f}" for x in leaks))


if __name__ == "__main__":
    main()
    part_d()
    part_e()
