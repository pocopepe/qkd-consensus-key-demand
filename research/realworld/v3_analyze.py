#!/usr/bin/env python3
"""Cycle-3 Aptos replication. Runs the LOCKED v2_analyze.py unchanged on the held-out raw_v3
epochs: per-epoch statistics are computed in parallel (WORKERS processes) by v2_analyze's own
analyze_one, then v2_analyze.main() is run with those results substituted, so every verdict
uses the v2 code and bands byte-for-byte. Usage: v3_analyze.py <raw_v3_dir> <out_json>"""
import glob, os, sys
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import v2_analyze as v2a

def per_epoch(path):
    return v2a.analyze_one(v2a.load_epoch(path), True)

if __name__ == "__main__":
    files = sorted(glob.glob(os.path.join(sys.argv[1], "epoch_*.json")))
    with Pool(int(os.environ.get("WORKERS", "10"))) as p:
        cache = {r["epoch"]: r for r in p.map(per_epoch, files)}
    v2a.load_epoch = lambda f: {"epoch": int(os.path.basename(f)[6:-5])}
    v2a.analyze_one = lambda ep, with_zoo: cache[ep["epoch"]]
    sys.exit(v2a.main())
