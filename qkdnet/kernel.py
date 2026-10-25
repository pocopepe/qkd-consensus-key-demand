"""Model of the eBPF/XDP enforcement plane, with a corrected resource account."""
from __future__ import annotations

from dataclasses import dataclass, field

from .consensus import Pair

# Measured constants for a one-lookup XDP fast path (see bpf/prearm.bpf.c).
XDP_PROG_INSNS = 312          # static, independent of map occupancy
VERIFIER_INSN_LIMIT = 1_000_000
ENTRY_VALUE_BYTES = 32
ENTRY_KEY_BYTES = 8


@dataclass
class KernelBudget:
    max_entries: int = 256          # M_max
    max_updates_per_round: int = 64  # U_max
    entry_bytes: int = ENTRY_KEY_BYTES + ENTRY_VALUE_BYTES

    @classmethod
    def from_memory(cls, kib: int, updates_per_round: int) -> "KernelBudget":
        per = ENTRY_KEY_BYTES + ENTRY_VALUE_BYTES
        return cls(max_entries=(kib * 1024) // per,
                   max_updates_per_round=updates_per_round)

    def memory_bytes(self) -> int:
        return self.max_entries * self.entry_bytes


@dataclass
class PrearmEntry:
    pair: Pair
    bits: float
    installed_view: int
    ttl_views: int

    def expired(self, view: int) -> bool:
        return view >= self.installed_view + self.ttl_views


@dataclass
class KernelStats:
    updates: int = 0
    deletes: int = 0
    inserts: int = 0
    evictions: int = 0
    update_budget_hits: int = 0
    capacity_hits: int = 0
    hits: int = 0
    misses: int = 0
    expired_unused: int = 0
    bits_wasted: float = 0.0
    bits_served_fast: float = 0.0


class XDPMap:
    """LRU hash of pre-armed pairs, with a per-round update budget and TTLs."""

    def __init__(self, budget: KernelBudget, net=None):
        self.budget = budget
        self.net = net                      # for releasing reservations on rollback
        self.entries: dict[Pair, PrearmEntry] = {}
        self.stats = KernelStats()
        self._lru: list[Pair] = []

    # -- verifier bookkeeping ------------------------------------------------

    def verifier_report(self) -> dict:
        return {
            "prog_insns": XDP_PROG_INSNS,
            "insn_limit": VERIFIER_INSN_LIMIT,
            "insns_scale_with_prearm_set": False,
            "map_entries": len(self.entries),
            "max_entries": self.budget.max_entries,
            "map_bytes": len(self.entries) * self.budget.entry_bytes,
        }

    # -- state transitions ---------------------------------------------------

    def expire(self, view: int) -> list[tuple[Pair, float]]:
        """Roll back reservations whose TTL has run out. Bounded and reversible:
        a wrong prediction costs the key-rate held for at most ttl_views."""
        dead = [p for p, e in self.entries.items() if e.expired(view)]
        released = []
        for p in dead:
            e = self.entries.pop(p)
            self._lru = [x for x in self._lru if x != p]
            self.stats.expired_unused += 1
            self.stats.bits_wasted += e.bits
            released.append((p, e.bits))
            if self.net is not None:
                self.net.release(p[0], p[1], e.bits)
        return released

    def commit(self, target: dict[Pair, float], view: int, ttl_views: int) -> dict:
        """Install `target` as the pre-arm set, subject to M_max and U_max."""
        cur = set(self.entries)
        want = set(target)
        # a pair already installed with the same bits needs no syscall
        keep = {p for p in cur & want if abs(self.entries[p].bits - target[p]) < 1e-9}
        to_del = cur - want
        to_ins = want - cur
        to_upd = (cur & want) - keep

        budget = self.budget.max_updates_per_round
        spent = 0
        # deletions first: they free both capacity and (importantly) held key
        for p in sorted(to_del):
            if spent >= budget:
                self.stats.update_budget_hits += 1
                break
            e = self.entries.pop(p)
            self._lru = [x for x in self._lru if x != p]
            if self.net is not None:
                self.net.release(p[0], p[1], e.bits)
            self.stats.bits_wasted += e.bits
            self.stats.deletes += 1
            spent += 1

        for p in sorted(to_upd):
            if spent >= budget:
                self.stats.update_budget_hits += 1
                break
            self.entries[p] = PrearmEntry(p, target[p], view, ttl_views)
            self.stats.updates += 1
            spent += 1

        for p in sorted(to_ins):
            if spent >= budget:
                self.stats.update_budget_hits += 1
                break
            if len(self.entries) >= self.budget.max_entries:
                # LRU eviction, exactly as the kernel map would do
                if not self._lru:
                    self.stats.capacity_hits += 1
                    break
                victim = self._lru.pop(0)
                ev = self.entries.pop(victim, None)
                if ev is not None and self.net is not None:
                    self.net.release(victim[0], victim[1], ev.bits)
                if ev is not None:
                    self.stats.bits_wasted += ev.bits
                self.stats.evictions += 1
                self.stats.capacity_hits += 1
            self.entries[p] = PrearmEntry(p, target[p], view, ttl_views)
            self._lru.append(p)
            self.stats.inserts += 1
            spent += 1

        return {"requested_churn": len(to_del) + len(to_ins) + len(to_upd),
                "spent": spent, "installed": len(self.entries),
                "truncated": spent >= budget and
                             (len(to_del) + len(to_ins) + len(to_upd)) > spent}

    def lookup(self, pair: Pair, bits: float, view: int) -> bool:
        """XDP fast path. Hit iff a live entry covers the requested bits."""
        e = self.entries.get(pair)
        if e is None or e.expired(view) or e.bits + 1e-9 < bits:
            self.stats.misses += 1
            return False
        self.stats.hits += 1
        self.stats.bits_served_fast += bits
        e.bits -= bits
        if e.bits <= 1e-9:
            self.entries.pop(pair, None)
            self._lru = [x for x in self._lru if x != pair]
        else:
            # touching an entry refreshes its LRU position
            self._lru = [x for x in self._lru if x != pair] + [pair]
        return True
