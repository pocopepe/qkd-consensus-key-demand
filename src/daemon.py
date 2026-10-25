#!/usr/bin/env python3
"""Predictive control-plane daemon.

Ingests telemetry, forecasts the next view's demand from the consensus
schedule, ranks candidates, and writes the winning set into the kernel maps with
native bpf() calls through libbpf. The kernel program is never reloaded; only
map contents change, which is what keeps a commit to a few microseconds per
entry.

Maps are picked up from bpffs by path, so this process can be restarted without
disturbing the data plane.
"""
from __future__ import annotations

import argparse
import ctypes as ct
import os
import struct
import sys
import time
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

PIN_DIR = "/sys/fs/bpf/qkd"
KEY_ID_BYTES = 16
MAX_VALIDATORS = 1024


# ---------------------------------------------------------------------------
# libbpf binding
# ---------------------------------------------------------------------------

class _Libbpf:
    """Thin ctypes binding: bpf_obj_get plus the element and batch operations."""

    def __init__(self, path="libbpf.so.1"):
        self.lib = ct.CDLL(path, use_errno=True)
        self.lib.bpf_obj_get.argtypes = [ct.c_char_p]
        self.lib.bpf_obj_get.restype = ct.c_int
        self.lib.bpf_map_update_elem.argtypes = [ct.c_int, ct.c_void_p,
                                                 ct.c_void_p, ct.c_uint64]
        self.lib.bpf_map_update_elem.restype = ct.c_int
        self.lib.bpf_map_lookup_elem.argtypes = [ct.c_int, ct.c_void_p, ct.c_void_p]
        self.lib.bpf_map_lookup_elem.restype = ct.c_int
        self.lib.bpf_map_delete_elem.argtypes = [ct.c_int, ct.c_void_p]
        self.lib.bpf_map_delete_elem.restype = ct.c_int
        self.lib.bpf_map_update_batch.argtypes = [ct.c_int, ct.c_void_p, ct.c_void_p,
                                                  ct.POINTER(ct.c_uint32), ct.c_void_p]
        self.lib.bpf_map_update_batch.restype = ct.c_int
        self.lib.bpf_map_get_next_key.argtypes = [ct.c_int, ct.c_void_p, ct.c_void_p]
        self.lib.bpf_map_get_next_key.restype = ct.c_int

    def obj_get(self, name):
        fd = self.lib.bpf_obj_get(os.path.join(PIN_DIR, name).encode())
        if fd < 0:
            raise OSError(ct.get_errno(),
                          f"bpf_obj_get({name}) failed; is the loader attached?")
        return fd


# struct pair_key { u32 lo, hi; }
PAIR = struct.Struct("<II")
# struct prearm_val: key_id[16], offset, bits_left, install_ns, expiry_ns,
#                    lease_ns, max_life_ns, uses, owner_a, owner_b, _pad
VAL = struct.Struct("<16sIIQQQQIIII")
# struct qkd_token_bucket: tokens, capacity, refill, last_refill, throttled, credits
TOK = struct.Struct("<QQQQQQ")
# struct enforcer_stats: 8 x u64
STATS = struct.Struct("<8Q")


