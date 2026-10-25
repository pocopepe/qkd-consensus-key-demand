#!/usr/bin/env python3
"""E2 smoke analysis: hub-union fit and persistence, happy vs timeout views."""
from __future__ import annotations

import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research.e1_analyze import D_ALL, D_CORE, analyze, build_views, min_vertex_cover


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "research/results/e2_smoke/raw/smoke_run1.json"
    data = json.load(open(src))
    n = data["n_validators"]
    recs = [tuple(r) for r in data["records"]]
    tmo = {int(k) for k in data.get("timeout_views", {})}
    props = {int(k): v for k, v in data.get("proposers", {}).items()}

    pi_pred = (n + 1) / (2 * (n - 1))
    print(f"n = {n}   PREDICTION (locked before the run): m=2, k=1, rho=0, "
          f"pi = (n+1)/(2(n-1)) = {pi_pred:.6f}\n")

    splits = [
        ("all views", lambda v: True),
        ("happy-path views only", lambda v: v not in tmo),
        ("timeout views only", lambda v: v in tmo),
    ]
    out = {}
    for label, keep in splits:
        sub = [r for r in recs if keep(r[0])]
        if not sub:
            print(f"  {label}: no views\n")
            continue
        summ, per = analyze(sub, n, D_CORE, label)
        out[label] = summ
        print(f"  {label}")
        print(f"    views              {summ['views']}")
        print(f"    support size       {summ['support_mean']:.3f} of {n*(n-1)//2}")
        print(f"    m (min cover)      {summ['m_mean']:.4f} +/- {summ['m_sd']:.4f}"
              f"  (cv {summ['m_cv']:.4f})")
        print(f"    k (cover overlap)  {summ['k_mean']:.4f} +/- {summ['k_sd']:.4f}"
              f"  (cv {summ['k_cv']:.4f})")
        print(f"    rho                {summ['rho_mean']:.6f}")
        print(f"    pi measured        {summ['pi_measured']:.6f} +/- {summ['pi_sd']:.6f}")
        print(f"    pi theory(m,k)     {summ['pi_theory']:.6f}   (m={summ['m_used']}, k={summ['k_used']})")
        print(f"    |pi - 0.833333|    {abs(summ['pi_measured'] - pi_pred):.6f}")
        print()

    # leader rotation check
    vs = sorted(props)[:400]
    changes = sum(1 for a, b in zip(vs, vs[1:])
                  if b == a + 1 and props[a] != props[b])
    consec = sum(1 for a, b in zip(vs, vs[1:]) if b == a + 1)
    print(f"  leader changes on {changes}/{consec} consecutive view pairs "
          f"({100*changes/max(consec,1):.1f}%)")
    print(f"  timeout view fraction: {len(tmo)}/{len(set(r[0] for r in recs))} "
          f"= {len(tmo)/max(len(set(r[0] for r in recs)),1):.5f}")

    dst = "research/results/e2_smoke/analysis.json"
    json.dump({"prediction": {"m": 2, "k": 1, "rho": 0, "pi": pi_pred},
               "splits": out,
               "leader_change_rate": changes / max(consec, 1),
               "timeout_fraction": len(tmo) / max(len(set(r[0] for r in recs)), 1)},
              open(dst, "w"), indent=2)
    print(f"\nwrote {dst}")


if __name__ == "__main__":
    main()
