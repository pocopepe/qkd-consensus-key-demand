#!/usr/bin/env python3
"""E3d: held-out test of the role-dependent participation correction.

Uses the ORIGINAL (serialised-delay) emulator binary on purpose: it is a
reproducible source of lost votes, which is what the correction is about. The
geographies are NEW (seeds e3d-geo-<n>-<g>); the 20 E3 geographies on which the
correction was found are development data and are not reused."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import e3_driver as d
d.OUT = f"{HERE}/raw_d"; d.FAIL = f"{HERE}/failures_d.json"; d.DURATION_S = 120
NS, GEOS = [8, 16, 32], 8

def main():
    os.makedirs(d.OUT, exist_ok=True)
    for n in NS:
        for g in range(GEOS):
            try:
                d.one(f"role_n{n}_g{g}", n, f"e3d-geo-{n}-{g}", [])
            except d.subprocess.TimeoutExpired:
                d.fail(f"role_n{n}_g{g}", "timeout expired")
    print("E3D_DONE", flush=True)

if __name__ == "__main__":
    main()