class KernelPlane:
    """The map-writing half of the control plane."""

    def __init__(self, lib: _Libbpf):
        self.lib = lib
        self.prearm = lib.obj_get("prearm_map")
        self.tokens = lib.obj_get("token_map")
        self.gc_ring = lib.obj_get("gc_ring")
        self.stats = lib.obj_get("stats_map")
        self.ncpu = os.cpu_count() or 1
        self._ring_slot = 0
        self._ring_size = 1024
        self.syscalls = 0

    def arm(self, a, b, bits, lease_ms, max_life_ms, key_id=None):
        lo, hi = (a, b) if a < b else (b, a)
        now = time.monotonic_ns()
        kid = key_id or bytes((lo * 31 + hi * 17 + i) & 0xFF for i in range(KEY_ID_BYTES))
        val = VAL.pack(kid, 0, int(bits), now,
                       now + int(lease_ms * 1e6), int(lease_ms * 1e6),
                       int(max_life_ms * 1e6), 0, lo, hi, 0)
        k = PAIR.pack(lo, hi)
        r = self.lib.lib.bpf_map_update_elem(self.prearm, k, val, 0)
        self.syscalls += 1
        if r == 0:
            # register in the GC ring so the data plane can reclaim it itself
            idx = struct.pack("<I", self._ring_slot)
            self.lib.lib.bpf_map_update_elem(self.gc_ring, idx, k, 0)
            self.syscalls += 1
            self._ring_slot = (self._ring_slot + 1) % self._ring_size
        return r == 0

    def arm_batch(self, plan, lease_ms, max_life_ms):
        """One bpf_map_update_batch for the whole plan.

        Batching matters because the commit sits inside the view's deadline: the
        per-entry cost falls by roughly a factor of three once the plan is more
        than a few dozen entries."""
        if not plan:
            return 0
        n = len(plan)
        now = time.monotonic_ns()
        kbuf = (ct.c_char * (PAIR.size * n))()
        vbuf = (ct.c_char * (VAL.size * n))()
        for i, ((a, b), bits) in enumerate(plan.items()):
            lo, hi = (a, b) if a < b else (b, a)
            kid = bytes((lo * 31 + hi * 17 + j) & 0xFF for j in range(KEY_ID_BYTES))
            PAIR.pack_into(kbuf, i * PAIR.size, lo, hi)
            VAL.pack_into(vbuf, i * VAL.size, kid, 0, int(bits), now,
                          now + int(lease_ms * 1e6), int(lease_ms * 1e6),
                          int(max_life_ms * 1e6), 0, lo, hi, 0)
        cnt = ct.c_uint32(n)
        r = self.lib.lib.bpf_map_update_batch(self.prearm, kbuf, vbuf,
                                              ct.byref(cnt), None)
        self.syscalls += 1
        return cnt.value if r == 0 else 0

    def disarm(self, a, b):
        lo, hi = (a, b) if a < b else (b, a)
        self.syscalls += 1
        return self.lib.lib.bpf_map_delete_elem(self.prearm, PAIR.pack(lo, hi)) == 0

    def set_token_bucket(self, vid, capacity_bits, refill_bps):
        v = TOK.pack(int(capacity_bits), int(capacity_bits), int(refill_bps),
                     time.monotonic_ns(), 0, 0)
        self.syscalls += 1
        return self.lib.lib.bpf_map_update_elem(
            self.tokens, struct.pack("<I", vid), v, 0) == 0

    def read_token_bucket(self, vid):
        buf = (ct.c_char * TOK.size)()
        if self.lib.lib.bpf_map_lookup_elem(self.tokens, struct.pack("<I", vid), buf):
            return None
        t, c, r, lr, th, cr = TOK.unpack(bytes(buf))
        return {"tokens": t, "capacity": c, "refill": r,
                "throttled": th, "starved_credits": cr}

    def read_stats(self):
        buf = (ct.c_char * (STATS.size * self.ncpu))()
        if self.lib.lib.bpf_map_lookup_elem(self.stats, struct.pack("<I", 0), buf):
            return None
        agg = np.zeros(8, dtype=np.uint64)
        raw = bytes(buf)
        for c in range(self.ncpu):
            agg += np.array(STATS.unpack_from(raw, c * STATS.size), dtype=np.uint64)
        names = ["hits", "misses", "expired", "short_key", "throttled",
                 "gc_reclaimed", "renewals", "fast_ns"]
        return dict(zip(names, (int(x) for x in agg)))

    def live_pairs(self):
        out, cur = [], None
        nxt = (ct.c_char * PAIR.size)()
        while True:
            r = self.lib.lib.bpf_map_get_next_key(
                self.prearm, cur if cur else None, nxt)
            if r != 0:
                break
            k = bytes(nxt)
            out.append(PAIR.unpack(k))
            cur = (ct.c_char * PAIR.size)(*k)
            if len(out) > 200000:
                break
        return out


# ---------------------------------------------------------------------------
# Control loop
# ---------------------------------------------------------------------------

@dataclass
class DaemonConfig:
    n_validators: int = 16
    max_entries: int = 4096
    max_updates: int = 256
    bits_per_pair: int = 400_000
    # One view, not two. Sweep B showed a two-view lease makes starvation worse
    # than no pre-arming at all under bursty load: reserved key is unavailable
    # key, and the burst needs it now. A one-view lease that the data plane
    # renews on actual use recovers the whole regression and keeps the fast path.
    lease_ms: float = 250.0
    max_life_ms: float = 1000.0
    view_period_s: float = 0.25
    token_capacity_bits: int = 4_000_000
    token_refill_bps: int = 2_000_000
    use_batch: bool = True
    policy: str = "hybrid"


