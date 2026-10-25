#!/usr/bin/env python3
"""Cycle-3 Aptos fetch (fetch only; nothing here can see a result): held-out epochs for a
pre-registered replication of the leader-schedule results and a test of an activity-weighted
form of Corollary 2.

Reuses the locked v2_fetch.py by import (the file itself is unchanged): its request helper
and epoch table. Excludes every epoch ever examined: sample A and the 30 epochs of campaign v2.
Draws EPOCHS_TARGET completed epochs by seeded shuffle and takes ROUNDS consecutive rounds from
each, at a seeded offset. Oldest epochs are fetched first (retained history is pruned from the old end).

Requests: an optional Geomi API key is read from $APTOS_API_KEY or ~/.config/predictive/aptos_api_key (never
logged or stored in the repository) and sent as a bearer token. Pacing adapts: the delay starts at 3.4 s
anonymously (just under the measured anonymous quota of about 90 requests per 300 s) or 0.2 s with a key,
shrinks by 10% after 20 consecutive successes, and doubles on HTTP 429 (plus a 60 s pause). 404/410 mean the
data is pruned and are not retried. --archive-full additionally downloads each chosen epoch in full to
raw_v3_full/ (an archive for later work; the locked analysis reads only raw_v3/).
Resume-safe: an epoch whose file exists is skipped."""
import gzip, json, os, random, sys, time, urllib.error, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import v2_fetch as v2

RAW = os.path.join(HERE, "raw_v3")
FULL = os.path.join(HERE, "raw_v3_full")

def _key():
    k = os.environ.get("APTOS_API_KEY", "").strip()
    p = os.path.expanduser("~/.config/predictive/aptos_api_key")
    if not k and os.path.exists(p): k = open(p).read().strip()
    return k or None
KEY = _key()
PACE = {"delay": 0.2 if KEY else 3.4, "floor": 0.05 if KEY else 3.0, "ok": 0}

def get(url, retries=12):
    """GET with optional bearer key and adaptive pacing. Returns parsed JSON."""
    hdr = {"User-Agent": "consensus-measurement/1.0 (academic research)"}
    if KEY: hdr["Authorization"] = f"Bearer {KEY}"
    for attempt in range(retries):
        time.sleep(PACE["delay"])
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=40) as r:
                d = json.load(r)
            PACE["ok"] += 1
            if PACE["ok"] >= 20: PACE["delay"] = max(PACE["floor"], PACE["delay"] * 0.9); PACE["ok"] = 0
            return d
        except urllib.error.HTTPError as e:
            if e.code in (404, 410): raise RuntimeError(f"HTTP {e.code} (pruned) on {url}")
            PACE["ok"] = 0
            if e.code == 429:
                PACE["delay"] = min(10.0, PACE["delay"] * 2); v2.log(f"  429: delay now {PACE['delay']:.2f}s, pausing 60s"); time.sleep(60)
            else:
                v2.log(f"  HTTP {e.code}; retry {attempt + 1}"); time.sleep(5 * (attempt + 1))
        except Exception as e:
            v2.log(f"  {type(e).__name__}: {e}; retry {attempt + 1}"); time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"gave up on {url}")
EPOCHS_TARGET, ROUNDS = 40, 6000
SELECT_SEED, OFFSET_SEED = "v3-epoch-select-2026-09-22", "v3-offset-2026-09-22"

def seen_epochs():
    chosen = json.load(open(os.path.join(HERE, "raw_v2", "_epoch_table.json")))["chosen"]
    return v2.SEEN | {c["epoch"] for c in chosen}

