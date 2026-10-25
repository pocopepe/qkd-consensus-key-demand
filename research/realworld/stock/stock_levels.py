#!/usr/bin/env python3
# Standing key stock for chained rotation (votes go to the next leader).
# Each validator pair keeps a pool of B tags. Tags used in view t are reordered at
# the end of that view and arrive delta views later, so they are back for view
# t + delta + 1. A tag is served on time if the pool is not empty when needed.
#
# usage: stock_levels.py dev|heldout <out.json>   (dev = the 4 epochs used while writing this)
#        stock_levels.py forecast <out.json>      (carry-forward manager under the same delays)
#        stock_levels.py retain <out.json>        (manager that follows demand and keeps what it ordered)
#        stock_levels.py views <out.json>         (same policies scored per view: does a quorum form without waiting?)
import glob
import json
import math
import os
import sys
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RW = os.path.dirname(HERE)
sys.path.insert(0, RW)

DELTAS = (1, 2, 5, 10, 20, 50)
UNIFORM = tuple(range(1, 21))
QS = (0.9, 0.95, 0.98, 0.99, 0.995, 0.998, 0.999, 0.9995, 0.9999, 0.99999)
TARGETS = (0.99, 0.999)
DEV = ("17270", "17279", "17280", "17283")
MODEL_VIEWS = 60000
MODEL_SEED = 20261010
BOOT = 10000
BOOT_SEED = 20261010


def incidence(L, n):
    # a[t, u] = 1 if u leads view t, plus 1 if u leads view t + 1
    T = len(L) - 1
    a = np.zeros((T, n), np.int32)
    i = np.arange(T)
    np.add.at(a, (i, L[:-1]), 1)
    np.add.at(a, (i, L[1:]), 1)
    return a


def fill(L, n, B, delta):
    # tags served on time and tags demanded, for leader sequence L and pool depths B (n x n)
    L = np.asarray(L)
    a = incidence(L, n)
    T = a.shape[0]
    i = np.arange(T)
    cum = np.vstack([np.zeros((1, n), np.int64), np.cumsum(a, 0)])
    W = cum[i] - cum[np.maximum(i - delta, 0)]
    b = L[:-1]
    c = L[1:]
    served = 0
    total = 0
    for hub, other in ((b, None), (c, b)):
        d = a[i, hub][:, None] + a
        onhand = B[hub] - W[i, hub][:, None] - W
        m = np.ones((T, n), bool)
        m[i, hub] = False
        if other is not None:
            m[i, other] = False
            m[hub == other] = False
        served += int(np.minimum(d, np.maximum(onhand, 0))[m].sum())
        total += int(d[m].sum())
    return served, total


def forecast(L, n, delta):
    # carry-forward: arm the pairs of view j with enough key for anything, usable in view j + delta + 1 only
    L = np.asarray(L)
    a = incidence(L, n)
    T = a.shape[0]
    i = np.arange(T)
    lag = delta + 1
    b = L[:-1]
    c = L[1:]
    served = 0
    total = 0
    for hub, other in ((b, None), (c, b)):
        d = a[i, hub][:, None] + a
        j = i - lag
        ok = j >= 0
        inS = np.zeros((T, n), bool)
        inS[ok] = (a[j[ok], hub[ok]] > 0)[:, None] | (a[j[ok]] > 0)
        m = np.ones((T, n), bool)
        m[i, hub] = False
        m[~ok] = False
        if other is not None:
            m[i, other] = False
            m[hub == other] = False
        served += int((d * inS)[m].sum())
        total += int(d[m].sum())
    return served, total


