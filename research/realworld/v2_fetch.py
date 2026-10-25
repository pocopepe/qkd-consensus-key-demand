#!/usr/bin/env python3
"""Campaign v2 fetcher: held-out Aptos mainnet sample via the NewBlockEvent
stream (100 consecutive blocks per request; sequence_number == block height).

Fetch ONLY -- no analysis here, so nothing in this file can see a result.
Raw events + the epoch's historical validator set (with voting power) are
persisted per epoch to raw_v2/epoch_<N>.json. Resume-safe: an epoch whose
file exists is never re-fetched. Epoch choice and within-epoch offsets come
from RNGs seeded with fixed strings recorded in PREDICTION_LOCK_V2.md.
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

API = "https://fullnode.mainnet.aptoslabs.com/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw_v2")
EPOCHS_TARGET = 30
ROUNDS_PER_EPOCH = 2000
DELAY_S = 1.0
# every epoch inspected before this lock (Phase 0 + campaign v1 = sample A)
SEEN = {17314, 17265, 17266, 17267, 17286, 17305}
SELECT_SEED = "v2-epoch-select-2026-09-18"
OFFSET_SEED = "v2-offset-2026-09-18"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def get(url: str, retries: int = 12):
    for attempt in range(retries):
        time.sleep(DELAY_S)
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.load(r), dict(r.headers)
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):  # pruned / not found: retrying cannot help
                raise RuntimeError(f"HTTP {e.code} (pruned) on {url}")
            wait = 60 if e.code == 429 else 5
            log(f"  HTTP {e.code}, waiting {wait}s (attempt {attempt + 1})")
            time.sleep(wait)
        except Exception as e:  # network blip
            log(f"  {type(e).__name__}: {e}; waiting 10s")
            time.sleep(10)
    raise RuntimeError(f"gave up on {url}")


def epoch_table() -> tuple[list[dict], int]:
    """All retained epochs as {epoch, first_height, last_height}, from the
    reconfiguration event stream, paged backwards 100 at a time."""
    _, hdr = get(f"{API}/")
    oldest_height = int(hdr.get("X-Aptos-Oldest-Block-Height") or hdr.get("x-aptos-oldest-block-height"))
    base = f"{API}/accounts/0x1/events/0x1::reconfiguration::Configuration/events"
    latest, _ = get(f"{base}?limit=1")
    top = int(latest[-1]["sequence_number"])
    rows = []
    for start in (top - 99, top - 199):
        try:
            page, _ = get(f"{base}?start={max(0, start)}&limit=100")
        except RuntimeError as e:  # older page may be beyond the prune horizon
            log(f"  epoch-table page at {start} unavailable: {e}")
            continue
        rows.extend(page)
    seen, recs = set(), []
    for ev in sorted(rows, key=lambda e: int(e["sequence_number"])):
        ep = int(ev["data"]["epoch"])
        if ep in seen:
            continue
        seen.add(ep)
        recs.append({"epoch": ep, "version": int(ev["version"])})
    return recs, oldest_height


def main() -> int:
    os.makedirs(RAW, exist_ok=True)
    table_path = os.path.join(RAW, "_epoch_table.json")
    if os.path.exists(table_path):
        chosen = json.load(open(table_path))["chosen"]
        log(f"resuming with recorded epoch choice ({len(chosen)} epochs)")
    else:
        recs, oldest_height = epoch_table()
        # resolve each epoch's first block height lazily: only for candidates
        # comfortably inside retained history (skip the 8 oldest, prune margin)
        recs = recs[:-1]  # newest epoch is still open; need its successor for an end bound
        cands = []
        for i in range(len(recs) - 1):
            if recs[i]["epoch"] in SEEN:
                continue
            cands.append({"epoch": recs[i]["epoch"], "version": recs[i]["version"],
                          "next_version": recs[i + 1]["version"]})
        rng = random.Random(SELECT_SEED)
        rng.shuffle(cands)
        chosen = []
        for c in cands:
            if len(chosen) >= EPOCHS_TARGET:
                break
            try:
                b0, _ = get(f"{API}/blocks/by_version/{c['version']}")
                b1, _ = get(f"{API}/blocks/by_version/{c['next_version']}")
            except RuntimeError:
                continue  # pruned
            h0, h1 = int(b0["block_height"]) + 1, int(b1["block_height"])  # skip the reconfig block itself
            if h0 < oldest_height + 2_000_000 or h1 - h0 < ROUNDS_PER_EPOCH + 10:
                continue  # too close to the prune horizon, or too short to sample
            c.update(first_height=h0, last_height=h1)
            chosen.append(c)
        offs = random.Random(OFFSET_SEED)
        for c in sorted(chosen, key=lambda c: c["epoch"]):
            c["start_height"] = c["first_height"] + offs.randrange(0, c["last_height"] - c["first_height"] - ROUNDS_PER_EPOCH)
        json.dump({"chosen": chosen, "candidates": len(cands)}, open(table_path, "w"), indent=1)
        log(f"chose {len(chosen)} epochs from {len(cands)} candidates: {sorted(c['epoch'] for c in chosen)}")

    ev_base = f"{API}/accounts/0x1/events/0x1::block::BlockResource/new_block_events"
    for c in sorted(chosen, key=lambda c: c["epoch"]):
        out = os.path.join(RAW, f"epoch_{c['epoch']}.json")
        if os.path.exists(out):
            continue
        events = []
        h = c["start_height"]
        try:
            while len(events) < ROUNDS_PER_EPOCH:
                page, _ = get(f"{ev_base}?start={h}&limit=100")
                if not page:
                    break
                events.extend(page)
                h += len(page)
        except RuntimeError as e:  # logged and reported as a shortfall, never silently dropped
            log(f"epoch {c['epoch']}: FETCH FAILED ({e}); skipping")
            continue
        events = [e for e in events[:ROUNDS_PER_EPOCH] if int(e["data"]["epoch"]) == c["epoch"]]
        vs, _ = get(f"{API}/accounts/0x1/resource/0x1::stake::ValidatorSet?ledger_version={events[0]['version']}")
        validators = [{"addr": v["addr"], "index": int(v["config"]["validator_index"]),
                       "voting_power": int(v["voting_power"])} for v in vs["data"]["active_validators"]]
        tmp = out + ".tmp"
        json.dump({"epoch": c["epoch"], "start_height": c["start_height"],
                   "validators": validators, "events": events}, open(tmp, "w"))
        os.replace(tmp, out)
        log(f"epoch {c['epoch']}: {len(events)} rounds, n={len(validators)}")
    log("FETCH_COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
