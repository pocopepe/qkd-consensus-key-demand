#!/usr/bin/env python3
"""Cosmos Hub campaign fetcher (fetch only; nothing here can see a result).

For each seeded window of consecutive heights, stores per block: height, time,
proposer, commit round, slot count, and the ADDRESSES of validators whose
precommit is flagged absent (1) or nil (3). Absent slots carry no address in a
CometBFT commit, so absentees are recovered as (validator set) minus (addresses
present); the validator set is fetched at the window start and re-fetched for
any block where the counts disagree (set membership changed mid-window).
Resume-safe: a window whose file exists is skipped."""
from __future__ import annotations
import json, os, random, sys, time, urllib.error, urllib.request

RPC = "https://cosmos-rpc.publicnode.com"
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
WINDOWS, BLOCKS = 30, 300
SEED = "cosmos-window-select-2026-09-19"
MARGIN = 200_000            # stay clear of the prune horizon and the chain tip
DELAY_S = 0.15
UA = {"User-Agent": "consensus-measurement/1.0 (academic research)"}


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def get(path: str, retries: int = 10):
    for a in range(retries):
        time.sleep(DELAY_S)
        try:
            with urllib.request.urlopen(urllib.request.Request(RPC + path, headers=UA), timeout=40) as r:
                d = json.load(r)
            if "result" in d:
                return d["result"]
            raise RuntimeError(str(d.get("error"))[:200])
        except urllib.error.HTTPError as e:
            w = 60 if e.code == 429 else 5
            log(f"  HTTP {e.code} on {path}; waiting {w}s"); time.sleep(w)
        except Exception as e:
            log(f"  {type(e).__name__}: {e}; waiting 10s"); time.sleep(10)
    raise RuntimeError(f"gave up on {path}")


def valset(h: int) -> dict[str, int]:
    out, page = {}, 1
    while True:
        r = get(f"/validators?height={h}&per_page=100&page={page}")
        out.update({v["address"]: int(v["voting_power"]) for v in r["validators"]})
        if len(out) >= int(r["total"]):
            return out
        page += 1


def main() -> int:
    os.makedirs(RAW, exist_ok=True)
    plan = os.path.join(RAW, "_windows.json")
    if os.path.exists(plan):
        starts = json.load(open(plan))["starts"]
    else:
        si = get("/status")["sync_info"]
        lo, hi = int(si["earliest_block_height"]) + MARGIN, int(si["latest_block_height"]) - MARGIN - BLOCKS
        starts = sorted(random.Random(SEED).sample(range(lo, hi), WINDOWS))
        json.dump({"starts": starts, "lo": lo, "hi": hi, "utc": time.strftime("%FT%TZ", time.gmtime())}, open(plan, "w"))
        log(f"windows drawn from [{lo}, {hi}]: {starts}")
    for s0 in starts:
        dst = os.path.join(RAW, f"window_{s0}.json")
        if os.path.exists(dst):
            continue
        vs = valset(s0); refetched = 0; blocks = []
        for h in range(s0, s0 + BLOCKS):
            sh = get(f"/commit?height={h}")["signed_header"]
            sigs = sh["commit"]["signatures"]
            present = {x["validator_address"] for x in sigs if x["validator_address"]}
            n_abs = sum(1 for x in sigs if int(x["block_id_flag"]) == 1)
            if len(sigs) != len(vs) or len(set(vs) - present) != n_abs or not present <= set(vs):
                vs = valset(h); refetched += 1
            blocks.append({"h": h, "t": sh["header"]["time"], "p": sh["header"]["proposer_address"],
                           "r": int(sh["commit"]["round"]), "n": len(sigs),
                           "absent": sorted(set(vs) - present),
                           "nil": sorted(x["validator_address"] for x in sigs if int(x["block_id_flag"]) == 3),
                           "consistent": len(set(vs) - present) == n_abs})
        json.dump({"start": s0, "power": vs, "valset_refetches": refetched, "blocks": blocks}, open(dst + ".tmp", "w"))
        os.replace(dst + ".tmp", dst)
        log(f"window {s0}: {len(blocks)} blocks, n={len(vs)}, refetches={refetched}, "
            f"inconsistent={sum(1 for b in blocks if not b['consistent'])}")
    log("FETCH_COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
