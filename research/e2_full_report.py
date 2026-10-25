#!/usr/bin/env python3
"""E2 full matrix aggregation: per-run stats, per-n statistics, figures, tables."""
from __future__ import annotations

import glob
import json
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research.e1_analyze import D_CORE, analyze
from scripts.plot_svg import Series, line_chart, write

E2 = "research/results/e2_full"
RAW, PROC = f"{E2}/raw", f"{E2}/processed"
FIG, TAB = f"{E2}/figures", f"{E2}/tables"

LOCKED = {4: 0.8333333333, 7: 0.6666666667, 10: 0.6111111111,
          16: 0.5666666667, 32: 0.5322580645}
TAG = re.compile(r"n(\d+)_(roundrobin|fixed)_run(\d+)\.json")


def ci95(xs):
    return 1.96 * statistics.stdev(xs) / math.sqrt(len(xs)) if len(xs) > 1 else 0.0


def per_run(path):
    m = TAG.search(os.path.basename(path))
    n, mode, run = int(m.group(1)), m.group(2), int(m.group(3))
    d = json.load(open(path))
    recs = [tuple(r) for r in d["records"]]
    tmo = {int(k) for k in d.get("timeout_views", {})}
    props = {int(k): v for k, v in d.get("proposers", {}).items()}
    allv = sorted({r[0] for r in recs})

    out = {"n": n, "mode": mode, "run": run, "views_total": len(allv),
           "timeout_views": len(tmo & set(allv)),
           "timeout_fraction": len(tmo & set(allv)) / max(len(allv), 1)}

    for label, keep in (("all", lambda v: True),
                        ("happy", lambda v: v not in tmo),
                        ("timeout", lambda v: v in tmo)):
        sub = [r for r in recs if keep(r[0])]
        if not sub:
            out[label] = None
            continue
        s, _ = analyze(sub, n, D_CORE, label)
        out[label] = {"views": s["views"], "support": s["support_mean"],
                      "m": s["m_mean"], "m_sd": s["m_sd"],
                      "k": s["k_mean"], "k_sd": s["k_sd"],
                      "rho": s["rho_mean"], "pi": s["pi_measured"],
                      "pi_sd": s["pi_sd"]}

    vs = sorted(props)
    consec = [(a, b) for a, b in zip(vs, vs[1:]) if b == a + 1]
    changed = sum(1 for a, b in consec if props[a] != props[b])
    out["leader_change_rate"] = changed / max(len(consec), 1)
    out["leader_first20"] = [props[v] for v in vs[:20]]
    out["leader_freq"] = dict(Counter(props.values()))
    return out


