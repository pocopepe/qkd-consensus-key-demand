#!/usr/bin/env python3
# Post hoc, not pre-specified. Exponential smoothing at the weights that Stan et al. test (0.1 and 0.3) and at
# 0.5, 0.7, 0.9, scored on the Aptos leader sequences with the scoring loop of v2_analyze.zoo_on_schedule.
# Self-check: the 0.7 column and carry-forward must reproduce the values in V2_RESULTS.json and V3_RESULTS.json.
# usage: posthoc_low_alpha.py [out.json]
import glob
import json
import os
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import v2_analyze as v2
import predictor_zoo_corrected as zoo

ALPHAS = (0.1, 0.3, 0.5, 0.7, 0.9)


def score(path):
    ep = v2.load_epoch(path)
    n = ep["n"]
    sched = max(v2.consecutive_runs(ep), key=len)
    views = min(v2.ZOO_VIEWS, len(sched) - 4)
    preds = [zoo.EWMA(n, a) for a in ALPHAS]
    preds.append(zoo.LastObs(n))
    acc = {p.name: [] for p in preds}
    pis = []
    prev = None
    for t in range(views):
        d = zoo.demand_of(n, sched, t)
        S = set(d)
        if prev is not None and t >= v2.ZOO_WARM:
            pis.append(zoo.pi_of(d, prev))
            for p in preds:
                sc = p.predict(t)
                acc[p.name].append(zoo.coverage(sc, d, len(S)) if sc else 0.0)
        for p in preds:
            p.observe(t, d)
        prev = S
    out = {k: sum(v) / len(v) for k, v in acc.items()}
    out["pi"] = sum(pis) / len(pis)
    return out


def mean(rows, key):
    return sum(r[key] for r in rows) / len(rows)


if __name__ == "__main__":
    out = {"alphas": list(ALPHAS), "note": "post hoc; same scoring loop, budget and warm-up as the pre-specified run"}
    for sample, folder, results in (("first", "raw_v2", "V2_RESULTS.json"), ("second", "raw_v3", "V3_RESULTS.json")):
        files = sorted(glob.glob(os.path.join(HERE, folder, "epoch_*.json")))
        with Pool(8) as pool:
            rows = pool.map(score, files)
        rows = [r for r in rows if r]
        names = [f"ewma{a:g}" for a in ALPHAS] + ["last"]
        res = {"epochs": len(rows), "pi_mean": mean(rows, "pi")}
        for nm in names:
            res[nm] = mean(rows, nm)
            res[nm + "_epochs_above_pi"] = sum(1 for r in rows if r[nm] > r["pi"])
        ref = json.load(open(os.path.join(HERE, results)))["verdicts"]["H6"]
        assert ref["epochs"] == len(rows), (ref["epochs"], len(rows))
        assert abs(ref["ewma0.7"]["mean_coverage"] - res["ewma0.7"]) < 1e-12
        assert abs(ref["last"]["mean_coverage"] - res["last"]) < 1e-12
        assert abs(ref["pi_mean"] - res["pi_mean"]) < 1e-12
        out[sample] = res
        print(sample, json.dumps({k: round(v, 4) if isinstance(v, float) else v for k, v in res.items()}))
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "POSTHOC_LOW_ALPHA.json")
    json.dump(out, open(path, "w"), indent=1)
