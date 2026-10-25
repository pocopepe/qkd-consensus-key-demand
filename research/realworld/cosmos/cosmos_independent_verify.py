#!/usr/bin/env python3
"""Independent recomputation of the Cosmos per-window statistics. Imports
nothing from cosmos_analyze.py; exact rational arithmetic; different traversal.
Usage: cosmos_independent_verify.py <raw_dir> <cosmos_analyze_output.json>"""
import glob, json, os, sys
from fractions import Fraction as F
mine = {}
for p in sorted(glob.glob(os.path.join(sys.argv[1], "window_*.json"))):
    w = json.load(open(p)); pw = w["power"]; tot = sum(pw.values()); B = w["blocks"]
    miss = [frozenset(b["absent"]) | frozenset(b["nil"]) for b in B]
    pc = sum(F(b["n"] - len(m), b["n"]) for b, m in zip(B, miss)) / len(B)
    pp = sum(F(tot - sum(pw.get(v, 0) for v in m), tot) for m in miss) / len(B)
    both = sum(len(x & y) for x, y in zip(miss, miss[1:])); base = sum(len(x) for x in miss[:-1])
    mine[w["start"]] = {"p_count": float(pc), "p_power": float(pp), "recurrence": (both / base) if base else None,
                        "round_gt0": sum(b["r"] > 0 for b in B) / len(B)}
theirs = {r["start"]: r for r in json.load(open(sys.argv[2]))["per_window"]}
worst = {}
for s, m in mine.items():
    for k, v in m.items():
        t = theirs[s][k]
        d = 0.0 if (v is None and t is None) else (float("inf") if (v is None) != (t is None) else abs(v - t))
        worst[k] = max(worst.get(k, 0.0), d)
bad = False
for k, d in worst.items():
    ok = d < 1e-9; bad |= not ok
    print(f"  {k:11s} max |independent - primary| over {len(mine)} windows = {d:.2e}  {'MATCH' if ok else 'MISMATCH'}")
sys.exit(1 if bad else 0)