def run_daemon(cfg: DaemonConfig, views: int, verbose: bool = True):
    from qkdnet.consensus import BFTConsensus, ConsensusConfig
    from qkdnet.forecast import StructuralForecaster
    from qkdnet.topology import ring_with_chords
    from qkdnet.allocate import UtilityModel, build_candidates
    from simulator.hybrid import HybridSwapOptimizer

    lib = _Libbpf()
    kp = KernelPlane(lib)
    net = ring_with_chords(cfg.n_validators, seed=3)
    ccfg = ConsensusConfig(n=cfg.n_validators, seed=3, byzantine=(3, 11),
                           timeout_prob=0.03, view_period_s=cfg.view_period_s)
    cons = BFTConsensus(ccfg)
    fc = StructuralForecaster(cons)
    um = UtilityModel(lambda_bit=2.5e-5)
    opt = HybridSwapOptimizer(iters=600, time_budget_s=0.006)

    for v in range(cfg.n_validators):
        kp.set_token_bucket(v, cfg.token_capacity_bits, cfg.token_refill_bps)

    resident: dict = {}
    t_commit, t_opt = [], []
    for v in range(views):
        t0 = time.perf_counter()
        groups = fc.groups(v)
        pred = fc.predict(v)
        cands = build_candidates(pred, net, um)

        class _B:
            max_entries = cfg.max_entries
            max_updates_per_round = cfg.max_updates
        plan = opt.select(cands, _B, resident, net, groups=groups)
        plan = {p: cfg.bits_per_pair for p in plan}
        t_opt.append(time.perf_counter() - t0)

        # the commit timer covers only the kernel-facing work, because that is
        # the part U_max is denominated in; planning happens off the deadline
        t1 = time.perf_counter()
        stale = [p for p in resident if p not in plan]
        for p in stale:
            kp.disarm(*p)
        if cfg.use_batch:
            kp.arm_batch(plan, cfg.lease_ms, cfg.max_life_ms)
        else:
            for (a, b), bits in plan.items():
                kp.arm(a, b, bits, cfg.lease_ms, cfg.max_life_ms)
        resident = plan
        t_commit.append(time.perf_counter() - t1)

        # starvation credits feed straight back into next view's ranking
        credits = {i: (kp.read_token_bucket(i) or {}).get("starved_credits", 0)
                   for i in range(cfg.n_validators)}
        opt.set_credits(credits)

        out = cons.step()
        fc.observe(v, out.demand, {"leader": out.leader,
                                   "view_change": out.phase.value == "view_change"})
        if verbose and v % 20 == 0:
            st = kp.read_stats() or {}
            print(f"view {v:5d}  armed={len(plan):4d}  plan={t_opt[-1]*1e3:6.2f} ms  "
                  f"commit={t_commit[-1]*1e3:6.3f} ms  "
                  f"hits={st.get('hits',0):8d} misses={st.get('misses',0):8d} "
                  f"gc={st.get('gc_reclaimed',0):6d} thr={st.get('throttled',0):5d}",
                  flush=True)

    return {"plan_ms_mean": float(np.mean(t_opt) * 1e3),
            "commit_ms_mean": float(np.mean(t_commit) * 1e3),
            "commit_ms_p99": float(np.percentile(t_commit, 99) * 1e3),
            "commit_us_per_entry": float(np.mean(t_commit) * 1e6 / max(len(resident), 1)),
            "syscalls": kp.syscalls,
            "stats": kp.read_stats(),
            "live": len(kp.live_pairs())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--views", type=int, default=200)
    ap.add_argument("--validators", type=int, default=16)
    ap.add_argument("--max-entries", type=int, default=4096)
    ap.add_argument("--max-updates", type=int, default=256)
    ap.add_argument("--no-batch", action="store_true")
    a = ap.parse_args()
    cfg = DaemonConfig(n_validators=a.validators, max_entries=a.max_entries,
                       max_updates=a.max_updates, use_batch=not a.no_batch)
    r = run_daemon(cfg, a.views)
    print("\n--- daemon summary ---")
    for k, v in r.items():
        print(f"  {k:16} {v}")


if __name__ == "__main__":
    main()
