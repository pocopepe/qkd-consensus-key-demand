#!/usr/bin/env python3
"""Proposition 1 under REAL correlated vote loss: Cosmos Hub per-validator absence
sequences drive the chained-rotation simulator (chain_model.simulate).

For a window of consecutive blocks and a set of n validators, validator v's vote in view
t is lost iff v was absent from the commit of block t. Leaders are either round-robin over
the n validators, or drawn independently in proportion to voting power (seeded; repeats
allowed, which is Corollary 2's schedule). Per run: simulated pi, per-role loss rates,
Proposition 1, the complete first-order form, and the exact expectation under
independent loss at the measured per-role rates.
Usage: cosmos_loss_sim.py <cosmos_windows_or_chunks_dir> <out_json> [selection] [n...]"""
import glob, json, os, random, sys
from multiprocessing import Pool
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from chain_model import simulate, prop1, first_order, exact_expected_pi

def cor2(n, s):
    """Corollary 2 (no loss) for normalized stakes s."""
    q = sum(x * x for x in s); e = sum(x ** 3 for x in s)
    return (2 * q - e) + (q - e) * n / (2 * (n - 1)) + (1 - 3 * q + 2 * e) * (n + 1) / (2 * (n - 1))

def load_windows(d):
    out = []
    for f in sorted(glob.glob(os.path.join(d, "window_*.json")) + glob.glob(os.path.join(d, "chunk_*.json"))):
        w = json.load(open(f)); out.append((os.path.basename(f), w["power"], [set(b["absent"]) for b in w["blocks"]]))
    return out

def one(args):
    name, power, absent, n, sel, sched, seed = args
    rng = random.Random(f"{seed}|{name}|{n}|{sel}|{sched}")
    vals = sorted(power)
    if sel == "random":
        chosen = rng.sample(vals, n)
    else:   # "stress": the n validators most often absent in this window, excluding any absent from more than
            # half of its blocks (offline or jailed: a committee of those could not form a quorum at all)
        rate = {v: sum(v in a for a in absent) for v in vals}
        live = [v for v in vals if rate[v] <= len(absent) / 2]
        chosen = sorted(live, key=lambda v: (-rate[v], v))[:n]
    idx = {v: i for i, v in enumerate(chosen)}
    T = len(absent)
    if sched == "rr":
        leaders = [t % n for t in range(T)]
    else:
        w = [power[v] for v in chosen]; leaders = rng.choices(range(n), weights=w, k=T)
    lost_set = {(t, idx[v]) for t, a in enumerate(absent) for v in a if v in idx}
    sim, miss, Tc = simulate(leaders, lambda t, v: (t, v) in lost_set, n)
    sim0, _, _ = simulate(leaders, lambda t, v: False, n)      # same leader sequence, no loss
    distinct = sum(1 for t in range(1, T - 2) if len({leaders[t - 1], leaders[t], leaders[t + 1], leaders[t + 2]}) == 4)
    tot = sum(power[v] for v in chosen); stakes = [power[v] / tot for v in chosen]
    pa, pb, pg = miss["a"] / Tc, miss["b"] / Tc, miss["g"] / Tc; po = miss["other"] / Tc / max(1, n - 4)
    mu2, mu1 = pa + pg, pb + miss["other"] / Tc
    return {"window": name, "n": n, "sel": sel, "sched": sched, "views": Tc, "sim": sim,
            "prop1": prop1(n, mu2, mu1), "first_order": first_order(n, pa, pb, pg, po),
            "exact_indep": exact_expected_pi(n, pa, pb, pg, po), "lost_per_view": (sum(miss.values())) / Tc,
            # combined estimator for repeated leaders: Corollary 2 plus Proposition 1's loss correction,
            # applied on the share of views whose four leaders are distinct
            "loss_effect_sim": sim - sim0,
            "loss_effect_pred": (distinct / max(1, T - 3)) * (prop1(n, mu2 * (T - 3) / max(1, distinct), mu1 * (T - 3) / max(1, distinct)) - (n + 1) / (2 * (n - 1))),
            "combined": (cor2(n, stakes) if sched == "stake" else (n + 1) / (2 * (n - 1)))
                        + (distinct / max(1, T - 3)) * (prop1(n, mu2 * (T - 3) / max(1, distinct), mu1 * (T - 3) / max(1, distinct)) - (n + 1) / (2 * (n - 1))),
            "distinct_leader_share": distinct / max(1, T - 3), "missing": miss}

if __name__ == "__main__":
    wins = load_windows(sys.argv[1]); sels = [sys.argv[3]] if len(sys.argv) > 3 else ["random", "stress"]
    ns = [int(x) for x in sys.argv[4:]] or [16, 32, 64]
    jobs = [(nm, pw, ab, n, s, sch, "c1") for nm, pw, ab in wins for n in ns for s in sels for sch in ("rr", "stake")]
    with Pool(int(os.environ.get("WORKERS", "10"))) as p: rows = p.map(one, jobs, chunksize=4)
    json.dump(rows, open(sys.argv[2], "w"))
    for sch in ("rr", "stake"):
        for s in sels:
            for n in ns:
                rr = [r for r in rows if r["n"] == n and r["sel"] == s and r["sched"] == sch]
                if not rr: continue
                f = lambda k: max(abs(r["sim"] - r[k]) for r in rr)
                print(f"{sch:5} {s:6} n={n:2d} runs={len(rr)} lost/view={sum(r['lost_per_view'] for r in rr)/len(rr):.3f} "
                      f"max|sim-prop1|={f('prop1'):.1e} max|sim-first|={f('first_order'):.1e} max|sim-exact_indep|={f('exact_indep'):.1e} max|sim-combined|={f('combined'):.1e} "
                      f"max|loss effect sim-pred|={max(abs(r['loss_effect_sim'] - r['loss_effect_pred']) for r in rr):.1e} mean loss effect={sum(r['loss_effect_sim'] for r in rr)/len(rr):+.1e} "
                      f"distinct={sum(r['distinct_leader_share'] for r in rr)/len(rr):.3f}")
