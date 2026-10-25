#!/usr/bin/env python3
# Pooled check for the older sections: a literal in paper.tex is accepted only if some value in its own
# experiment family's result files rounds to it (plain or as a percentage). Prints the chance-match rate
# of each pool so the check's weakness is visible.
import glob
import json
import os
import random
import re
import sys
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
R = os.path.join(ROOT, "research", "results") + "/"
tex = open(os.path.join(ROOT, "paper", "paper.tex")).read()


def numbers_in(path):
    out = set()
    try:
        if path.endswith(".json"):
            def walk(o):
                if isinstance(o, dict):
                    for v in o.values():
                        walk(v)
                elif isinstance(o, list):
                    for v in o:
                        walk(v)
                elif isinstance(o, (int, float)) and not isinstance(o, bool):
                    out.add(float(o))
            walk(json.load(open(path)))
        else:
            for m in re.findall(r"-?\d+\.\d+(?:[eE][-+]?\d+)?", open(path, errors="ignore").read()):
                out.add(float(m))
    except Exception:
        pass
    return out


def pool(*patterns):
    vals = set()
    for p in patterns:
        for f in glob.glob(p, recursive=True):
            if "/raw/" not in f and os.path.isfile(f) and os.path.getsize(f) < 3e7:
                vals |= numbers_in(f)
    return vals


def rounded(vals, d):
    out = set()
    for v in vals:
        for scale in (1, 100):
            for mode in (ROUND_HALF_EVEN, ROUND_HALF_UP):
                try:
                    out.add(Decimal(repr(abs(v) * scale)).quantize(Decimal(1).scaleb(-d), rounding=mode))
                except Exception:
                    pass
    return out


FAMILIES = {
    "E2/E1 validation (frozen e2_full, e1)": (
        pool(R + "e2_full/processed/*.json", R + "e2_full/tables/*", R + "e2_full/E2_FULL_REPORT.md",
             R + "e1/processed/*.json", R + "e1/tables/*", R + "e1/E1_REPORT.md"),
        ["0.9869", "0.9991", "2.996",
         "0.833333", "0.666657", "0.611085", "0.566645", "0.531836"]),
    "Sec. V predictor zoo (frozen corrected zoo)": (
        pool(R + "predictor_zoo_corrected/*", os.path.join(ROOT, "research/PREDICTOR_ZOO_CORRECTED_REPORT.md")),
        ["0.185417", "0.945833"]),
}

bad = 0
rng = random.Random(1)
for name, (vals, literals) in FAMILIES.items():
    tables = {}
    missing = []
    for lit in literals:
        assert lit in tex, f"{lit} is listed here but no longer appears in paper.tex"
        d = len(lit.split(".")[1])
        if d not in tables:
            tables[d] = rounded(vals, d)
        if Decimal(lit) not in tables[d]:
            missing.append(lit)
    chance = {}
    for d, t in tables.items():
        chance[d] = sum(Decimal(f"{rng.random():.{d}f}") in t for _ in range(3000)) / 3000
    print(f"{name}\n  pool {len(vals)} values; {len(literals) - len(missing)}/{len(literals)} literals sourced; "
          f"chance-match rate by precision: " + ", ".join(f"{d}dp {c:.3f}" for d, c in sorted(chance.items())))
    for m in missing:
        print("  ** NO SOURCE:", m)
    bad += len(missing)
sys.exit(1 if bad else 0)
