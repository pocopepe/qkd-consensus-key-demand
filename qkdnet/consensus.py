"""Chained-HotStuff-style BFT state machine that *generates* pairwise key
demand."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

Pair = tuple[int, int]


def pkey(a: int, b: int) -> Pair:
    return (a, b) if a < b else (b, a)


class Phase(Enum):
    HAPPY = "happy"
    VIEW_CHANGE = "view_change"


@dataclass
class DemandBlock:
    """One protocol step's worth of pairwise demand, plus how many of its pairs
    must actually complete for the step to make progress."""
    name: str
    pairs: dict[Pair, float]
    quorum: int          # pairs that must complete; len(pairs) means all


@dataclass
class ViewOutcome:
    view: int
    leader: int
    next_leader: int
    phase: Phase
    demand: dict[Pair, float]      # pairwise key demand, bits
    blocks: list[DemandBlock]
    committed: bool
    deadline_s: float


@dataclass
class ConsensusConfig:
    n: int = 16
    tag_bits: float = 256.0        # Wegman-Carter tag per authenticated message
    payload_keyed: bool = False    # if True, OTP-encrypt proposals (much heavier)
    payload_bits: float = 4096.0
    view_period_s: float = 0.25
    deadline_s: float = 0.25
    # leader schedule
    schedule: str = "round_robin"  # round_robin | vrf
    lookahead: int = 4             # how many views ahead the schedule is public
    # faults
    byzantine: tuple[int, ...] = ()
    timeout_prob: float = 0.03     # spontaneous timeouts (network asynchrony)
    seed: int = 0


class BFTConsensus:
    """Generates a stream of ViewOutcomes with pairwise key demand."""

    def __init__(self, cfg: ConsensusConfig):
        self.cfg = cfg
        self.rng = np.random.default_rng(cfg.seed)
        self._sched_rng = np.random.default_rng(cfg.seed + 9999)
        self.view = 0
        self._sched: list[int] = []
        self._extend_schedule(256)

    # ---- leader schedule ------------------------------------------------

    def _extend_schedule(self, k: int) -> None:
        n = self.cfg.n
        if self.cfg.schedule == "round_robin":
            start = len(self._sched)
            self._sched.extend([(start + i) % n for i in range(k)])
        else:  # vrf: unpredictable beyond the published lookahead window
            self._sched.extend(int(x) for x in self._sched_rng.integers(0, n, k))

    def leader(self, view: int) -> int:
        while view >= len(self._sched):
            self._extend_schedule(256)
        return self._sched[view]

    def leader_known_at(self, view: int, now_view: int) -> int | None:
        """Leader of `view` as visible to a forecaster standing at `now_view`."""
        if self.cfg.schedule == "round_robin":
            return self.leader(view)
        return self.leader(view) if view - now_view <= self.cfg.lookahead else None

    # ---- demand generation ----------------------------------------------

    def _msg_bits(self) -> float:
        b = self.cfg.tag_bits
        if self.cfg.payload_keyed:
            b += self.cfg.payload_bits
        return b

    @property
    def f(self) -> int:
        return (self.cfg.n - 1) // 3

    @property
    def quorum_pairs(self) -> int:
        """Pairs of a star that must complete: 2f+1 participants, one of which
        is the star's centre itself, so 2f pairs."""
        return min(2 * self.f, self.cfg.n - 1)

    def happy_blocks(self, view: int) -> list[DemandBlock]:
        n, ld, nxt = self.cfg.n, self.leader(view), self.leader(view + 1)
        bits = self._msg_bits()
        q = self.quorum_pairs
        propose = {pkey(ld, j): bits for j in range(n) if j != ld}
        vote = {pkey(j, nxt): bits for j in range(n) if j != nxt}
        return [DemandBlock(f"propose@{ld}", propose, q),
                DemandBlock(f"vote->{nxt}", vote, q)]

    def happy_demand(self, view: int) -> dict[Pair, float]:
        """O(n) steady state: propose fan-out + vote fan-in to the next leader."""
        d: dict[Pair, float] = {}
        for blk in self.happy_blocks(view):
            for p, b in blk.pairs.items():
                d[p] = d.get(p, 0.0) + b
        return d

    def view_change_blocks(self, view: int) -> list[DemandBlock]:
        """All-to-all NEW-VIEW. Each replica needs 2f+1 NEW-VIEW messages, so
        each replica's fan-in is its own quorum block. The union is O(n^2) pairs
        but no single block needs more than 2f of them."""
        n, bits = self.cfg.n, self.cfg.tag_bits
        q = self.quorum_pairs
        return [DemandBlock(f"newview->{i}",
                            {pkey(i, j): bits for j in range(n) if j != i}, q)
                for i in range(n)]

    def view_change_demand(self, view: int) -> dict[Pair, float]:
        """All-to-all NEW-VIEW: O(n^2) pairs, each carrying a tag."""
        n, bits = self.cfg.n, self.cfg.tag_bits
        return {pkey(i, j): bits for i in range(n) for j in range(i + 1, n)}

    def step(self) -> ViewOutcome:
        cfg = self.cfg
        v = self.view
        ld, nxt = self.leader(v), self.leader(v + 1)
        faulty_leader = ld in cfg.byzantine
        timed_out = faulty_leader or (self.rng.random() < cfg.timeout_prob)
        if timed_out:
            phase, committed = Phase.VIEW_CHANGE, False
            blocks = self.view_change_blocks(v)
            demand = self.view_change_demand(v)
        else:
            phase, committed = Phase.HAPPY, True
            blocks = self.happy_blocks(v)
            demand = self.happy_demand(v)
        self.view += 1
        return ViewOutcome(view=v, leader=ld, next_leader=nxt, phase=phase,
                           demand=demand, blocks=blocks, committed=committed,
                           deadline_s=cfg.deadline_s)

    # ---- ground truth for the structural forecaster ----------------------

    def view_change_hazard(self, view: int, now_view: int) -> float:
        """P(view `view` times out), as estimable by the control plane."""
        ld = self.leader_known_at(view, now_view)
        if ld is None:
            return self.cfg.timeout_prob + len(self.cfg.byzantine) / self.cfg.n
        return 1.0 if ld in self.cfg.byzantine else self.cfg.timeout_prob


def per_validator(demand: dict[Pair, float]) -> dict[int, float]:
    """Collapse pairwise demand to the per-validator vector d_v(t) of the proposal."""
    out: dict[int, float] = {}
    for (a, b), bits in demand.items():
        out[a] = out.get(a, 0.0) + bits
        out[b] = out.get(b, 0.0) + bits
    return out
