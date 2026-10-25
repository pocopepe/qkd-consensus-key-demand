#!/usr/bin/env python3
"""E3: chained HotStuff under emulated WAN latency (relab's built-in
WonderProxy city matrix) and silent-proposer faults. Same instrumented tree
and frozen parser as E2; no consensus logic touched. Resumable; failures are
recorded, never silently retried. Geography per run = seeded city sample, so
run-to-run spread reflects real differences in who is far from whom."""
from __future__ import annotations

import json, os, random, re, subprocess, sys, time

ROOT = "/home/pocopepe/code/predictive"
HS = f"{ROOT}/ext/relab-hotstuff"
BIN = f"{HS}/hotstuff"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = f"{HERE}/raw"
FAIL = f"{HERE}/failures.json"
DURATION_S = 120
GEOS = 5
WAN_NS = [8, 16, 32, 64]
FAULT_N = 16
FAULT_SETS = {1: [4], 5: [2, 5, 8, 11, 14]}   # non-adjacent under round-robin

CITIES = sorted(set(re.findall(r'"([A-Z][A-Za-z]*)"', open(f"{HS}/internal/latency/latency_matrix.go").read())))


def cue(n, locs, silent):
    byz = f"\n\tbyzantineStrategy: {{\n\t\tsilentproposer: {json.dumps(silent)}\n\t}}" if silent else ""
    return ('package config\n\nconfig: {\n\treplicaHosts: ["localhost"]\n\tclientHosts: ["localhost"]\n'
            f'\treplicas: {n}\n\tclients: 2\n\tlocations: {json.dumps(locs)}\n\tleaderRotation: "round-robin"{byz}\n}}\n')


def fail(tag, why, detail=""):
    f = json.load(open(FAIL)) if os.path.exists(FAIL) else []
    f.append({"tag": tag, "reason": why, "detail": detail[-600:], "utc": time.strftime("%FT%TZ", time.gmtime())})
    json.dump(f, open(FAIL, "w"), indent=1)


def one(tag, n, geo_seed, silent):
    dest = f"{OUT}/{tag}.json"
    if os.path.exists(dest):
        return
    locs = random.Random(geo_seed).sample(CITIES, n)
    cfg, log = f"/tmp/e3_{tag}.cue", f"/tmp/e3_{tag}.log"
    open(cfg, "w").write(cue(n, locs, silent))
    load0 = os.getloadavg()[0]
    t0 = time.time()
    with open(log, "w") as f:
        p = subprocess.run([BIN, "run", "--cue", cfg, "--batch-size", "10", "--max-concurrent", "20",
                            "--duration", f"{DURATION_S}s", "--log-level", "info",
                            "--log-pkgs", "comm:debug,synchronizer:debug,votingmachine:debug"],
                           stdout=f, stderr=subprocess.STDOUT, timeout=DURATION_S * 4 + 120)
    if p.returncode != 0:
        fail(tag, "nonzero exit", open(log, errors="ignore").read()); print(f"  {tag}: FAILED", flush=True); return
    r = subprocess.run([sys.executable, f"{ROOT}/research/e2_parse.py", log, str(n), dest], capture_output=True, text=True)
    if r.returncode != 0:
        fail(tag, "parse failed", r.stderr); print(f"  {tag}: PARSE FAILED", flush=True); return
    d = json.load(open(dest))
    d["e3_meta"] = {"tag": tag, "n": n, "geo_seed": geo_seed, "locations": locs, "silent": silent,
                    "duration_s": DURATION_S, "loadavg_before": load0, "loadavg_after": os.getloadavg()[0],
                    "wall_s": time.time() - t0}
    json.dump(d, open(dest, "w"))
    os.remove(log)
    print(f"  {tag}: {len({x[0] for x in d['records']})} views, load {load0:.1f}->{os.getloadavg()[0]:.1f}", flush=True)


def main():
    os.makedirs(OUT, exist_ok=True)
    jobs = [(f"wan_n{n}_g{g}", n, f"e3-geo-{n}-{g}", []) for n in WAN_NS for g in range(GEOS)]
    jobs += [(f"fault_f{f}_g{g}", FAULT_N, f"e3-geo-{FAULT_N}-{g}", s) for f, s in FAULT_SETS.items() for g in range(GEOS)]
    for tag, n, seed, silent in jobs:
        try:
            one(tag, n, seed, silent)
        except subprocess.TimeoutExpired:
            fail(tag, "timeout expired"); print(f"  {tag}: TIMEOUT", flush=True)
    print("E3_DONE", flush=True)


if __name__ == "__main__":
    main()
