#!/usr/bin/env python3
"""Collapse identical (view,src,dst) Proposal records: relab re-dispatches an
early proposal through the same handler, so the frozen log line fires twice for
one network message. Pre-registered for E3c (found post hoc in E3)."""
import glob, json, os, sys
src, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True); tot = dup = 0
for p in sorted(glob.glob(os.path.join(src, "*.json"))):
    d = json.load(open(p)); seen = set(); out = []
    for r in d["records"]:
        k = tuple(r)
        if r[4] == "Proposal" and k in seen:
            dup += 1; continue
        seen.add(k); out.append(r)
    tot += len(d["records"]); d["records"] = out
    json.dump(d, open(os.path.join(dst, os.path.basename(p)), "w"))
print(f"{dup} duplicate proposal records removed of {tot}")
