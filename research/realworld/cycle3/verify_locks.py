#!/usr/bin/env python3
"""Refuse to start unless every file hashed in a Cycle-3 lock still has its locked SHA-256.
Usage: verify_locks.py <lock.md>...   Exit 1 on any mismatch or missing file."""
import hashlib, os, re, sys
bad = 0
for lock in sys.argv[1:]:
    base = os.path.dirname(os.path.abspath(lock)); body = open(lock).read().split("## Hashes at lock time", 1)[1]
    for name, h in re.findall(r"^\s{4}(\S+)(?:\s+\([^)]*\))?\s+([0-9a-f]{64})\s*$", body, re.M):
        path = {"hotstuff_e3t": "/home/pocopepe/code/predictive/ext/relab-hotstuff/hotstuff_e3t",
                "research/e2_parse.py": os.path.join(base, "..", "..", "e2_parse.py"),
                "research/e1_analyze.py": os.path.join(base, "..", "..", "e1_analyze.py"),
                "pi_p_model.py": os.path.join(base, "..", "pi_p_model.py")}.get(name, os.path.join(base, name))
        try: got = hashlib.sha256(open(path, "rb").read()).hexdigest()
        except FileNotFoundError: got = "MISSING"
        ok = got == h; bad += not ok
        print(f"{'ok ' if ok else 'BAD'} {os.path.basename(lock)}: {name}")
sys.exit(1 if bad else 0)
