#!/usr/bin/env python3
"""E1 aggregation: tables, figures, statistics across all collected traces."""
from __future__ import annotations

import glob
import json
import math
import os
import statistics
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.e1_analyze import D_ALL, D_CORE, analyze
from scripts.plot_svg import Series, line_chart, write

E1 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "research", "results", "e1")
RAW, PROC = os.path.join(E1, "raw"), os.path.join(E1, "processed")
FIG, TAB = os.path.join(E1, "figures"), os.path.join(E1, "tables")


def ci95(xs):
    if len(xs) < 2:
        return 0.0
    return 1.96 * statistics.stdev(xs) / math.sqrt(len(xs))


def classify(fn):
    b = os.path.basename(fn)
    if b.startswith("hotstuff_stable"):
        return "libhotstuff", "stable-leader", None
    if b.startswith("hotstuff_induced"):
        return "libhotstuff", "induced-rotation", None
    if b.startswith("hotstuff_trace"):
        return "libhotstuff", "stable-leader", None
    if b.startswith("comet_n"):
        n = int(b.split("_")[1][1:])
        return "CometBFT", "steady", n
    if b.startswith("comet_trace"):
        return "CometBFT", "steady", 4
    return None, None, None


def main():
    for d in (PROC, FIG, TAB):
        os.makedirs(d, exist_ok=True)
    files = sorted(glob.glob(os.path.join(RAW, "*.json")))
    rows = []
    for fn in files:
        impl, regime, _ = classify(fn)
        if impl is None:
            continue
        data = json.load(open(fn))
        n = data["n_validators"]
        recs = [tuple(r) for r in data["records"]]
        if not recs:
            continue
        for label, types in (("D-core", D_CORE), ("D-all", D_ALL)):
            summ, per = analyze(recs, n, types, label)
            summ.update(impl=impl, regime=regime, file=os.path.basename(fn),
                        demand_model=label)
            rows.append(summ)
        json.dump(rows[-1], open(os.path.join(
            PROC, os.path.basename(fn).replace(".json", "_summary.json")), "w"),
            indent=2)

    json.dump(rows, open(os.path.join(PROC, "all_summaries.json"), "w"), indent=2)

    # ---- aggregate across runs ----
    groups = defaultdict(list)
    for r in rows:
        groups[(r["impl"], r["regime"], r["n"], r["demand_model"])].append(r)

    print("=" * 108)
    print("TABLE 1  Theoretical vs measured persistence")
    print("=" * 108)
    hdr = (f"{'implementation':<14}{'regime':<18}{'model':<8}{'n':>4}{'runs':>5}"
           f"{'views':>8}{'m':>7}{'k':>7}{'rho':>8}{'pi theory':>11}"
           f"{'pi measured':>14}{'error':>9}")
    print(hdr)
    t1 = []
    for key in sorted(groups, key=lambda k: (k[0], k[1], k[2] or 0, k[3])):
        impl, regime, n, dm = key
        g = groups[key]
        pim = [x["pi_measured"] for x in g]
        pit = [x["pi_theory"] for x in g]
        ms = [x["m_mean"] for x in g]
        ks = [x["k_mean"] for x in g]
        rh = [x["rho_mean"] for x in g]
        vw = sum(x["views"] for x in g)
        err = abs(statistics.mean(pim) - statistics.mean(pit))
        c = ci95(pim)
        t1.append({"impl": impl, "regime": regime, "n": n, "model": dm,
                   "runs": len(g), "views": vw,
                   "m": statistics.mean(ms), "k": statistics.mean(ks),
                   "rho": statistics.mean(rh),
                   "pi_theory": statistics.mean(pit),
                   "pi_measured": statistics.mean(pim), "ci95": c, "error": err})
        print(f"{impl:<14}{regime:<18}{dm:<8}{n:>4}{len(g):>5}{vw:>8}"
              f"{statistics.mean(ms):>7.2f}{statistics.mean(ks):>7.2f}"
              f"{statistics.mean(rh):>8.4f}{statistics.mean(pit):>11.4f}"
              f"{statistics.mean(pim):>9.4f}+/-{c:<4.3f}{err:>9.4f}")

    with open(os.path.join(TAB, "table1_theory_vs_measured.json"), "w") as f:
        json.dump(t1, f, indent=2)

    print()
    print("=" * 108)
    print("TABLE 2  Hub-union fit quality  (rho = share of predicted edges not observed)")
    print("=" * 108)
    print(f"{'implementation':<14}{'regime':<18}{'model':<8}{'n':>4}"
          f"{'support':>9}{'max edges':>11}{'m':>7}{'m cv':>8}{'k cv':>8}"
          f"{'rho':>9}{'hub-union?':>12}")
    t2 = []
    for key in sorted(groups, key=lambda k: (k[0], k[1], k[2] or 0, k[3])):
        impl, regime, n, dm = key
        g = groups[key]
        sup = statistics.mean([x["support_mean"] for x in g])
        rho = statistics.mean([x["rho_mean"] for x in g])
        mcv = statistics.mean([x["m_cv"] for x in g])
        kcv = statistics.mean([x["k_cv"] for x in g])
        verdict = "yes" if rho <= 0.15 and mcv <= 0.5 and kcv <= 0.5 else "NO"
        t2.append({"impl": impl, "regime": regime, "n": n, "model": dm,
                   "support": sup, "max_edges": n * (n - 1) // 2,
                   "m": statistics.mean([x["m_mean"] for x in g]),
                   "m_cv": mcv, "k_cv": kcv, "rho": rho, "hub_union": verdict})
        print(f"{impl:<14}{regime:<18}{dm:<8}{n:>4}{sup:>9.2f}"
              f"{n*(n-1)//2:>11}{statistics.mean([x['m_mean'] for x in g]):>7.2f}"
              f"{mcv:>8.3f}{kcv:>8.3f}{rho:>9.4f}{verdict:>12}")
    with open(os.path.join(TAB, "table2_fit_quality.json"), "w") as f:
        json.dump(t2, f, indent=2)

    # ---- Figure 1: theory vs measured ----
    core = [r for r in t1 if r["model"] == "D-core"]
    if core:
        xs = [r["pi_theory"] for r in core]
        ys = [r["pi_measured"] for r in core]
        lo, hi = min(xs + ys + [0.0]), max(xs + ys + [1.0])
        write(os.path.join(FIG, "fig1_theory_vs_measured.svg"), line_chart(
            [Series("y = x", [lo, hi], [lo, hi], dashed=True),
             Series("measured", xs, ys)],
            "Figure 1  Predicted vs measured support persistence",
            "pi predicted from measured (n, m, k)", "pi measured from the trace",
            subtitle="Points on the dashed line mean the closed form predicted the trace exactly.",
            y_fmt="{:.2f}", x_fmt="{:.2f}"))

    # ---- Figure 2: persistence vs n ----
    cb = sorted([r for r in t1 if r["impl"] == "CometBFT" and r["model"] == "D-core"],
                key=lambda r: r["n"])
    if len(cb) > 1:
        write(os.path.join(FIG, "fig2_persistence_vs_n.svg"), line_chart(
            [Series("measured", [r["n"] for r in cb], [r["pi_measured"] for r in cb]),
             Series("predicted", [r["n"] for r in cb], [r["pi_theory"] for r in cb],
                    dashed=True)],
            "Figure 2  Persistence vs validator count (CometBFT)",
            "validators n", "support persistence",
            subtitle="No pipeline sweep: neither implementation exposes per-view leader rotation.",
            y_fmt="{:.2f}", x_fmt="{:g}"))

    print(f"\nwrote tables to {TAB} and figures to {FIG}")
    return t1, t2


if __name__ == "__main__":
    main()
