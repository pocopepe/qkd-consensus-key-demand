#!/usr/bin/env python3
"""E2 full matrix driver: 5 validator counts x 2 leader modes x 5 runs.

Resumable: each completed run is parsed to disk immediately and skipped on
relaunch. Failures are recorded in failures.json rather than silently retried.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

ROOT = "/home/pocopepe/code/predictive"
BIN = "/tmp/hsbin"
OUT = f"{ROOT}/research/results/e2_full/raw"
FAILLOG = f"{ROOT}/research/results/e2_full/failures.json"

NS = [4, 7, 10, 16, 32]
MODES = ["round-robin", "fixed"]
RUNS = 5
DUR = {4: "25s", 7: "25s", 10: "30s", 16: "40s", 32: "60s"}
MIN_VIEWS = 1000


def record_failure(tag, reason, detail=""):
    fails = []
    if os.path.exists(FAILLOG):
        fails = json.load(open(FAILLOG))
    fails.append({"tag": tag, "reason": reason, "detail": detail[:800],
                  "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    json.dump(fails, open(FAILLOG, "w"), indent=2)


def one_run(n, mode, run):
    tag = f"n{n}_{mode.replace('-', '')}_run{run}"
    dest = f"{OUT}/{tag}.json"
    if os.path.exists(dest):
        print(f"  {tag}: exists, skip", flush=True)
        return True
    log = f"/tmp/e2f_{tag}.log"
    cmd = [BIN, "run", "--replicas", str(n), "--clients", "2",
           "--batch-size", "10", "--max-concurrent", "20",
           "--consensus", "chainedhotstuff", "--communication", "clique",
           "--leader-rotation", mode, "--duration", DUR[n],
           "--fixed-timeout", "100ms", "--log-level", "info",
           "--log-pkgs", "comm:debug,synchronizer:debug,votingmachine:debug"]
    t0 = time.time()
    with open(log, "w") as f:
        p = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT,
                           timeout=int(DUR[n][:-1]) * 6 + 120)
    if p.returncode != 0:
        record_failure(tag, "nonzero exit", open(log, errors="ignore").read()[-800:])
        print(f"  {tag}: FAILED rc={p.returncode}", flush=True)
        return False
    r = subprocess.run([sys.executable, f"{ROOT}/research/e2_parse.py",
                        log, str(n), dest], capture_output=True, text=True)
    if r.returncode != 0:
        record_failure(tag, "parse failed", r.stderr[-800:])
        print(f"  {tag}: PARSE FAILED", flush=True)
        return False
    d = json.load(open(dest))
    views = len({rec[0] for rec in d["records"]})
    if views < MIN_VIEWS:
        record_failure(tag, "insufficient views", f"{views} < {MIN_VIEWS}")
        print(f"  {tag}: only {views} views (kept, flagged)", flush=True)
    else:
        print(f"  {tag}: {views} views in {time.time()-t0:.0f}s", flush=True)
    os.remove(log)
    return True


def main():
    os.makedirs(OUT, exist_ok=True)
    for n in NS:
        for mode in MODES:
            for run in range(1, RUNS + 1):
                try:
                    one_run(n, mode, run)
                except subprocess.TimeoutExpired:
                    record_failure(f"n{n}_{mode}_run{run}", "timeout expired")
                    print(f"  n{n}_{mode}_run{run}: TIMEOUT", flush=True)
                except Exception as e:
                    record_failure(f"n{n}_{mode}_run{run}", "exception", str(e))
                    print(f"  n{n}_{mode}_run{run}: EXC {e}", flush=True)
    print("E2_MATRIX_DONE", flush=True)


if __name__ == "__main__":
    main()
