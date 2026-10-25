#!/usr/bin/env python3
# Post hoc, not pre-specified. The follow-and-keep manager of stock_levels.retain starts with empty pools, and
# every late tag adds one tag to a pool for good. This script asks how much of its late share is that start:
# it scores each quarter of every held-out epoch separately, and it runs the epochs of equal validator count
# end to end as one long sequence. Self-check: the whole-epoch totals must equal RETAIN_RESULTS.json.
# usage: retain_warm.py [out.json]
import json
import os
import sys
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import stock_levels as sl

DELTAS = (1, 5, 50)


def run(L, n, delta):
    # same policy as stock_levels.retain, returning per-view served and demanded tags and the final position
    L = np.asarray(L)
    T = len(L) - 1
    pool = np.zeros((n, n))
    due = {}
    up = np.triu_indices(n, 1)
    served = np.zeros(T)
    total = np.zeros(T)
    position = 0.0
    for t in range(T):
        arrived = due.pop(t, None)
        if arrived is not None:
            pool += arrived
        b = L[t]
        c = L[t + 1]
        d = np.zeros((n, n))
        for h in (b, c):
            d[h, :] += 1
            d[:, h] += 1
        d[b, b] = 0
        d[c, c] = 0
        if b != c:
            d[b, c] = 2
            d[c, b] = 2
        got = np.minimum(d, pool)
        pool -= got
        served[t] = got[up].sum()
        total[t] = d[up].sum()
        position += total[t] - served[t]
        due[t + delta + 1] = due.get(t + delta + 1, 0) + d
    return served, total, position / (n * (n - 1) // 2)


def one(f):
    n, s, L = sl.load(f)
    rows = []
    for delta in DELTAS:
        sv, tot, pos = run(L, n, delta)
        q = len(sv) // 4
        rows.append({"epoch": os.path.basename(f), "n": int(n), "delta": delta, "views": len(sv),
                     "served": float(sv.sum()), "total": float(tot.sum()), "final_position_per_pair": pos,
                     "served_q": [float(sv[i * q:(i + 1) * q].sum()) for i in range(4)],
                     "total_q": [float(tot[i * q:(i + 1) * q].sum()) for i in range(4)]})
    return rows


def long_run(args):
    n, delta, files = args
    L = np.concatenate([sl.load(f)[2] for f in files])
    sv, tot, pos = run(L, n, delta)
    tenth = len(sv) // 10
    return {"n": int(n), "delta": delta, "epochs": len(files), "views": len(sv),
            "late_all": float(1 - sv.sum() / tot.sum()),
            "late_first_tenth": float(1 - sv[:tenth].sum() / tot[:tenth].sum()),
            "late_last_tenth": float(1 - sv[-tenth:].sum() / tot[-tenth:].sum()),
            "final_position_per_pair": pos}


if __name__ == "__main__":
    files = sl.epochs("heldout")
    with Pool(10) as pool:
        rows = [r for rs in pool.map(one, files) for r in rs]
    ref = json.load(open(os.path.join(HERE, "RETAIN_RESULTS.json")))["cells"]
    out = {"note": "post hoc; same policy as stock_levels.retain", "by_quarter": {}, "long": []}
    for delta in DELTAS:
        rs = [r for r in rows if r["delta"] == delta]
        fill = sum(r["served"] for r in rs) / sum(r["total"] for r in rs)
        assert abs(fill - ref[str(delta)]["fill"]) < 1e-12, (delta, fill, ref[str(delta)]["fill"])
        late_q = [1 - sum(r["served_q"][i] for r in rs) / sum(r["total_q"][i] for r in rs) for i in range(4)]
        pos = float(np.mean([r["final_position_per_pair"] for r in rs]))
        tags_per_pair = float(np.mean([r["total"] / (r["n"] * (r["n"] - 1) / 2) for r in rs]))
        out["by_quarter"][str(delta)] = {"late_all": 1 - fill, "late_by_quarter": late_q,
                                         "final_position_per_pair": pos, "tags_per_pair_per_epoch": tags_per_pair}
        print(f"delta {delta:2d}: late {1 - fill:.4f}; by quarter {' '.join(f'{x:.4f}' for x in late_q)}; position at end {pos:.2f} tags/pair; demand {tags_per_pair:.0f} tags/pair")
    byn = {}
    for f in files:
        byn.setdefault(sl.load(f)[0], []).append(f)
    jobs = [(n, delta, fs) for n, fs in sorted(byn.items()) for delta in DELTAS]
    with Pool(min(10, len(jobs))) as pool:
        for r in pool.map(long_run, jobs):
            out["long"].append(r)
            print(f"n={r['n']} delta {r['delta']:2d}: {r['epochs']} epochs end to end, {r['views']} views: late {r['late_all']:.4f}; first tenth {r['late_first_tenth']:.4f}; last tenth {r['late_last_tenth']:.4f}; position {r['final_position_per_pair']:.2f} tags/pair")
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "RETAIN_WARM.json"), "w"), indent=1)
