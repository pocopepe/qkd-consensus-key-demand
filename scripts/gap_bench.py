#!/usr/bin/env python3
"""Where does density-greedy actually lose, and does the hybrid recover it?

Every policy is truncated to U_max before scoring, because that is what the
kernel does at commit time: a plan larger than the update budget is applied
until the budget runs out and the rest is dropped. Scoring an untruncated plan
credits a policy for work the data plane never performs.

The reference is a valid upper bound, not a claimed optimum. Each pair belongs
to at most two quorum blocks (star(a) and star(b)), so covering a set B of
blocks needs at least ceil(sum_g need_g / 2) distinct pairs; a block subset
whose lower bound exceeds the budget cannot be covered, and the best subset that
survives bounds the attainable value from above.
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from qkdnet.allocate import (DensityGreedyPolicy, LagrangianLinkPolicy,
                             QuorumCoveragePolicy, UtilityModel, build_candidates)
from qkdnet.consensus import BFTConsensus, ConsensusConfig
from qkdnet.forecast import StructuralForecaster
from qkdnet.kernel import KernelBudget
from qkdnet.topology import ring_with_chords
from simulator.hybrid import HybridSwapOptimizer


def truncate(plan, by_pair, budget):
    """Apply the plan the way the kernel would: densest first until budgets run out."""
    out, ent, upd = {}, 0, 0
    for p in sorted(plan, key=lambda p: -by_pair[p].utility / max(by_pair[p].weight, 1)):
        c = by_pair[p]
        if ent + c.weight > budget.max_entries:
            continue
        if upd + 1 > budget.max_updates_per_round:
            break
        out[p] = plan[p]
        ent += c.weight
        upd += 1
    return out


ENTRY_COST = 0.004


def group_value(sel, groups, by_pair=None):
    """Scenario-correlated value, minus the cost of holding entries.

    Blocks in one scenario happen together or not at all, so a scenario pays out
    only when every block in it is covered -- partial coverage of the sixteen
    view-change fan-ins is worth nothing. And every entry held is key withheld
    from the pairs that need it now, which sweep B showed converts into
    starvation, so holding is charged rather than free."""
    scen = {}
    for g in groups:
        covered = sum(1 for p in g.pairs if p in sel) >= g.need()
        st = scen.setdefault(g.scenario, [True, g.prob])
        st[0] = st[0] and covered
        st[1] = max(st[1], g.prob)
    v = sum(prob for ok, prob in scen.values() if ok)
    if by_pair:
        v -= ENTRY_COST * sum(by_pair[p].weight for p in sel if p in by_pair)
    return v


def upper_bound(groups, budget):
    """Best attainable scenario value, bounded from above.

    A scenario pays only when all its blocks are covered, so the unit of choice
    is the scenario, not the block. Covering a scenario needs at least
    ceil(sum_g need_g / 2) distinct pairs, since a pair lies in at most two
    stars. That lower bound turns the problem into a knapsack over scenarios,
    solved exactly by DP. The entry-hold cost is omitted, which only makes the
    bound looser and therefore still admissible."""
    cap = 2 * min(budget.max_updates_per_round, budget.max_entries)
    if cap <= 0 or not groups:
        return 0.0
    scen = {}
    for g in groups:
        st = scen.setdefault(g.scenario, [0, 0.0])
        st[0] += int(g.need())
        st[1] = max(st[1], g.prob)
    dp = np.zeros(cap + 1)
    for need, prob in scen.values():
        w = max(1, -(-need // 2))
        if w > cap:
            continue
        dp[w:] = np.maximum(dp[w:], dp[:cap + 1 - w] + prob)
    return float(dp[cap])


def main():
    n = 16
    net = ring_with_chords(n, seed=3)
    ccfg = ConsensusConfig(n=n, seed=3, byzantine=(3, 11), timeout_prob=0.03)
    um = UtilityModel(lambda_bit=2.5e-5)
    views = 80

    pols = {
        "greedy": lambda: DensityGreedyPolicy(),
        "lagrangian": lambda: LagrangianLinkPolicy(),
        "quorum": lambda: QuorumCoveragePolicy(),
        "hybrid": lambda: HybridSwapOptimizer(iters=1500, time_budget_s=0.03),
    }

    print("Attained quorum-block value, all plans truncated to U_max as the kernel would")
    print(f"{'M_max':>6}{'U_max':>7}" + "".join(f"{k:>12}" for k in pols) + f"{'bound':>10}")
    rows = []
    for M, U in [(192, 96), (192, 48), (192, 24), (96, 16), (48, 12), (32, 10)]:
        budget = KernelBudget(max_entries=M, max_updates_per_round=U)
        acc = {k: [] for k in pols}
        ubs = []
        insts = {k: v() for k, v in pols.items()}
        cons = BFTConsensus(ccfg)
        fc = StructuralForecaster(cons)
        for v in range(views):
            groups = fc.groups(v)
            cands = build_candidates(fc.predict(v), net, um)
            by_pair = {c.pair: c for c in cands}
            if cands:
                ubs.append(upper_bound(groups, budget))
                for k, pol in insts.items():
                    try:
                        plan = pol.select(cands, budget, {}, net, groups=groups)
                    except TypeError:
                        plan = pol.select(cands, budget, {}, net)
                    acc[k].append(group_value(truncate(plan, by_pair, budget), groups, by_pair))
            out = cons.step()
            fc.observe(v, out.demand, {"leader": out.leader,
                                       "view_change": out.phase.value == "view_change"})
        ub = float(np.mean(ubs)) if ubs else 1.0
        line = f"{M:>6}{U:>7}" + "".join(f"{np.mean(acc[k]):>12.4f}" for k in pols) \
               + f"{ub:>10.4f}"
        print(line)
        rows.append((M, U, {k: float(np.mean(acc[k])) for k in pols}, ub))

    print(f"\n{'M_max':>6}{'U_max':>7}" + "".join(f"{k+'/bound':>14}" for k in pols))
    for M, U, vals, ub in rows:
        print(f"{M:>6}{U:>7}" + "".join(f"{vals[k]/max(ub,1e-9):>14.4f}" for k in pols))

    print("\nGap closed by the hybrid over density-greedy:")
    for M, U, vals, ub in rows:
        g, h = vals["greedy"], vals["hybrid"]
        if ub > 1e-9:
            closed = (h - g) / max(ub - g, 1e-9) if ub > g else 0.0
            print(f"  M={M:>4} U={U:>3}   greedy {g/ub:.3f} -> hybrid {h/ub:.3f} of bound"
                  f"   ({100*closed:5.1f}% of the residual gap closed)")


if __name__ == "__main__":
    main()
