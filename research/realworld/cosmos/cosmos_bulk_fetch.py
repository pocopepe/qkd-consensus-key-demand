#!/usr/bin/env python3
"""Cycle-3 Cosmos Hub bulk fetch (fetch only; nothing here can see a result).

One contiguous held-out range of LEN blocks, start drawn with seed SEED from the node's
retained history, away from the prune horizon and the tip, and not overlapping any of the
30 windows of the earlier campaign (development data). Stored in chunks of CHUNK blocks in
the same compact format as cosmos_fetch.py (per block: height, time, proposer, commit round,
slot count, absent and nil addresses; validator power at the chunk start, re-fetched when a
block's signature set disagrees with it). WORKERS threads take whole chunks; a chunk file
is written atomically, so the fetch is resume-safe.
Usage: cosmos_bulk_fetch.py [--plan-only]"""
from __future__ import annotations
import json, os, queue, random, sys, threading, time, urllib.error, urllib.request
RPC = "https://cosmos-rpc.publicnode.com"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "raw_bulk")
LEN, CHUNK, WORKERS = 200_000, 2_000, 8
SEED = "cosmos-bulk-select-2026-09-22"
MARGIN = 200_000
UA = {"User-Agent": "consensus-measurement/1.0 (academic research)"}
LOCK = threading.Lock()

def log(m):
    with LOCK: print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

def get(path, retries=12):
    for a in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(RPC + path, headers=UA), timeout=40) as r:
                d = json.load(r)
            if "result" in d: return d["result"]
            raise RuntimeError(str(d.get("error"))[:200])
        except urllib.error.HTTPError as e:
            w = 60 if e.code == 429 else 5 * (a + 1); log(f"  HTTP {e.code} on {path}; waiting {w}s"); time.sleep(w)
        except Exception as e:
            log(f"  {type(e).__name__}: {e}; waiting {5 * (a + 1)}s"); time.sleep(5 * (a + 1))
    raise RuntimeError(f"gave up on {path}")

def valset(h):
    out, page = {}, 1
    while True:
        r = get(f"/validators?height={h}&per_page=100&page={page}")
        out.update({v["address"]: int(v["voting_power"]) for v in r["validators"]})
        if len(out) >= int(r["total"]): return out
        page += 1

def plan():
    p = os.path.join(OUT, "_plan.json")
    if os.path.exists(p): return json.load(open(p))
    si = get("/status")["sync_info"]
    lo, hi = int(si["earliest_block_height"]) + MARGIN, int(si["latest_block_height"]) - MARGIN - LEN
    dev = json.load(open(os.path.join(HERE, "raw", "_windows.json")))["starts"]
    rng = random.Random(SEED)
    while True:
        s0 = rng.randrange(lo, hi)
        if all(s0 + LEN <= d or d + 300 <= s0 for d in dev): break
    pl = {"start": s0, "len": LEN, "chunk": CHUNK, "lo": lo, "hi": hi, "dev_windows_avoided": len(dev),
          "utc": time.strftime("%FT%TZ", time.gmtime()), "seed": SEED}
    os.makedirs(OUT, exist_ok=True); json.dump(pl, open(p, "w"), indent=1); log(f"plan: {pl}"); return pl

def fetch_chunk(c0):
    dst = os.path.join(OUT, f"chunk_{c0}.json")
    if os.path.exists(dst): return
    vs = valset(c0); refetched = 0; blocks = []
    for h in range(c0, c0 + CHUNK):
        sh = get(f"/commit?height={h}")["signed_header"]; sigs = sh["commit"]["signatures"]
        present = {x["validator_address"] for x in sigs if x["validator_address"]}
        n_abs = sum(1 for x in sigs if int(x["block_id_flag"]) == 1)
        if len(sigs) != len(vs) or len(set(vs) - present) != n_abs or not present <= set(vs):
            vs = valset(h); refetched += 1
        blocks.append({"h": h, "t": sh["header"]["time"], "p": sh["header"]["proposer_address"], "r": int(sh["commit"]["round"]),
                       "n": len(sigs), "absent": sorted(set(vs) - present),
                       "nil": sorted(x["validator_address"] for x in sigs if int(x["block_id_flag"]) == 3),
                       "consistent": len(set(vs) - present) == n_abs})
    json.dump({"start": c0, "power": vs, "valset_refetches": refetched, "blocks": blocks}, open(dst + ".tmp", "w"))
    os.replace(dst + ".tmp", dst)

def main():
    pl = plan()
    if "--plan-only" in sys.argv: return 0
    q = queue.Queue()
    for c0 in range(pl["start"], pl["start"] + pl["len"], pl["chunk"]):
        if not os.path.exists(os.path.join(OUT, f"chunk_{c0}.json")): q.put(c0)
    total, t0 = q.qsize(), time.time(); log(f"{total} chunks to fetch with {WORKERS} workers")
    def worker():
        while True:
            try: c0 = q.get_nowait()
            except queue.Empty: return
            try:
                fetch_chunk(c0); done = total - q.qsize()
                log(f"chunk {c0} done ({done}/{total}, {done * CHUNK / (time.time() - t0):.1f} blocks/s)")
            except Exception as e:
                log(f"chunk {c0} FAILED: {e}")
    ts = [threading.Thread(target=worker) for _ in range(WORKERS)]
    [t.start() for t in ts]; [t.join() for t in ts]
    missing = [c for c in range(pl["start"], pl["start"] + pl["len"], pl["chunk"]) if not os.path.exists(os.path.join(OUT, f"chunk_{c}.json"))]
    log("FETCH_COMPLETE" if not missing else f"FETCH_INCOMPLETE {len(missing)} chunks missing")
    return 0 if not missing else 1

if __name__ == "__main__":
    sys.exit(main())
