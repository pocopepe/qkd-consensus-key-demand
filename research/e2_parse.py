#!/usr/bin/env python3
"""Parse relab/hotstuff E2 instrumentation into per-view pairwise demand.

Instrumentation emitted by the logging-only patch in
research/results/e2_smoke/instrumentation.diff:

    E2 SEND_PROPOSE view=V from=F to=ALL     leader F broadcasts in view V
    E2 RECV_PROPOSE view=V from=F to=T       replica T received F's proposal
    E2 SEND_VOTE    view=V from=F to=L       replica F votes to leader L
    E2 LOCAL_TIMEOUT view=V id=R             replica R timed out in view V

Proposal edges are taken from RECV_PROPOSE, not from SEND_PROPOSE, so the
proposal star is *measured* rather than assumed to reach everyone. Vote edges
come from SEND_VOTE with the self-vote dropped, since a replica voting for
itself consumes no link key.

The vote in view V is addressed to the leader of view V+1, which is what makes
the support of view V the union of two stars.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

RECV = re.compile(r"E2 RECV_PROPOSE view=(\d+) from=(\d+) to=(\d+)")
SVOTE = re.compile(r"E2 SEND_VOTE view=(\d+) from=(\d+) to=(\d+)")
SPROP = re.compile(r"E2 SEND_PROPOSE view=(\d+) from=(\d+) to=ALL")
TMO = re.compile(r"E2 LOCAL_TIMEOUT view=(\d+) id=(\d+)")


def parse(path):
    recs, timeouts, proposers = [], defaultdict(set), {}
    counts = defaultdict(int)
    with open(path, errors="ignore") as f:
        for line in f:
            m = RECV.search(line)
            if m:
                v, s, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                counts["recv_propose"] += 1
                if s != d:
                    recs.append((v, 0, s, d, "Proposal"))
                continue
            m = SVOTE.search(line)
            if m:
                v, s, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                counts["send_vote"] += 1
                if s != d:
                    recs.append((v, 0, s, d, "Vote"))
                continue
            m = SPROP.search(line)
            if m:
                counts["send_propose"] += 1
                proposers[int(m.group(1))] = int(m.group(2))
                continue
            m = TMO.search(line)
            if m:
                counts["local_timeout"] += 1
                timeouts[int(m.group(1))].add(int(m.group(2)))
    return recs, {k: sorted(v) for k, v in timeouts.items()}, proposers, dict(counts)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/e2_smoke.log"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    out = sys.argv[3] if len(sys.argv) > 3 else "research/results/e2_smoke/raw/smoke.json"
    recs, tmo, props, counts = parse(src)
    print("event counts:", counts)
    print(f"records: {len(recs)}")
    views = sorted({r[0] for r in recs})
    print(f"views with demand: {len(views)}  range {views[0] if views else '-'}..{views[-1] if views else '-'}")
    print(f"views with a local timeout: {len(tmo)}")
    print(f"distinct proposers observed: {sorted(set(props.values()))}")
    seq = [props.get(v) for v in views[:16]]
    print(f"leader sequence (first 16 views): {seq}")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"n_validators": n, "records": recs,
               "timeout_views": {str(k): v for k, v in tmo.items()},
               "proposers": {str(k): v for k, v in props.items()},
               "counts": counts}, open(out, "w"))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
