#!/usr/bin/env python3
"""Parse CometBFT debug logs into per-view pairwise demand.

Instrumentation point: the p2p layer logs every inbound message as

    D[...] Received bytes  module=p2p peer=<nodeid>@<addr> chID=<n> msgBytes=<hex>

on the *receiving* node, naming the *sending* peer. That is the logical
consensus-message layer required by the trace model: one log line per delivered
consensus message, attributed to a validator pair, with the protobuf payload
available for typing and for extracting (height, round).

No consensus code was modified. Only the log level was raised.

Channel map (CometBFT p2p):
    32 StateChannel        NewRoundStep, NewValidBlock
    33 DataChannel         Proposal, ProposalPOL, BlockPart
    34 VoteChannel         Vote
    35 VoteSetBitsChannel  HasVote, VoteSetMaj23, VoteSetBits
Other channels (0 PEX, 48 mempool, 64 blocksync, 96 evidence) are not consensus
and are excluded by the trace model.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

CONSENSUS_CHANNELS = {32, 33, 34, 35}

# tmcons.Message oneof field number -> logical type
ONEOF = {1: "NewRoundStep", 2: "NewValidBlock", 3: "Proposal",
         4: "ProposalPOL", 5: "BlockPart", 6: "Vote", 7: "HasVote",
         8: "VoteSetMaj23", 9: "VoteSetBits"}

# per the trace model
D_CORE = {"Proposal", "Vote"}
D_ALL = set(ONEOF.values())

LINE = re.compile(
    r"Received bytes.*?peer=([0-9a-f]{40})@\S*\s+chID=(\d+)\s+msgBytes=([0-9A-F]*)")


def read_varint(b, i):
    shift = 0
    val = 0
    while i < len(b):
        x = b[i]
        val |= (x & 0x7F) << shift
        i += 1
        if not (x & 0x80):
            return val, i
        shift += 7
    return None, i


def scan_fields(b, start, end):
    """Parse a protobuf message into {field_number: value} for varint fields,
    recording lengths for LEN fields. Absent fields simply do not appear.

    This is the correction that made the parser work: protobuf omits fields at
    their default value, so round == 0 is not on the wire at all. The first
    version required the round tag to be present and discarded every message in
    round 0 -- which is almost all of them."""
    out = {}
    i = start
    while i < end:
        tag, i = read_varint(b, i)
        if tag is None:
            break
        fn, wt = tag >> 3, tag & 7
        if wt == 0:
            v, i = read_varint(b, i)
            if v is None:
                break
            out.setdefault(fn, v)
        elif wt == 2:
            ln, i = read_varint(b, i)
            if ln is None:
                break
            out.setdefault(fn, ("LEN", i, i + ln))
            i += ln
        elif wt == 5:
            i += 4
        elif wt == 1:
            i += 8
        else:
            break
    return out


# (wrapped?, height field, round field) per tmcons.Message oneof member
LAYOUT = {
    "NewRoundStep":  (False, 1, 2),
    "NewValidBlock": (False, 1, 2),
    "Proposal":      (True,  2, 3),
    "ProposalPOL":   (False, 1, 2),
    "BlockPart":     (False, 1, 2),
    "Vote":          (True,  2, 3),
    "HasVote":       (False, 1, 2),
    "VoteSetMaj23":  (False, 1, 2),
    "VoteSetBits":   (False, 1, 2),
}


def decode(msg_hex):
    """Return (type, height, round). Absent varints default to 0, per protobuf."""
    try:
        b = bytes.fromhex(msg_hex)
    except ValueError:
        return None, None, None
    if not b:
        return None, None, None
    tag, i = read_varint(b, 0)
    if tag is None:
        return None, None, None
    fn, wt = tag >> 3, tag & 7
    if wt != 2 or fn not in ONEOF:
        return None, None, None
    name = ONEOF[fn]
    ln, i = read_varint(b, i)
    if ln is None:
        return name, None, None
    outer = scan_fields(b, i, min(i + ln, len(b)))

    wrapped, hf, rf = LAYOUT[name]
    if wrapped:
        inner = outer.get(1)
        if not (isinstance(inner, tuple) and inner[0] == "LEN"):
            return name, None, None
        fields = scan_fields(b, inner[1], inner[2])
    else:
        fields = outer

    h = fields.get(hf, 0)
    r = fields.get(rf, 0)
    if isinstance(h, tuple) or isinstance(r, tuple):
        return name, None, None
    return name, h, r


def parse(logdir, nodeid_to_validator):
    """Returns list of records: (height, round, sender, receiver, type)."""
    recs = []
    undecoded = defaultdict(int)
    for fn in sorted(os.listdir(logdir)):
        if not fn.endswith(".log"):
            continue
        idx = int(re.search(r"node(\d+)", fn).group(1))
        receiver = idx
        with open(os.path.join(logdir, fn), errors="ignore") as f:
            for line in f:
                m = LINE.search(line)
                if not m:
                    continue
                peer, ch, hexmsg = m.group(1), int(m.group(2)), m.group(3)
                if ch not in CONSENSUS_CHANNELS:
                    continue
                sender = nodeid_to_validator.get(peer)
                if sender is None or sender == receiver:
                    continue
                t, h, r = decode(hexmsg)
                if t is None:
                    undecoded[ch] += 1
                    continue
                if h is None or r is None:
                    undecoded[f"{t}-noview"] += 1
                    continue
                recs.append((h, r, sender, receiver, t))
    return recs, dict(undecoded)


def main():
    logdir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/e1logs"
    netdir = sys.argv[2] if len(sys.argv) > 2 else "/tmp/e1net"
    out = sys.argv[3] if len(sys.argv) > 3 else "research/results/e1/raw/comet_trace.json"

    import subprocess, glob
    n_val = len(glob.glob(os.path.join(netdir, "node*")))
    nid = {}
    for i in range(n_val):
        r = subprocess.run(
            ["./ext/cometbft/build/cometbft", "show-node-id",
             "--home", f"{netdir}/node{i}"],
            capture_output=True, text=True)
        nid[r.stdout.strip()] = i
    print(f"node id map: {len(nid)} nodes (n={n_val})")

    recs, undec = parse(logdir, nid)
    print(f"parsed {len(recs)} consensus messages")
    print(f"undecoded: {undec}")
    by_type = defaultdict(int)
    for _, _, _, _, t in recs:
        by_type[t] += 1
    print("by type:", dict(sorted(by_type.items(), key=lambda kv: -kv[1])))
    hs = sorted({h for h, _, _, _, _ in recs})
    print(f"heights: {min(hs) if hs else '-'}..{max(hs) if hs else '-'} "
          f"({len(hs)} distinct)")
    views = sorted({(h, r) for h, r, _, _, _ in recs})
    print(f"views (height,round): {len(views)}")

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump({"n_validators": n_val, "records": recs, "undecoded": undec}, f)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
