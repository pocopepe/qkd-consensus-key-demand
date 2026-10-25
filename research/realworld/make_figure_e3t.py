#!/usr/bin/env python3
# Coordinates for the targeted-suppression figure, from e3/E3T_RESULTS.json. Values in units of 1e-3.
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
ARMS = ("a", "g", "b", "other", "blind")


def table():
    runs = json.load(open(os.path.join(HERE, "e3", "E3T_RESULTS.json")))["runs"]
    out = {}
    for n in (16, 32):
        for arm in ARMS:
            rs = [r for r in runs if r["n"] == n and r["arm"] == arm]
            meas = [1e3 * (r["cor1"] - r["pi_meas"]) for r in rs]
            out[n, arm] = {"meas": statistics.mean(meas),
                           "sd": statistics.stdev(meas),
                           "prop1": statistics.mean(1e3 * (r["cor1"] - r["prop1"]) for r in rs),
                           "blind": statistics.mean(1e3 * (r["cor1"] - r["blind"]) for r in rs),
                           "runs": len(rs)}
    return out


def coords(n, key, t=None):
    if t is None:
        t = table()
    if key == "meas":
        return " ".join(f"({a},{t[n, a]['meas']:.2f}) +- (0,{t[n, a]['sd']:.2f})" for a in ARMS)
    return " ".join(f"({a},{t[n, a][key]:.2f})" for a in ARMS)


if __name__ == "__main__":
    t = table()
    for n in (16, 32):
        for key in ("meas", "prop1", "blind"):
            print(n, key, coords(n, key, t))