def retain(L, n, delta):
    # follow demand and keep it: pools start empty, every tag used is reordered, nothing is released
    L = np.asarray(L)
    T = len(L) - 1
    pool = np.zeros((n, n))
    due = {}
    served = 0
    total = 0
    standing = 0.0
    intransit = 0.0
    up = np.triu_indices(n, 1)
    for t in range(T):
        arrived = due.pop(t, None)
        if arrived is not None:
            pool += arrived
            intransit -= arrived[up].sum()
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
        served += got[up].sum()
        total += d[up].sum()
        due[t + delta + 1] = due.get(t + delta + 1, 0) + d
        intransit += d[up].sum()
        standing += pool[up].sum() + intransit
    pairs = n * (n - 1) // 2
    return int(served), int(total), standing / T / pairs


def star_rows(b, c, n):
    # tags of one view as two rows: proposals b -> all and votes all -> c. Row c leaves out the pair with b.
    xb = np.ones(n, np.int64)
    xb[b] = 0
    xc = np.ones(n, np.int64)
    xc[c] = 0
    if b == c:
        return 2 * xb, None
    xb[c] = 2
    xc[b] = 0
    return xb, xc


def run_views(L, n, s, delta, B=None):
    # B given: base stock of depth B on every pair. B None: follow demand and keep it, pools start empty.
    # A validator counts as on time in a view if its proposal and its vote were both served; the proposal takes
    # the first tag of a pair. Counts are returned for all views and for the second half of the sequence.
    L = np.asarray(L)
    T = len(L) - 1
    half = T // 2
    f = (n - 1) // 3
    keep = B is None
    if keep:
        pool = np.zeros((n, n), np.int64)
    else:
        pool = B.astype(np.int64).copy()
    held = 0
    due = {}
    out = {"served": [0, 0], "total": [0, 0], "views": [0, 0], "q_stake": [0, 0], "q_count": [0, 0], "standing": [0.0, 0.0]}
    for t in range(T):
        back = due.pop(t, None)
        if back is not None:
            for h, x in back:
                pool[h, :] += x
                pool[:, h] += x
                held += int(x.sum())
        b = int(L[t])
        c = int(L[t + 1])
        xb, xc = star_rows(b, c, n)
        gb = np.minimum(xb, np.maximum(pool[b], 0))
        take = gb if keep else xb
        pool[b, :] -= take
        pool[:, b] -= take
        served = int(gb.sum())
        total = int(xb.sum())
        if xc is None:
            ok = gb >= 2
            ok[b] = True
            due[t + delta + 1] = [(b, xb)]
        else:
            gc = np.minimum(xc, np.maximum(pool[c], 0))
            take = gc if keep else xc
            pool[c, :] -= take
            pool[:, c] -= take
            served += int(gc.sum())
            total += int(xc.sum())
            ok = (gb >= 1) & (gc >= 1)
            ok[b] = gb[c] >= 2
            ok[c] = gb[c] >= 1
            due[t + delta + 1] = [(b, xb), (c, xc)]
        held -= served
        qs = s[ok].sum() > 2 / 3
        qc = ok.sum() >= 2 * f + 1
        for k in range(2):
            if k == 1 and t < half:
                continue
            out["served"][k] += served
            out["total"][k] += total
            out["views"][k] += 1
            out["q_stake"][k] += int(qs)
            out["q_count"][k] += int(qc)
            out["standing"][k] += held
    out["max_depth"] = int(pool.max())
    return out


def stake_levels(s, delta, q):
    # depth per pair = q-quantile of its demand over delta + 1 views with leaders drawn by stake
    n = len(s)
    p = np.clip(s[:, None] + s[None, :], 0, 1)
    B = np.zeros((n, n), np.int64)
    ks = np.arange(delta + 1)
    logc = np.array([math.lgamma(delta + 1) - math.lgamma(k + 1) - math.lgamma(delta - k + 1) for k in ks])
    for u in range(n):
        for v in range(u + 1, n):
            pp = p[u, v]
            if pp <= 0:
                continue
            if pp < 1:
                mid = np.exp(logc + ks * math.log(pp) + (delta - ks) * math.log1p(-pp))
            else:
                mid = (ks == delta).astype(float)
            ends = np.array([(1 - pp) ** 2, 2 * pp * (1 - pp), pp ** 2])
            pmf = np.zeros(2 * delta + 3)
            for k, w in enumerate(mid):
                pmf[2 * k:2 * k + 3] += w * ends
            B[u, v] = int(np.searchsorted(np.cumsum(pmf), q - 1e-12))
            B[v, u] = B[u, v]
    return B