def main():
    for d in (PROC, FIG, TAB):
        os.makedirs(d, exist_ok=True)
    files = sorted(glob.glob(f"{RAW}/*.json"))
    runs = []
    for f in files:
        try:
            runs.append(per_run(f))
        except Exception as e:
            print(f"  skip {f}: {e}")
    json.dump(runs, open(f"{PROC}/all_runs.json", "w"), indent=2)
    print(f"{len(runs)} runs parsed\n")

    groups = defaultdict(list)
    for r in runs:
        groups[(r["mode"], r["n"])].append(r)

    # ---------- Table 1: round-robin, theory vs measured ----------
    print("=" * 104)
    print("TABLE 1  Round-robin arm: measured pi vs LOCKED prediction (happy-path views)")
    print("=" * 104)
    print(f"{'n':>4}{'runs':>6}{'views':>9}{'m':>8}{'k':>8}{'rho':>9}"
          f"{'pi theory':>12}{'pi measured':>14}{'95% CI':>10}{'error':>9}")
    t1, maxerr = [], 0.0
    for n in sorted(LOCKED):
        g = [r for r in groups.get(("roundrobin", n), []) if r["happy"]]
        if not g:
            continue
        pis = [r["happy"]["pi"] for r in g]
        mm = statistics.mean([r["happy"]["m"] for r in g])
        kk = statistics.mean([r["happy"]["k"] for r in g])
        rh = statistics.mean([r["happy"]["rho"] for r in g])
        vw = sum(r["happy"]["views"] for r in g)
        mean_pi, c = statistics.mean(pis), ci95(pis)
        err = abs(mean_pi - LOCKED[n])
        maxerr = max(maxerr, err)
        t1.append({"n": n, "runs": len(g), "views": vw, "m": mm, "k": kk,
                   "rho": rh, "pi_theory": LOCKED[n], "pi_measured": mean_pi,
                   "pi_sd": statistics.pstdev(pis), "ci95": c, "error": err,
                   "per_run_pi": pis})
        print(f"{n:>4}{len(g):>6}{vw:>9}{mm:>8.4f}{kk:>8.4f}{rh:>9.5f}"
              f"{LOCKED[n]:>12.6f}{mean_pi:>14.6f}{c:>10.5f}{err:>9.6f}")
    print(f"\n  maximum absolute error across all n: {maxerr:.6f}")

    # ---------- Table 2: fixed-leader control ----------
    print()
    print("=" * 104)
    print("TABLE 2  Fixed-leader control: locked prediction m=1, k=1, rho=0, pi=1")
    print("=" * 104)
    print(f"{'n':>4}{'runs':>6}{'views':>9}{'m':>8}{'k':>8}{'rho':>9}"
          f"{'pi measured':>14}{'95% CI':>10}{'error vs 1':>12}")
    t2, cmaxerr = [], 0.0
    for n in sorted(LOCKED):
        g = [r for r in groups.get(("fixed", n), []) if r["happy"]]
        if not g:
            continue
        pis = [r["happy"]["pi"] for r in g]
        mm = statistics.mean([r["happy"]["m"] for r in g])
        kk = statistics.mean([r["happy"]["k"] for r in g])
        rh = statistics.mean([r["happy"]["rho"] for r in g])
        vw = sum(r["happy"]["views"] for r in g)
        mean_pi, c = statistics.mean(pis), ci95(pis)
        err = abs(mean_pi - 1.0)
        cmaxerr = max(cmaxerr, err)
        t2.append({"n": n, "runs": len(g), "views": vw, "m": mm, "k": kk,
                   "rho": rh, "pi_measured": mean_pi, "ci95": c, "error": err,
                   "per_run_pi": pis})
        print(f"{n:>4}{len(g):>6}{vw:>9}{mm:>8.4f}{kk:>8.4f}{rh:>9.5f}"
              f"{mean_pi:>14.6f}{c:>10.5f}{err:>12.6f}")
    print(f"\n  maximum control error: {cmaxerr:.6f}")

    # ---------- Table 3: timeouts ----------
    print()
    print("=" * 104)
    print("TABLE 3  Timeout views (not discarded)")
    print("=" * 104)
    print(f"{'n':>4}{'mode':>12}{'timeout frac':>14}{'timeout views':>15}"
          f"{'pi(timeout)':>13}{'pi(all)':>10}")
    t3 = []
    for mode in ("roundrobin", "fixed"):
        for n in sorted(LOCKED):
            g = groups.get((mode, n), [])
            if not g:
                continue
            tf = statistics.mean([r["timeout_fraction"] for r in g])
            tv = sum(r["timeout_views"] for r in g)
            tpi = [r["timeout"]["pi"] for r in g if r["timeout"]]
            api = [r["all"]["pi"] for r in g if r["all"]]
            t3.append({"mode": mode, "n": n, "timeout_fraction": tf,
                       "timeout_views": tv,
                       "pi_timeout": statistics.mean(tpi) if tpi else None,
                       "pi_all": statistics.mean(api) if api else None})
            print(f"{n:>4}{mode:>12}{tf:>14.5f}{tv:>15}"
                  f"{(statistics.mean(tpi) if tpi else float('nan')):>13.5f}"
                  f"{(statistics.mean(api) if api else float('nan')):>10.5f}")

    for name, tab in (("table1_roundrobin", t1), ("table2_control", t2),
                      ("table3_timeouts", t3)):
        json.dump(tab, open(f"{TAB}/{name}.json", "w"), indent=2)

    # ---------- Figures ----------
    if t1:
        ns = [r["n"] for r in t1]
        dense = list(range(4, 33))
        write(f"{FIG}/fig1_pi_vs_n.svg", line_chart(
            [Series("theory (n+1)/(2(n-1))", dense,
                    [(x + 1) / (2 * (x - 1)) for x in dense], dashed=True),
             Series("measured", ns, [r["pi_measured"] for r in t1])],
            "Figure 1  Support persistence vs validator count",
            "validators n", "support persistence pi",
            subtitle="Locked curve plotted before the matrix ran; points are 5-run means.",
            y_fmt="{:.2f}", x_fmt="{:g}"))
        write(f"{FIG}/fig2_residual.svg", line_chart(
            [Series("zero", [min(ns), max(ns)], [0.0, 0.0], dashed=True),
             Series("residual", ns, [r["pi_measured"] - r["pi_theory"] for r in t1])],
            "Figure 2  Residual: measured minus theory",
            "validators n", "pi_measured - pi_theory",
            subtitle="Locked falsification band is +/- 0.05.",
            y_fmt="{:.4f}", x_fmt="{:g}"))
        write(f"{FIG}/fig3_m_k_vs_n.svg", line_chart(
            [Series("m measured", ns, [r["m"] for r in t1]),
             Series("k measured", ns, [r["k"] for r in t1]),
             Series("m predicted", ns, [2.0] * len(ns), dashed=True),
             Series("k predicted", ns, [1.0] * len(ns), dashed=True)],
            "Figure 3  Hub structure vs validator count",
            "validators n", "hubs per view",
            subtitle="The theorem's prediction is conditional on these staying at m=2, k=1.",
            y_fmt="{:.1f}", x_fmt="{:g}"))
    if t3:
        rr = [r for r in t3 if r["mode"] == "roundrobin"]
        fx = [r for r in t3 if r["mode"] == "fixed"]
        write(f"{FIG}/fig4_timeout_fraction.svg", line_chart(
            [Series("round-robin", [r["n"] for r in rr],
                    [r["timeout_fraction"] for r in rr]),
             Series("fixed leader", [r["n"] for r in fx],
                    [r["timeout_fraction"] for r in fx])],
            "Figure 4  Timeout-view fraction vs validator count",
            "validators n", "fraction of views with a local timeout",
            subtitle="Timeout views are reported separately, never discarded.",
            y_fmt="{:.3f}", x_fmt="{:g}"))

    print(f"\nwrote tables to {TAB}, figures to {FIG}")
    return t1, t2, t3, maxerr, cmaxerr


if __name__ == "__main__":
    main()
