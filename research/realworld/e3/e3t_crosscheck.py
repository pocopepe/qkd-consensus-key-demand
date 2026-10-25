#!/usr/bin/env python3
"""Independent cross-check of E3T's headline D (written after the locked analysis; not a campaign).

Imports nothing from the E1/E3 analysers. From the raw records alone: per view, the multiset of
unordered pairs carrying a Proposal or Vote; pi_t = demand in view t on pairs used in view t-1,
over all demand in view t. Views counted as in the lock: t and t-1 both have messages and are not
timeout views, and t is not the run's final view. D per geography = mean(pi_b, pi_other) -
mean(pi_a, pi_g); reported as the mean over geographies per n, next to E3T_RESULTS.json.

Usage: e3t_crosscheck.py <raw_dir> <results_json>"""
import glob, json, os, sys
from collections import Counter, defaultdict

def run_pi(path):
    d = json.load(open(path))
    views = defaultdict(Counter)
    for view, _, s, t, ty in d["records"]:
        if ty in ("Proposal", "Vote"): views[view][frozenset((s, t))] += 1
    tmo = {int(k) for k in d.get("timeout_views", {})}
    last = max(views)
    pis = [sum(c for p, c in views[v].items() if p in views[v - 1]) / sum(views[v].values())
           for v in views if v != last and v not in tmo and v - 1 in views and v - 1 not in tmo]
    return d["e3_meta"], sum(pis) / len(pis)

def main():
    pi = {}
    for f in sorted(glob.glob(os.path.join(sys.argv[1], "*.json"))):
        m, p = run_pi(f); pi[(m["n"], m["geo_seed"], m["arm"])] = p
    locked = json.load(open(sys.argv[2]))
    for n in sorted({k[0] for k in pi}):
        geos = sorted({k[1] for k in pi if k[0] == n})
        D = [(pi[n, g, "b"] + pi[n, g, "other"]) / 2 - (pi[n, g, "a"] + pi[n, g, "g"]) / 2 for g in geos]
        ours, theirs = sum(D) / len(D), locked["verdicts"][f"n{n}"]["D_measured"]
        print(f"n={n}: D independent {ours:.6f}  locked {theirs:.6f}  diff {ours - theirs:+.1e}")
        assert abs(ours - theirs) < 1e-9, "cross-check disagrees with the locked analysis"
    print("OK")

if __name__ == "__main__":
    main()