def load(path):
    import v2_analyze as v2a
    ep = v2a.load_epoch(path)
    idx = ep["addr_to_idx"]
    s = np.array(ep["share"], float)
    s = s / s.sum()
    L = [idx.get(e["data"]["proposer"]) for e in ep["events"]]
    L = [x for x in L if x is not None]
    return ep["n"], s, np.array(L)


def epochs(which):
    files = sorted(glob.glob(os.path.join(RW, "raw_v2", "epoch_*.json")) + glob.glob(os.path.join(RW, "raw_v3", "epoch_*.json")))
    out = []
    for f in files:
        is_dev = os.path.basename(f)[6:11] in DEV and "raw_v3" in f
        if is_dev == (which == "dev"):
            out.append(f)
    return out


def bootstrap(served, total, rng):
    k = rng.integers(0, len(served), size=(BOOT, len(served)))
    bs = served[k].sum(1) / total[k].sum(1)
    return [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))]


def one_epoch(f):
    n, s, L = load(f)
    pairs = n * (n - 1) // 2
    name = os.path.basename(f)
    Lm = np.random.default_rng([MODEL_SEED, int(name[6:11])]).choice(n, size=MODEL_VIEWS + 1, p=s)
    Lr = np.arange(len(L)) % n
    rows = []
    for delta in DELTAS:
        rules = [("uniform", B, np.full((n, n), B, np.int64)) for B in UNIFORM]
        rules += [("stake", q, stake_levels(s, delta, q)) for q in QS]
        for kind, par, B in rules:
            sv, tot = fill(L, n, B, delta)
            ms, mt = fill(Lm, n, B, delta)
            row = {"epoch": name, "n": n, "stock_per_pair": int(B[np.triu_indices(n, 1)].sum()) / pairs,
                   "served": sv, "total": tot, "model_served": ms, "model_total": mt}
            if kind == "uniform":
                row["rr_served"], row["rr_total"] = fill(Lr, n, B, delta)
            rows.append((f"{delta}|{kind}|{par}", delta, kind, par, row))
    return rows


