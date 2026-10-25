#!/usr/bin/env python3
"""E3c: E3 repeated with the corrected latency emulation (emulation_fix.diff:
handlers release the per-sender gorums stream before sleeping, so delay is per
message instead of accumulating). Same design and the SAME geography seeds as
E3, so every run is paired with an E3 run. f=5 fault runs are lengthened because
five silent leaders stall the view timer (E3 got only ~35 views in 120 s)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import e3_driver as d

d.BIN = f"{d.HS}/hotstuff_e3c"
d.OUT = f"{HERE}/raw_c"
d.FAIL = f"{HERE}/failures_c.json"
F5_DURATION_S = 480

def main():
    os.makedirs(d.OUT, exist_ok=True)
    jobs = [(f"wan_n{n}_g{g}", n, f"e3-geo-{n}-{g}", [], 120) for n in d.WAN_NS for g in range(d.GEOS)]
    jobs += [(f"fault_f{f}_g{g}", d.FAULT_N, f"e3-geo-{d.FAULT_N}-{g}", s, F5_DURATION_S if f == 5 else 120)
             for f, s in d.FAULT_SETS.items() for g in range(d.GEOS)]
    for tag, n, seed, silent, dur in jobs:
        d.DURATION_S = dur
        try:
            d.one(tag, n, seed, silent)
        except d.subprocess.TimeoutExpired:
            d.fail(tag, "timeout expired"); print(f"  {tag}: TIMEOUT", flush=True)
    print("E3C_DONE", flush=True)

if __name__ == "__main__":
    main()
