"""Experiment 1 -- support versus magnitude in consensus key-demand
forecasting."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from qkdnet.consensus import BFTConsensus, ConsensusConfig
from qkdnet.forecast import (EWMAPairForecaster, HoltForecaster,
                             StructuralForecaster, forecast_error)


def sweep_alpha(ccfg, views=600, alphas=(0.1, 0.2, 0.3, 0.5, 0.7, 0.9)):
    """Best case for the baseline: tune alpha over a grid, report the winner."""
    best = None
    for a in alphas:
        cons = BFTConsensus(ccfg)
        f = EWMAPairForecaster(alpha=a)
        js = []
        for v in range(views):
            pred = f.predict(v)
            out = cons.step()
            if v >= 20:
                js.append(forecast_error(pred, out.demand, topk=48)["coverage"])
            f.observe(v, out.demand, {"leader": out.leader,
                                      "view_change": out.phase.value == "view_change"})
        score = float(np.mean(js))
        if best is None or score > best[1]:
            best = (a, score)
    return best


def evaluate(ccfg, make_fc, views=600, warmup=20, topk=48):
    cons = BFTConsensus(ccfg)
    f = make_fc(cons)
    acc = {"coverage": [], "precision": [], "mae": [], "wasted_mass": []}
    for v in range(views):
        pred = f.predict(v)
        out = cons.step()
        if v >= warmup:
            e = forecast_error(pred, out.demand, topk=topk)
            for k in acc:
                acc[k].append(e[k])
        f.observe(v, out.demand, {"leader": out.leader,
                                  "view_change": out.phase.value == "view_change"})
    return {k: float(np.mean(vs)) for k, vs in acc.items()}


def main():
    scenarios = [
        ("round_robin, no faults", dict(schedule="round_robin", byzantine=(), timeout_prob=0.02)),
        ("round_robin, 2 byzantine", dict(schedule="round_robin", byzantine=(3, 11), timeout_prob=0.02)),
        ("vrf, lookahead=4", dict(schedule="vrf", lookahead=4, byzantine=(), timeout_prob=0.02)),
        ("vrf, lookahead=0 (blind)", dict(schedule="vrf", lookahead=0, byzantine=(), timeout_prob=0.02)),
    ]
    for title, kw in scenarios:
        ccfg = ConsensusConfig(n=16, seed=7, **kw)
        a_best, _ = sweep_alpha(ccfg)
        rows = [
            (f"ewma (alpha*={a_best})", lambda c, a=a_best: EWMAPairForecaster(alpha=a)),
            ("holt", lambda c: HoltForecaster()),
            ("structural", lambda c: StructuralForecaster(c)),
            ("structural -hazard", lambda c: StructuralForecaster(c, use_hazard=False)),
            ("structural -schedule", lambda c: StructuralForecaster(c, use_schedule=False)),
        ]
        print(f"\n=== {title}  (n=16) ===")
        print(f"{'forecaster':<24}{'cover@48':>10}{'prec@48':>9}{'wasted':>9}{'MAE(bits)':>12}")
        for name, mk in rows:
            r = evaluate(ccfg, mk)
            print(f"{name:<24}{r['coverage']:>10.3f}{r['precision']:>9.3f}"
                  f"{r['wasted_mass']:>9.3f}{r['mae']:>12.1f}")


if __name__ == "__main__":
    main()
