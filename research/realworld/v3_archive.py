#!/usr/bin/env python3
"""Full-epoch archive of the 40 chosen Cycle-3 epochs (raw_v3_full/, gzip JSON lines, one event per line).
Not read by any locked analysis; kept as a large local dataset for later work. Uses v3_fetch's keyed,
adaptively paced request path; THREADS epochs are fetched concurrently. Resume-safe per epoch."""
import gzip, json, os, sys
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import v3_fetch as f
THREADS = 4
EV = f"{f.v2.API}/accounts/0x1/events/0x1::block::BlockResource/new_block_events"

def one(c):
    out = os.path.join(f.FULL, f"epoch_{c['epoch']}_full.jsonl.gz")
    if os.path.exists(out): return
    try:
        with gzip.open(out + ".tmp", "wt") as g:
            h = c["first_height"]
            while h < c["last_height"]:
                page = f.get(f"{EV}?start={h}&limit=100")
                if not page: break
                for e in page:
                    if int(e["sequence_number"]) < c["last_height"]: g.write(json.dumps(e) + "\n")
                h += len(page)
        os.replace(out + ".tmp", out); f.v2.log(f"archive epoch {c['epoch']}: {c['last_height'] - c['first_height']:,} rounds")
    except RuntimeError as e:
        f.v2.log(f"archive epoch {c['epoch']}: FAILED ({e})")

if __name__ == "__main__":
    if not f.KEY: sys.exit("no API key: the full-epoch archive is only practical with one")
    os.makedirs(f.FULL, exist_ok=True)
    chosen = sorted(json.load(open(os.path.join(f.RAW, "_epoch_table.json")))["chosen"], key=lambda c: c["epoch"])
    with ThreadPoolExecutor(THREADS) as ex: list(ex.map(one, chosen))
    missing = [c["epoch"] for c in chosen if not os.path.exists(os.path.join(f.FULL, f"epoch_{c['epoch']}_full.jsonl.gz"))]
    f.v2.log("ARCHIVE_COMPLETE" if not missing else f"ARCHIVE_INCOMPLETE {missing}")
    sys.exit(0 if not missing else 1)
