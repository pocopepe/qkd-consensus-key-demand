#!/usr/bin/env python3
"""Userspace control plane: push the pre-arm set into prearm_map each view.

Requires root, a compiled prearm.bpf.o, and python bcc or libbpf bindings. This
is deliberately thin: the interesting logic lives in the control plane
(qkdnet/), and this file only shows the syscall accounting that motivates the
U_max budget -- one bpf_map_update_elem per *changed* entry, batched where the
kernel supports BPF_MAP_UPDATE_BATCH, and nothing at all for entries that stay.
"""
import ctypes
import struct
import time


class PairKey(ctypes.Structure):
    _fields_ = [("lo", ctypes.c_uint32), ("hi", ctypes.c_uint32)]


class PrearmVal(ctypes.Structure):
    _fields_ = [("key_id", ctypes.c_uint8 * 16),
                ("offset", ctypes.c_uint32),
                ("bits_left", ctypes.c_uint32),
                ("expiry_ns", ctypes.c_uint64)]


def diff_commit(bpf_map, current: dict, target: dict, ttl_ns: int) -> dict:
    """Apply target as a diff. Returns the syscall count, which is the quantity
    the U_max constraint in the control plane is denominated in."""
    to_del = set(current) - set(target)
    to_put = {p: v for p, v in target.items()
              if p not in current or current[p] != v}
    now = time.monotonic_ns()
    n = 0
    for p in to_del:
        del bpf_map[PairKey(*p)]
        n += 1
    for p, (key_id, offset, bits) in to_put.items():
        val = PrearmVal()
        val.key_id[:] = key_id[:16]
        val.offset = offset
        val.bits_left = bits
        val.expiry_ns = now + ttl_ns
        bpf_map[PairKey(*p)] = val
        n += 1
    return {"syscalls": n, "deleted": len(to_del), "written": len(to_put)}


if __name__ == "__main__":
    print(__doc__)
    print("Compile:  clang -O2 -g -target bpf -c bpf/prearm.bpf.c -o bpf/prearm.bpf.o")
    print("Verify:   bpftool prog load bpf/prearm.bpf.o /sys/fs/bpf/prearm")
    print("Insns:    bpftool prog show pinned /sys/fs/bpf/prearm   # constant in |S|")
