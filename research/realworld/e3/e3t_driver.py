#!/usr/bin/env python3
"""E3T: targeted single-role vote loss (falsification test of the role-dependent
proposition). Chained HotStuff, round-robin rotation, per-message-delay emulation
(hotstuff_e3t = E2 logging + emulation_fix.diff + e3t_injector.diff; build_e3t.sh).

Each geography runs every arm, so arms are compared WITHIN a geography. At equal
total loss LAMBDA (expected suppressed votes per view) the arms differ only in whose
vote is suppressed:
  a      previous leader L(t-1)           (proposition: costs 2 carried units)
  g      leader two views ahead L(t+2)    (costs 2)
  b      current leader L(t)              (costs 1)
  other  any other sender                 (costs 1)
  blind  every sender, same probability   (null control; role-blind by design)
  none   no suppression                   (baseline)
Suppression happens at the sender, before the E2 SEND_VOTE record, so the frozen
parser sees the vote as never sent. The injector logs every suppression separately.

Validity guard (fixed before any held-out run): a run is invalid if the host was suspended during it
(CLOCK_BOOTTIME advanced more than 5 s beyond CLOCK_MONOTONIC) or its wall time exceeded 2x its duration
plus 60 s (host stalled). An invalid run is moved to <out>/invalid/ with the reason and re-run once; a run
that exits nonzero is recorded and re-run once. Every invalidation and retry is logged, never silent.

Usage: e3t_driver.py dev|heldout     (dev = smoke seeds only; heldout = locked design). Resumable."""
import json, os, random, re, shutil, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import e3_driver as d

BIN = f"{d.HS}/hotstuff_e3t"
ARMS = ["none", "a", "g", "b", "other", "blind"]
LAMBDA = 0.2                       # expected suppressed votes per view, every arm except none
SUPP = re.compile(r"E3T SUPPRESS_VOTE view=(\d+) from=(\d+) to=(\d+) role=(\w+)")

def p_for(arm, n):
    """Per-eligible-sender probability giving LAMBDA suppressed votes per view."""
    eligible = {"a": 1, "g": 1, "b": 1, "other": n - 4, "blind": n - 1}
    return 0.0 if arm == "none" else LAMBDA / eligible[arm]

def one(tag, n, geo_seed, arm, out, duration):
    dest = f"{out}/{tag}.json"
    if os.path.exists(dest):
        return
    locs = random.Random(geo_seed).sample(d.CITIES, n)
    cfg, log = f"/tmp/e3t_{tag}.cue", f"/tmp/e3t_{tag}.log"
    open(cfg, "w").write(d.cue(n, locs, []))
    env = dict(os.environ, E3T_ROLE=arm, E3T_P=repr(p_for(arm, n)), E3T_SEED=f"{geo_seed}|{arm}")
    load0, t0 = os.getloadavg()[0], time.time()
    slept0 = time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()
    with open(log, "w") as f:
        p = subprocess.run([BIN, "run", "--cue", cfg, "--batch-size", "10", "--max-concurrent", "20",
                            "--duration", f"{duration}s", "--log-level", "info",
                            "--log-pkgs", "comm:debug,synchronizer:debug,votingmachine:debug"],
                           stdout=f, stderr=subprocess.STDOUT, timeout=duration * 4 + 120, env=env)
    if p.returncode != 0:
        d.FAIL = f"{out}/failures.json"; d.fail(tag, "nonzero exit", open(log, errors="ignore").read()); return
    supp = [tuple(int(x) if x.isdigit() else x for x in m.groups()) for m in SUPP.finditer(open(log, errors="ignore").read())]
    r = subprocess.run([sys.executable, f"{d.ROOT}/research/e2_parse.py", log, str(n), dest], capture_output=True, text=True)
    if r.returncode != 0:
        d.FAIL = f"{out}/failures.json"; d.fail(tag, "parse failed", r.stderr); return
    rec = json.load(open(dest))
    rec["e3_meta"] = {"tag": tag, "n": n, "geo_seed": geo_seed, "locations": locs, "silent": [], "arm": arm,
                      "lambda": LAMBDA if arm != "none" else 0.0, "p": p_for(arm, n), "duration_s": duration,
                      "loadavg_before": load0, "loadavg_after": os.getloadavg()[0], "wall_s": time.time() - t0}
    rec["suppressed"] = supp
    slept = (time.clock_gettime(time.CLOCK_BOOTTIME) - time.monotonic()) - slept0
    rec["e3_meta"]["suspended_s"] = slept
    json.dump(rec, open(dest, "w")); os.remove(log); os.remove(cfg)
    why = ("host suspended %.0f s" % slept) if slept > 5 else ("wall %.0f s > 2x duration + 60" % (time.time() - t0)) if time.time() - t0 > 2 * duration + 60 else None
    if why:
        os.makedirs(f"{out}/invalid", exist_ok=True); shutil.move(dest, f"{out}/invalid/{tag}.json")
        d.FAIL = f"{out}/failures.json"; d.fail(tag, "invalid run", why); print(f"  {tag}: INVALID ({why})", flush=True)
    print(f"  {tag}: {len({x[0] for x in rec['records']})} views, {len(supp)} suppressed, "
          f"load {load0:.1f}->{os.getloadavg()[0]:.1f}, {time.time() - t0:.0f}s", flush=True)

def main(mode):
    if mode == "dev":
        out, ns, geos, dur, seed = f"{HERE}/raw_t_dev", [16], 1, 40, "e3t-dev-geo"
    else:
        out, ns, geos, dur, seed = f"{HERE}/raw_t", [16, 32], 6, 120, "e3t-geo"
    os.makedirs(out, exist_ok=True)
    for attempt in (1, 2):                      # second pass re-runs anything missing (failed or invalid), once
        for n in ns:
            for g in range(geos):
                for arm in ARMS:
                    tag = f"t_n{n}_g{g}_{arm}"
                    if attempt == 2 and not os.path.exists(f"{out}/{tag}.json"):
                        print(f"  {tag}: retry (attempt 2)", flush=True)
                    try:
                        one(tag, n, f"{seed}-{n}-{g}", arm, out, dur)
                    except subprocess.TimeoutExpired:
                        d.FAIL = f"{out}/failures.json"; d.fail(tag, "timeout expired")
    print(f"E3T_{mode.upper()}_DONE", flush=True)

if __name__ == "__main__":
    main(sys.argv[1])
