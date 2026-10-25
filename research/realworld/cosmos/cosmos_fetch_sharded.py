#!/usr/bin/env python3
"""Run the locked cosmos_fetch.py unchanged on one shard of the recorded windows.
Usage: cosmos_fetch_sharded.py <shard> <nshards>. The fetcher skips any window
whose file already exists; this wrapper makes it treat other shards' windows as
existing, so N workers split the same seeded window list with no overlap. No
analysis here, and cosmos_fetch.py itself is not modified (its hash is locked)."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import cosmos_fetch as f
shard, nshards = int(sys.argv[1]), int(sys.argv[2])
starts = json.load(open(os.path.join(f.RAW, "_windows.json")))["starts"]
todo = [s for s in starts if not os.path.exists(os.path.join(f.RAW, f"window_{s}.json"))]
mine = {s for i, s in enumerate(todo) if i % nshards == shard}
real_exists = os.path.exists
def exists(p):
    m = re.search(r"window_(\d+)\.json$", str(p))
    return True if (m and int(m.group(1)) not in mine) else real_exists(p)
os.path.exists = exists
f.log(f"shard {shard}/{nshards}: {len(mine)} windows {sorted(mine)}")
sys.exit(f.main())
