#!/usr/bin/env python3
"""Parse libhotstuff protocol logs into per-view pairwise demand.

Instrumentation: libhotstuff built with -DHOTSTUFF_PROTO_LOG=ON emits, on each
replica, a line per delivered consensus message naming the sending replica id:

    [hotstuff proto] got <proposal rid=R blk=H>
    [hotstuff proto] got <vote rid=R blk=H>

and, on the proposer,

    [hotstuff proto] propose <block id=H height=N parent=... qc_ref=...>

which supplies the block-id -> height map used to assign messages to views.

No consensus code was modified; the build flag only enables logging.

A note that turned out to matter: libhotstuff's "rr" pacemaker is a view-change
mechanism, not a per-view leader rotation. It rotates on impeachment and then
stops at the new proposer, so in steady state there is a single stable hub.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

GOT = re.compile(r"got <(proposal|vote) rid=(\d+) blk=([0-9a-f]+)>")
PROPOSE = re.compile(r"propose <block id=([0-9a-f]+) height=(\d+)")
ROTATE = re.compile(r"Pacemaker: (rotate to|stop rotation at) (\d+)")


def parse(logdir, n):
    blk_height = {}
    rotations = []
    raw = []
    for i in range(n):
        p = os.path.join(logdir, f"log{i}")
        if not os.path.exists(p):
            continue
        with open(p, errors="ignore") as f:
            for line in f:
                mp = PROPOSE.search(line)
                if mp:
                    blk_height[mp.group(1)] = int(mp.group(2))
                    continue
                mr = ROTATE.search(line)
                if mr:
                    rotations.append((i, mr.group(1), int(mr.group(2))))
                    continue
                mg = GOT.search(line)
                if mg:
                    raw.append((int(mg.group(2)), i, mg.group(1), mg.group(3)))
    recs = []
    unmapped = 0
    for sender, receiver, typ, blk in raw:
        h = blk_height.get(blk)
        if h is None:
            unmapped += 1
            continue
        if sender == receiver:
            continue                      # self-delivery consumes no link key
        recs.append((h, 0, sender, receiver,
                     "Proposal" if typ == "proposal" else "Vote"))
    return recs, unmapped, rotations


def main():
    logdir = sys.argv[1] if len(sys.argv) > 1 else "ext/libhotstuff"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    out = sys.argv[3] if len(sys.argv) > 3 else "research/results/e1/raw/hotstuff_trace.json"
    recs, unmapped, rot = parse(logdir, n)
    print(f"parsed {len(recs)} inter-replica consensus messages "
          f"({unmapped} unmapped block ids)")
    by = defaultdict(int)
    for _, _, _, _, t in recs:
        by[t] += 1
    print("by type:", dict(by))
    hs = sorted({h for h, _, _, _, _ in recs})
    print(f"heights: {min(hs) if hs else '-'}..{max(hs) if hs else '-'} "
          f"({len(hs)} distinct)")
    props = defaultdict(int)
    for _, _, s, _, t in recs:
        if t == "Proposal":
            props[s] += 1
    print("proposals sent by replica:", dict(props))
    print(f"pacemaker events: {len(rot)}", rot[:6])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"n_validators": n, "records": recs,
               "rotations": rot, "unmapped": unmapped}, open(out, "w"))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