def main():
    os.makedirs(RAW, exist_ok=True)
    tp = os.path.join(RAW, "_epoch_table.json")
    if os.path.exists(tp):
        chosen = json.load(open(tp))["chosen"]; v2.log(f"resuming with recorded choice ({len(chosen)} epochs)")
    else:
        seen = seen_epochs(); recs, oldest = v2.epoch_table(); recs = recs[:-1]
        cands = [{"epoch": recs[i]["epoch"], "version": recs[i]["version"], "next_version": recs[i + 1]["version"]}
                 for i in range(len(recs) - 1) if recs[i]["epoch"] not in seen]
        random.Random(SELECT_SEED).shuffle(cands); chosen = []
        for c in cands:
            if len(chosen) >= EPOCHS_TARGET: break
            try:
                b0, _ = v2.get(f"{v2.API}/blocks/by_version/{c['version']}"); b1, _ = v2.get(f"{v2.API}/blocks/by_version/{c['next_version']}")
            except RuntimeError:
                continue
            h0, h1 = int(b0["block_height"]) + 1, int(b1["block_height"])
            if h0 < oldest + 2_000_000 or h1 - h0 < ROUNDS + 10: continue
            c.update(first_height=h0, last_height=h1); chosen.append(c)
        offs = random.Random(OFFSET_SEED)
        for c in sorted(chosen, key=lambda c: c["epoch"]):
            c["start_height"] = c["first_height"] + offs.randrange(0, c["last_height"] - c["first_height"] - ROUNDS)
        json.dump({"chosen": chosen, "candidates": len(cands), "excluded_seen": sorted(seen),
                   "utc": time.strftime("%FT%TZ", time.gmtime())}, open(tp, "w"), indent=1)
        v2.log(f"chose {len(chosen)} epochs from {len(cands)} unseen candidates: {sorted(c['epoch'] for c in chosen)}")
    if "--plan-only" in sys.argv: return 0
    ev_base = f"{v2.API}/accounts/0x1/events/0x1::block::BlockResource/new_block_events"
    for c in sorted(chosen, key=lambda c: c["epoch"]):
        out = os.path.join(RAW, f"epoch_{c['epoch']}.json")
        if os.path.exists(out): continue
        events, h = [], c["start_height"]
        try:
            while len(events) < ROUNDS:
                page = get(f"{ev_base}?start={h}&limit=100")
                if not page: break
                events.extend(page); h += len(page)
        except RuntimeError as e:
            v2.log(f"epoch {c['epoch']}: FETCH FAILED ({e}); skipping"); continue
        events = [e for e in events[:ROUNDS] if int(e["data"]["epoch"]) == c["epoch"]]
        vs = get(f"{v2.API}/accounts/0x1/resource/0x1::stake::ValidatorSet?ledger_version={events[0]['version']}")
        validators = [{"addr": v["addr"], "index": int(v["config"]["validator_index"]), "voting_power": int(v["voting_power"])}
                      for v in vs["data"]["active_validators"]]
        json.dump({"epoch": c["epoch"], "start_height": c["start_height"], "validators": validators, "events": events}, open(out + ".tmp", "w"))
        os.replace(out + ".tmp", out); v2.log(f"epoch {c['epoch']}: {len(events)} rounds, n={len(validators)}")
    if "--archive-full" in sys.argv:
        os.makedirs(FULL, exist_ok=True)
        for c in sorted(chosen, key=lambda c: c["epoch"]):
            out = os.path.join(FULL, f"epoch_{c['epoch']}_full.jsonl.gz")
            if os.path.exists(out): continue
            try:
                with gzip.open(out + ".tmp", "wt") as f:
                    h = c["first_height"]
                    while h < c["last_height"]:
                        page = get(f"{ev_base}?start={h}&limit=100")
                        if not page: break
                        for e in page: f.write(json.dumps(e) + "\n")
                        h += len(page)
                os.replace(out + ".tmp", out); v2.log(f"archive epoch {c['epoch']}: {c['last_height'] - c['first_height']} rounds")
            except RuntimeError as e:
                v2.log(f"archive epoch {c['epoch']}: FAILED ({e})")
    missing = [c["epoch"] for c in chosen if not os.path.exists(os.path.join(RAW, f"epoch_{c['epoch']}.json"))]
    v2.log("FETCH_COMPLETE" if not missing else f"FETCH_INCOMPLETE {missing}")
    return 0 if not missing else 1

if __name__ == "__main__":
    sys.exit(main())
