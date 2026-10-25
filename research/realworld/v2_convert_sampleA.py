#!/usr/bin/env python3
"""Convert the v1 (sample A) raw epochs to the v2 on-disk format so
v2_analyze.py can be developed/tested without touching held-out data."""
import ast, glob, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "sampleA_v2fmt"), exist_ok=True)
for p in sorted(glob.glob(os.path.join(HERE, "raw", "epoch_*.json"))):
    r = json.load(open(p)); vs = json.load(open(p.replace("epoch_", "valset_")))
    events = []
    for tx in r["rounds_raw"]:
        evs = tx["events"] if isinstance(tx["events"], list) else ast.literal_eval(tx["events"])
        e = [x for x in evs if x["type"].endswith("NewBlockEvent")][0]
        events.append({"version": tx["version"], "sequence_number": e["sequence_number"], "type": e["type"], "data": e["data"]})
    json.dump({"epoch": r["epoch"], "start_height": int(events[0]["data"]["height"]),
               "validators": vs["validators"], "events": events},
              open(os.path.join(HERE, "sampleA_v2fmt", f"epoch_{r['epoch']}.json"), "w"))
    print(r["epoch"], len(events))