def main(which, out):
    files = epochs(which)
    res = {"which": which, "epochs": [os.path.basename(f) for f in files], "cells": {}}
    with Pool(min(10, len(files))) as pool:
        for rows in pool.map(one_epoch, files):
            for key, delta, kind, par, row in rows:
                cell = res["cells"].setdefault(key, {"delta": delta, "rule": kind, "param": par, "per_epoch": []})
                cell["per_epoch"].append(row)
    rng = np.random.default_rng(BOOT_SEED)
    for cell in res["cells"].values():
        pe = cell["per_epoch"]
        sv = np.array([r["served"] for r in pe], float)
        tt = np.array([r["total"] for r in pe], float)
        cell["fill"] = float(sv.sum() / tt.sum())
        cell["model_fill"] = sum(r["model_served"] for r in pe) / sum(r["model_total"] for r in pe)
        cell["stock_per_pair"] = float(np.mean([r["stock_per_pair"] for r in pe]))
        if "rr_served" in pe[0]:
            cell["rr_fill"] = sum(r["rr_served"] for r in pe) / sum(r["rr_total"] for r in pe)
        if len(pe) >= 5:
            cell["ci"] = bootstrap(sv, tt, rng)
    cells = list(res["cells"].values())
    res["max_abs_model_gap"] = max(abs(c["fill"] - c["model_fill"]) for c in cells)
    res["need"] = {}
    for delta in DELTAS:
        for target in TARGETS:
            for rule in ("uniform", "stake"):
                ok = [c for c in cells if c["delta"] == delta and c["rule"] == rule and c["fill"] >= target]
                best = min(ok, key=lambda c: c["stock_per_pair"]) if ok else None
                if best is None:
                    res["need"][f"{delta}|{target}|{rule}"] = None
                else:
                    res["need"][f"{delta}|{target}|{rule}"] = {"param": best["param"], "stock_per_pair": best["stock_per_pair"],
                                                              "fill": best["fill"], "model_fill": best["model_fill"], "ci": best.get("ci")}
            ok = [c for c in cells if c["delta"] == delta and c["rule"] == "uniform" and c["rr_fill"] >= 1]
            res["need"][f"{delta}|rr"] = min(c["param"] for c in ok) if ok else None
    json.dump(res, open(out, "w"), indent=1)
    tags = sum(r["total"] for r in cells[0]["per_epoch"])
    print(f"{len(files)} epochs, {tags} tags demanded; largest |measured - model| over {len(cells)} cells: {res['max_abs_model_gap']:.4f}")
    for delta in DELTAS:
        line = f"lead {delta:2d}  round-robin needs {res['need'][f'{delta}|rr']}"
        for target in TARGETS:
            u = res["need"][f"{delta}|{target}|uniform"]
            k = res["need"][f"{delta}|{target}|stake"]
            line += f"   {target}: uniform " + (f"{u['stock_per_pair']:.0f} ({u['fill']:.4f})" if u else "-")
            line += " stake " + (f"{k['stock_per_pair']:.2f} ({k['fill']:.4f}, q={k['param']})" if k else "-")
        print(line)


