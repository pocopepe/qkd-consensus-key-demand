#!/usr/bin/env python3
"""Where does density-greedy actually lose, and does the hybrid recover it?

Every policy is evaluated on the same footing: its plan is truncated to U_max
changes exactly as the kernel would truncate it mid-commit, then scored on the
quorum-block objective (a block pays out only if 2f+1 of its pairs are covered).

The reference is a valid upper bound, not a claimed optimum. For a chosen set of
blocks B, every pair belongs to at most two blocks (star(a) and star(b)), so
covering B needs at least ceil(sum_g need_g / 2) distinct pairs. Maximising
sum_g prob_g over block sets whose lower-bound cost fits the budget is therefore
an admissible bound on any policy's achievable value.
"""
import sys, os, itertools, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from qkdnet.allocate import (DensityGreedyPolicy, QuorumCoveragePolicy,
                             UtilityModel, build_candidates)
from qkdnet.consensus import BFTConsensus, ConsensusConfig
from qkdnet.forecast import StructuralForecaster
from qkdnet.kernel import KernelBudget
from qkdnet.topology import ring_with_chords
from simulator.hybrid import HybridSwapOptimizer


def truncate(plan, resident, budget, by_pair):
    """Apply the kernel's commit truncation: at most U_max changed entries."""
    changed = [p for p in plan if p not in resident]
    keep = [p for p in plan if p in resident]
    changed.sort(key=lambda p: -by_pair[p].utility / max(by_pair[p].weight, 1))
    allowed = changed[:budget.max_updates_per_round]
    sel, ent = [], 0
    for p in keep + allowed:
        if ent + by_pair[p].weight <= budget.max_entries:
            sel.append(p); ent += by_pair[p].weight
    return set(sel)


def group_value(sel, groups):
    return sum(g.prob for g in groups
               if sum(1 for p in g.pairs if p in sel) >= g.need())


def upper_bound(groups, budget, min_weight=1):
    blocks = sorted(groups, key=lambda g: -g.prob)[:14]
    best = 0.0
    for r in range(len(blocks) + 1):
        for combo in itertools.combinations(blocks, r):
            need = sum(g.need() for g in combo)
            pairs_lb = math.ceil(need / 2) if need else 0
            if pairs_lb <= budget.max_updates_per_round and \
               pairs_lb * min_weight <= budget.max_entries:
                best = max(best, sum(g.prob for g in combo))
    return best


def main():
    n = 16
    net = ring_with_chords(n, seed=3)
    ccfg = ConsensusConfig(n=n, seed=3, byzantine=(3, 11), timeout_prob=0.03)
    um = UtilityModel(lambda_bit=2.5e-5)
    views = int(os.environ.get("VIEWS", 80))

    print("Quorum-block value achieved, all plans truncated to U_max as the kernel would")
    print(f"{'M_max':>6}{'U_max':>7}{'greedy':>9}{'quorum':>9}{'hybrid':>9}"
          f"{'bound':>9}{'greedy/b':>10}{'quorum/b':>10}{'hybrid/b':>10}")
    rows = []
    for M, U in [(192, 64), (192, 24), (96, 16), (48, 12), (32, 10), (24, 8)]:
        budget = KernelBudget(max_entries=M, max_updates_per_round=U)
        cons = BFTConsensus(ccfg)
        fc = StructuralForecaster(cons)
        hyb = HybridSwapOptimizer(iters=2000, time_budget_s=0.03, seed=1)
        acc = {"greedy": [], "quorum": [], "hybrid": [], "ub": []}
        res_g = res_q = res_h = {}
        for v in range(views):
            groups = fc.groups(v)
            cands = build_candidates(fc.predict(v), net, um)
            by_pair = {c.pair: c for c in cands}
            if cands:
                g = truncate(DensityGreedyPolicy().select(cands, budget, res_g, net),
                             res_g, budget, by_pair)
                q = truncate(QuorumCoveragePolicy().select(cands, budget, res_q, net,
                                                           groups=groups),
                             res_q, budget, by_pair)
                h = truncate(hyb.select(cands, budget, res_h, net, groups=groups),
                             res_h, budget, by_pair)
                acc["greedy"].append(group_value(g, groups))
                acc["quorum"].append(group_value(q, groups))
                acc["hybrid"].append(group_value(h, groups))
                acc["ub"].append(upper_bound(groups, budget))
                res_g = {p: by_pair[p].bits for p in g}
                res_q = {p: by_pair[p].bits for p in q}
                res_h = {p: by_pair[p].bits for p in h}
            out = cons.step()
            fc.observe(v, out.demand, {"leader": out.leader,
                                       "view_change": out.phase.value == "view_change"})
        G, Q, H, B = (float(np.mean(acc[k])) for k in ("greedy", "quorum", "hybrid", "ub"))
        B = max(B, 1e-9)
        rows.append((M, U, G, Q, H, B))
        print(f"{M:>6}{U:>7}{G:>9.4f}{Q:>9.4f}{H:>9.4f}{B:>9.4f}"
              f"{G/B:>10.4f}{Q/B:>10.4f}{H/B:>10.4f}")

    print("\nWhere the gap lives:")
    for M, U, G, Q, H, B in rows:
        if H > G + 1e-9:
            print(f"  M={M:<4} U={U:<3}  hybrid beats greedy by "
                  f"{100*(H-G)/max(G,1e-9):6.1f}%   ({G:.3f} -> {H:.3f})")
    worst = min(rows, key=lambda r: r[2] / max(r[5], 1e-9))
    print(f"\n  greedy is furthest from the bound at M={worst[0]}, U={worst[1]}: "
          f"{worst[2]/max(worst[5],1e-9):.3f} of bound")


if __name__ == "__main__":
    main()
