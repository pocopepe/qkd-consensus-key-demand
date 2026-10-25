#!/usr/bin/env python3
# Can measured QKD links keep up with chained-BFT consensus? A calculation, not a pre-specified test.
#
# Demand: D = 2(n-1) tags per view with votes to the next leader, (n+1)(n-1) with votes broadcast, TAG bits each.
# Supply: a trusted-relay ring whose links give R bit/s. Dynes et al. 2019 (Eq. 1): every pair of N nodes can be
# guaranteed B >= 4R/[N(N-1)], so with demand spread evenly the ring sustains v_max = 2R/(D*TAG) views per second.
# Ceiling: a cut through the ring leaves two links for k(n-k) pairs, so no routing beats v_cap = v_max * 2(n-1)/n.
# Between v_max and v_cap the calculation does not decide.
# Link rates: Cambridge 2.22-2.58 Mbps (Dynes et al. 2019), Tokyo 45 km 304 and 81.7 kbps (Sasaki et al. 2011),
# and 1.8 kbps, the highest four-month link average of the Vienna network of commercial systems (Hubel et al. 2023).
# Block refill: if key reaches a pair once every T seconds, the pair must hold T seconds of its demand, on average
# D*v*T / (n(n-1)/2) tags with votes to the next leader.
# usage: feasibility.py [out.json]
import glob
import json
import os
import statistics
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RW = os.path.dirname(HERE)
RATES = {"Cambridge 10.6 km (2.58 Mbps)": 2.58e6, "Cambridge 5.0 km (2.22 Mbps)": 2.22e6,
         "Tokyo 45 km (304 kbps)": 304e3, "Tokyo 45 km (81.7 kbps)": 81.7e3,
         "Vienna commercial (1.8 kbps)": 1.8e3}
TAGS = (64, 128, 256)
NS = (4, 7, 16, 32, 64, 84, 100)


def demand(n, design):
    if design == "unicast":
        return 2 * (n - 1)
    return (n + 1) * (n - 1)


def vmax(R, n, design, tag):
    return 2 * R / (demand(n, design) * tag)


def bmax(R, n):
    if n % 2 == 0:
        return 8 * R / (n * n)
    return 8 * R / (n * n - 1)


def vcap(R, n, design, tag):
    return bmax(R, n) * n * (n - 1) / (2 * demand(n, design) * tag)


def selfcheck():
    for n in range(3, 40):
        worst = max(k * (n - k) for k in range(1, n))
        assert abs(bmax(1, n) - 2 / worst) < 1e-12
        assert bmax(1, n) >= 4 / (n * (n - 1)) - 1e-15
    assert abs(vcap(1, 64, "broadcast", 128) / vmax(1, 64, "broadcast", 128) - 2 * 63 / 64) < 1e-12


def aptos_round_rate():
    rates = []
    for f in sorted(glob.glob(os.path.join(RW, "raw_v3", "epoch_*.json"))):
        ev = sorted(json.load(open(f))["events"], key=lambda e: int(e["data"]["height"]))
        t0 = int(ev[0]["data"]["time_microseconds"])
        t1 = int(ev[-1]["data"]["time_microseconds"])
        r0 = int(ev[0]["data"]["round"])
        r1 = int(ev[-1]["data"]["round"])
        if t1 > t0:
            rates.append((r1 - r0) / ((t1 - t0) / 1e6))
    return rates


def stake_skew():
    # demand of pair {u, v} under leaders drawn by stake is proportional to s_u + s_v; heaviest pair over the mean pair
    out = []
    for f in sorted(glob.glob(os.path.join(RW, "raw_v2", "epoch_*.json")) + glob.glob(os.path.join(RW, "raw_v3", "epoch_*.json"))):
        power = sorted((v["voting_power"] for v in json.load(open(f))["validators"]), reverse=True)
        n = len(power)
        out.append((power[0] + power[1]) / sum(power) * n / 2)
    return out


def parse_time(t):
    if len(t) > 27:
        return datetime.fromisoformat(t[:26].rstrip("Z"))
    return datetime.fromisoformat(t.replace("Z", ""))


def cosmos_block_rate():
    rates = []
    for f in sorted(glob.glob(os.path.join(RW, "cosmos", "raw_bulk", "chunk_*.json"))):
        blocks = json.load(open(f))["blocks"]
        dt = (parse_time(blocks[-1]["t"]) - parse_time(blocks[0]["t"])).total_seconds()
        if dt > 0:
            rates.append((len(blocks) - 1) / dt)
    return rates


def summary(rates, label):
    out = {label: len(rates), "mean": statistics.mean(rates) if rates else None}
    if label == "epochs":
        out["min"] = min(rates) if rates else None
        out["max"] = max(rates) if rates else None
    return out


if __name__ == "__main__":
    selfcheck()
    ap = aptos_round_rate()
    co = cosmos_block_rate()
    obs = {"aptos_rounds_per_s": summary(ap, "epochs"), "cosmos_blocks_per_s": summary(co, "windows")}
    table = []
    for name, R in RATES.items():
        for n in NS:
            for tag in TAGS:
                table.append({"link": name, "R_bps": R, "n": n, "tag_bits": tag,
                              "vmax_unicast": vmax(R, n, "unicast", tag), "vmax_broadcast": vmax(R, n, "broadcast", tag),
                              "vcap_unicast": vcap(R, n, "unicast", tag), "vcap_broadcast": vcap(R, n, "broadcast", tag),
                              "U_unicast": n - 3, "D_unicast": demand(n, "unicast"), "D_broadcast": demand(n, "broadcast")})
    v = obs["aptos_rounds_per_s"]["mean"]
    refill = []
    for T in (30, 60, 90):
        for n in (16, 84, 100):
            refill.append({"period_s": T, "n": n, "views_per_s": v,
                           "tags_per_pair": demand(n, "unicast") * v * T / (n * (n - 1) / 2)})
    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "QKD_FEASIBILITY.json")
    skew = stake_skew()
    json.dump({"observed_view_rates": obs, "table": table, "block_refill": refill,
               "stake_skew": {"epochs": len(skew), "mean": statistics.mean(skew), "min": min(skew), "max": max(skew)}},
              open(out_path, "w"), indent=1)
    print("observed:", json.dumps(obs))
    print(f"{'link':32} {'n':>4} {'tag':>4} {'unicast max/cap':>18} {'broadcast max/cap':>20}  (views per second)")
    for r in table:
        if r["tag_bits"] == 128:
            print(f"{r['link']:32} {r['n']:4d} {r['tag_bits']:4d} {r['vmax_unicast']:8.2f}/{r['vcap_unicast']:<9.2f} {r['vmax_broadcast']:9.3f}/{r['vcap_broadcast']:<9.3f}")