def forecast_main(out):
    res = {"epochs": [], "cells": {}}
    for f in epochs("heldout"):
        n, s, L = load(f)
        name = os.path.basename(f)
        res["epochs"].append(name)
        Lr = np.arange(len(L)) % n
        for delta in (0,) + DELTAS:
            sv, tot = forecast(L, n, delta)
            rs, rt = forecast(Lr, n, delta)
            cell = res["cells"].setdefault(str(delta), {"delta": delta, "per_epoch": []})
            cell["per_epoch"].append({"epoch": name, "n": n, "served": sv, "total": tot, "rr_served": rs, "rr_total": rt,
                                      "armed_per_pair": 2 * (2 * n - 3) / (n * (n - 1) // 2)})
    rng = np.random.default_rng(BOOT_SEED)
    for c in res["cells"].values():
        pe = c["per_epoch"]
        sv = np.array([r["served"] for r in pe], float)
        tt = np.array([r["total"] for r in pe], float)
        c["fill"] = float(sv.sum() / tt.sum())
        c["rr_fill"] = sum(r["rr_served"] for r in pe) / sum(r["rr_total"] for r in pe)
        c["armed_per_pair"] = float(np.mean([r["armed_per_pair"] for r in pe]))
        c["ci"] = bootstrap(sv, tt, rng)
        print(f"carry-forward, lead {c['delta']:2d}: on time {c['fill']:.4f} [{c['ci'][0]:.4f}, {c['ci'][1]:.4f}]  round-robin {c['rr_fill']:.4f}  armed {c['armed_per_pair']:.3f} tags/pair")
    json.dump(res, open(out, "w"), indent=1)


def retain_one(f):
    n, s, L = load(f)
    name = os.path.basename(f)
    rows = []
    for delta in DELTAS:
        sv, tot, st = retain(L, n, delta)
        rows.append({"epoch": name, "delta": delta, "served": sv, "total": tot, "standing_per_pair": st})
    return rows


def retain_main(out):
    files = epochs("heldout")
    res = {"epochs": [os.path.basename(f) for f in files], "cells": {}}
    with Pool(min(10, len(files))) as pool:
        for rows in pool.map(retain_one, files):
            for r in rows:
                cell = res["cells"].setdefault(str(r["delta"]), {"delta": r["delta"], "per_epoch": []})
                cell["per_epoch"].append(r)
    rng = np.random.default_rng(BOOT_SEED)
    for c in res["cells"].values():
        pe = c["per_epoch"]
        sv = np.array([r["served"] for r in pe], float)
        tt = np.array([r["total"] for r in pe], float)
        c["fill"] = float(sv.sum() / tt.sum())
        c["standing_per_pair"] = float(np.mean([r["standing_per_pair"] for r in pe]))
        c["ci"] = bootstrap(sv, tt, rng)
        print(f"retained carry-forward, lead {c['delta']:2d}: on time {c['fill']:.4f} [{c['ci'][0]:.4f}, {c['ci'][1]:.4f}]  standing {c['standing_per_pair']:.3f} tags/pair")
    json.dump(res, open(out, "w"), indent=1)


VIEW_DELTAS = DELTAS + (100,)
VIEW_UNIFORM = (1, 2, 3, 4, 5, 6, 8, 10, 12, 14, 16, 20, 24)


def views_one(f):
    n, s, L = load(f)
    name = os.path.basename(f)
    rows = []
    for delta in VIEW_DELTAS:
        rules = [("uniform", B, np.full((n, n), B, np.int64)) for B in VIEW_UNIFORM]
        rules += [("stake", q, stake_levels(s, delta, q)) for q in (0.99, 0.998, 0.9999)]
        rules.append(("keep", 0, None))
        for kind, par, B in rules:
            r = run_views(L, n, s, delta, B)
            r["epoch"] = name
            r["n"] = n
            rows.append((f"{delta}|{kind}|{par}", delta, kind, par, r))
    return rows


def views_main(out):
    files = epochs("heldout")
    res = {"epochs": [os.path.basename(f) for f in files], "cells": {}}
    with Pool(min(10, len(files))) as pool:
        for rows in pool.map(views_one, files):
            for key, delta, kind, par, r in rows:
                cell = res["cells"].setdefault(key, {"delta": delta, "rule": kind, "param": par, "per_epoch": []})
                cell["per_epoch"].append(r)
    for key, cell in res["cells"].items():
        pe = cell["per_epoch"]
        for k, label in ((0, "all"), (1, "warm")):
            views = sum(r["views"][k] for r in pe)
            pairs = np.array([r["n"] * (r["n"] - 1) // 2 for r in pe])
            cell[label] = {"fill": sum(r["served"][k] for r in pe) / sum(r["total"][k] for r in pe),
                           "quorum_stake": sum(r["q_stake"][k] for r in pe) / views,
                           "quorum_count": sum(r["q_count"][k] for r in pe) / views,
                           "standing_per_pair": float(np.mean([r["standing"][k] / r["views"][k] for r in pe] / pairs)),
                           "views": views, "tags": sum(r["total"][k] for r in pe)}
        cell["max_depth"] = max(r["max_depth"] for r in pe)
    json.dump(res, open(out, "w"), indent=1)
    for delta in VIEW_DELTAS:
        k = res["cells"][f"{delta}|keep|0"]
        print(f"lead {delta:3d}  keep: all {k['all']['fill']:.4f} q {k['all']['quorum_stake']:.4f} | warm {k['warm']['fill']:.4f} q {k['warm']['quorum_stake']:.4f} standing {k['warm']['standing_per_pair']:.2f} max {k['max_depth']}")
        line = "          uniform quorum share by depth:"
        for B in VIEW_UNIFORM:
            line += f" {B}:{res['cells'][f'{delta}|uniform|{B}']['all']['quorum_stake']:.4f}"
        print(line)


def slow_fill(L, n, B, delta, notice=0):
    # plain simulation with an order queue, used to check fill()
    pool = B.copy()
    due = {}
    served = 0
    total = 0
    T = len(L) - 1

    def demand(t):
        out = {}
        for h in {L[t], L[t + 1]}:
            for v in range(n):
                if v != h:
                    out[tuple(sorted((h, v)))] = 0
        for (u, v) in out:
            out[(u, v)] = int(L[t] in (u, v)) + int(L[t + 1] in (u, v))
        return out

    if notice:
        for i in range(T):
            for pr, k in demand(i).items():
                due.setdefault(i - notice + delta + 1, {}).setdefault(pr, 0)
                due[i - notice + delta + 1][pr] += k
    for t in range(T):
        for at in [x for x in due if x <= t]:
            for (u, v), k in due.pop(at).items():
                pool[u, v] += k
                pool[v, u] += k
        for (u, v), k in demand(t).items():
            served += int(min(k, max(pool[u, v], 0)))
            total += k
            pool[u, v] -= k
            pool[v, u] -= k
            if not notice:
                due.setdefault(t + delta + 1, {})[(u, v)] = k
    return served, total


def selfcheck():
    rng = np.random.default_rng(1)
    n = 9
    s = rng.dirichlet(np.ones(n))
    L = rng.choice(n, size=400, p=s)
    for delta in (1, 3, 7):
        B = stake_levels(s, delta, 0.95)
        assert slow_fill(L, n, B, delta) == fill(L, n, B, delta)
    assert fill(np.arange(200) % 7, 7, np.full((7, 7), 4), 1) == (199 * 12, 199 * 12)
    for n2 in (5, 12):
        Lr = np.arange(40 * n2) % n2
        B4 = np.full((n2, n2), 4)
        for d in range(1, n2):
            sv, tot = fill(Lr, n2, B4, d)
            assert sv == tot
        sv, tot = fill(Lr, n2, B4, n2)
        assert sv < tot
    # advance notice of nu views is the same as a lead time shorter by nu
    L = rng.choice(n, size=400, p=s)
    delta, nu = 6, 4
    B = stake_levels(s, delta - nu, 0.95)
    assert slow_fill(L, n, B, delta, notice=nu) == fill(L, n, B, delta - nu)
    sv, tot, st = retain(np.arange(120) % 6, 6, 1)
    assert 0 < tot - sv < 0.05 * tot and 1.5 < st < 2.5
    # the per-view simulation serves the same tags as fill()
    L = rng.choice(n, size=500, p=s)
    for delta in (1, 4):
        B = stake_levels(s, delta, 0.9)
        r = run_views(L, n, s, delta, B)
        assert (r["served"][0], r["total"][0]) == fill(L, n, B, delta)
        assert r["q_stake"][0] <= r["views"][0] and r["views"][1] == r["views"][0] - r["views"][0] // 2
    r = run_views(np.arange(300) % 7, 7, np.full(7, 1 / 7), 2, np.full((7, 7), 4))
    assert r["served"][0] == r["total"][0] and r["q_stake"][0] == r["views"][0]
    r = run_views(np.arange(300) % 7, 7, np.full(7, 1 / 7), 2, np.full((7, 7), 1))
    assert r["q_stake"][0] < r["views"][0]
    # carry-forward with no delay serves exactly the schedule's demand-weighted persistence
    L = rng.choice(n, size=600, p=s)
    a = incidence(L, n)
    num = 0
    den = 0
    for t in range(1, a.shape[0]):
        for u in range(n):
            for v in range(u + 1, n):
                d = a[t, u] + a[t, v]
                den += d
                num += d * ((a[t - 1, u] + a[t - 1, v]) > 0)
    assert forecast(L, n, 0) == (num, den)


if __name__ == "__main__":
    selfcheck()
    mode, out = sys.argv[1], sys.argv[2]
    if mode == "forecast":
        forecast_main(out)
    elif mode == "retain":
        retain_main(out)
    elif mode == "views":
        views_main(out)
    else:
        main(mode, out)
