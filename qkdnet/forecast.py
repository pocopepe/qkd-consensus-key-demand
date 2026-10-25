"""Demand forecasters for the next consensus view."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .consensus import BFTConsensus, Pair, pkey

# A forecast is a predicted bit-demand per pair plus a per-pair confidence in
# (0,1], which the allocator turns into an expected benefit (proposal Eq. 2).
Forecast = dict[Pair, tuple[float, float]]


class Forecaster:
    name = "base"

    def observe(self, view: int, demand: dict[Pair, float], meta: dict) -> None:
        raise NotImplementedError

    def predict(self, view: int) -> Forecast:
        raise NotImplementedError


# --------------------------------------------------------------------------
# Baselines
# --------------------------------------------------------------------------

class EWMAPairForecaster(Forecaster):
    """d_hat(t+1) = a*d(t) + (1-a)*d_hat(t), per pair. Proposal Eq. (1)."""
    name = "ewma"

    def __init__(self, alpha: float = 0.3, err_alpha: float = 0.2):
        self.alpha = alpha
        self.err_alpha = err_alpha
        self.dhat: dict[Pair, float] = {}
        self.err: dict[Pair, float] = {}
        self._last_pred: dict[Pair, float] = {}

    def observe(self, view: int, demand: dict[Pair, float], meta: dict) -> None:
        seen = set(self.dhat) | set(demand)
        for p in seen:
            obs = demand.get(p, 0.0)
            pred = self._last_pred.get(p, self.dhat.get(p, 0.0))
            e = abs(obs - pred)
            self.err[p] = self.err_alpha * e + (1 - self.err_alpha) * self.err.get(p, e)
            self.dhat[p] = self.alpha * obs + (1 - self.alpha) * self.dhat.get(p, obs)

    def _confidence(self, p: Pair, mag: float) -> float:
        """p_v in (0,1], shrinking as the recent |d - d_hat| grows relative to d_hat."""
        e = self.err.get(p, 0.0)
        return float(np.clip(1.0 / (1.0 + e / max(mag, 1.0)), 1e-3, 1.0))

    def predict(self, view: int) -> Forecast:
        out: Forecast = {}
        for p, m in self.dhat.items():
            if m <= 0.0:
                continue
            out[p] = (m, self._confidence(p, m))
        self._last_pred = {p: m for p, (m, _) in out.items()}
        return out


class HoltForecaster(Forecaster):
    """Holt linear-trend smoothing per pair: level + slope. Stronger baseline."""
    name = "holt"

    def __init__(self, alpha: float = 0.4, beta: float = 0.2, err_alpha: float = 0.2):
        self.alpha, self.beta, self.err_alpha = alpha, beta, err_alpha
        self.level: dict[Pair, float] = {}
        self.trend: dict[Pair, float] = {}
        self.err: dict[Pair, float] = {}
        self._last_pred: dict[Pair, float] = {}

    def observe(self, view: int, demand: dict[Pair, float], meta: dict) -> None:
        for p in set(self.level) | set(demand):
            obs = demand.get(p, 0.0)
            pred = self._last_pred.get(p, self.level.get(p, obs))
            e = abs(obs - pred)
            self.err[p] = self.err_alpha * e + (1 - self.err_alpha) * self.err.get(p, e)
            l_prev = self.level.get(p, obs)
            t_prev = self.trend.get(p, 0.0)
            lvl = self.alpha * obs + (1 - self.alpha) * (l_prev + t_prev)
            self.trend[p] = self.beta * (lvl - l_prev) + (1 - self.beta) * t_prev
            self.level[p] = lvl

    def predict(self, view: int) -> Forecast:
        out: Forecast = {}
        for p, l in self.level.items():
            m = max(0.0, l + self.trend.get(p, 0.0))
            if m <= 0.0:
                continue
            e = self.err.get(p, 0.0)
            conf = float(np.clip(1.0 / (1.0 + e / max(m, 1.0)), 1e-3, 1.0))
            out[p] = (m, conf)
        self._last_pred = {p: m for p, (m, _) in out.items()}
        return out


# --------------------------------------------------------------------------
# Contribution: protocol-structural forecasting
# --------------------------------------------------------------------------

@dataclass
class _LeaderStats:
    """Beta-Bernoulli posterior over 'this leader's view times out'."""
    timeouts: float = 0.0
    views: float = 0.0
    prior_a: float = 1.0
    prior_b: float = 4.0

    def hazard(self) -> float:
        a = self.prior_a + self.timeouts
        b = self.prior_b + (self.views - self.timeouts)
        return a / (a + b)

    def concentration(self) -> float:
        return self.prior_a + self.prior_b + self.views


class StructuralForecaster(Forecaster):
    """Forecast next view's demand from the consensus state machine."""
    name = "structural"

    def __init__(self, consensus: BFTConsensus, use_hazard: bool = True,
                 use_schedule: bool = True, horizon: int = 1):
        self.c = consensus
        self.use_hazard = use_hazard
        self.use_schedule = use_schedule
        # How many views ahead to pre-arm. horizon=1 arms only the imminent view;
        # larger horizons buy lead time -- the quantity the proposal identifies as
        self.horizon = max(1, horizon)
        self.stats: dict[int, _LeaderStats] = {}
        self.global_stats = _LeaderStats()
        self._tag = consensus.cfg.tag_bits
        self._msg = consensus.cfg.tag_bits + (
            consensus.cfg.payload_bits if consensus.cfg.payload_keyed else 0.0)

    def observe(self, view: int, demand: dict[Pair, float], meta: dict) -> None:
        leader = meta["leader"]
        timed_out = float(meta["view_change"])
        st = self.stats.setdefault(leader, _LeaderStats())
        st.views += 1
        st.timeouts += timed_out
        self.global_stats.views += 1
        self.global_stats.timeouts += timed_out

    def _hazard(self, view: int, now: int) -> float:
        if not self.use_hazard:
            return self.global_stats.hazard()
        ld = self.c.leader_known_at(view, now)
        if ld is None:
            return self.global_stats.hazard()
        st = self.stats.get(ld)
        if st is None or st.views < 1:
            return self.global_stats.hazard()
        return st.hazard()

    def _star(self, centre: int, out: dict[Pair, list[float]], bits: float,
              weight: float) -> None:
        for j in range(self.c.cfg.n):
            if j == centre:
                continue
            p = pkey(centre, j)
            acc = out.setdefault(p, [0.0, 0.0])
            acc[0] += bits * weight
            acc[1] = max(acc[1], weight)

    def predict(self, view: int) -> Forecast:
        """Predict demand of `view`, standing at the end of view-1."""
        n = self.c.cfg.n
        now = view - 1
        h = float(np.clip(self._hazard(view, now), 0.0, 1.0))

        acc: dict[Pair, list[float]] = {}

        # --- happy-path branch, weight (1-h) ---
        if self.use_schedule:
            l1 = self.c.leader_known_at(view, now)
            l2 = self.c.leader_known_at(view + 1, now)
        else:
            l1 = l2 = None

        extra = []
        for k in range(1, self.horizon):
            lk_ = self.c.leader_known_at(view + 1 + k, now)
            if lk_ is not None:
                extra.append(lk_)

        if l1 is not None:
            self._star(l1, acc, self._msg, 1.0 - h)
        else:
            # schedule not yet committed: uniform prior over which validator leads
            for c in range(n):
                self._star(c, acc, self._msg, (1.0 - h) / n)
        if l2 is not None:
            self._star(l2, acc, self._msg, 1.0 - h)
        else:
            for c in range(n):
                self._star(c, acc, self._msg, (1.0 - h) / n)

        # --- lookahead branch: stars for views beyond the next one ---
        for c_ in extra:
            self._star(c_, acc, self._msg, 1.0 - h)

        # --- view-change branch, weight h: all-to-all ---
        if h > 0.0:
            for i in range(n):
                for j in range(i + 1, n):
                    a = acc.setdefault((i, j), [0.0, 0.0])
                    a[0] += self._tag * h
                    a[1] = max(a[1], h)

        return {p: (m, float(np.clip(w, 1e-3, 1.0))) for p, (m, w) in acc.items() if m > 0.0}


class OracleForecaster(Forecaster):
    """Perfect knowledge of the next view. Upper bound for every policy."""
    name = "oracle"

    def __init__(self, future: list[dict[Pair, float]]):
        self.future = future

    def observe(self, view: int, demand: dict[Pair, float], meta: dict) -> None:
        pass

    def predict(self, view: int) -> Forecast:
        if view >= len(self.future):
            return {}
        return {p: (b, 1.0) for p, b in self.future[view].items()}


def forecast_error(pred: Forecast, actual: dict[Pair, float],
                   topk: int | None = None) -> dict[str, float]:
    """Decision-relevant forecast metrics."""
    pairs = set(pred) | set(actual)
    if not pairs:
        return {"mae": 0.0, "coverage": 1.0, "precision": 1.0,
                "wasted_mass": 0.0, "support_recall": 1.0, "jaccard": 1.0}
    errs = [abs(pred.get(p, (0.0, 0.0))[0] - actual.get(p, 0.0)) for p in pairs]
    thr = 1e-9
    ps = {p for p in pred if pred[p][0] > thr}
    as_ = {p for p in actual if actual[p] > thr}
    total_bits = sum(actual.values()) or 1.0
    pred_mass = sum(pred[p][0] for p in ps) or 1.0
    wasted = sum(pred[p][0] for p in ps - as_) / pred_mass

    K = topk if topk is not None else len(as_)
    ranked = sorted(ps, key=lambda p: -pred[p][0])[:K]
    covered = sum(actual.get(p, 0.0) for p in ranked)
    hitk = sum(1 for p in ranked if p in as_)
    return {
        "mae": float(np.mean(errs)),
        "coverage": covered / total_bits,
        "precision": hitk / max(len(ranked), 1),
        "wasted_mass": wasted,
        "support_recall": len(ps & as_) / (len(as_) or 1),
        "jaccard": len(ps & as_) / (len(ps | as_) or 1),
    }


# --------------------------------------------------------------------------
# Group structure: the round is a max, not a sum
# --------------------------------------------------------------------------

@dataclass
class DemandGroup:
    """A set of pairs that a consensus round needs *together*."""
    name: str
    pairs: dict[Pair, float]
    prob: float
    quorum: int = 0        # 0 means "all pairs"; else the 2f+1 threshold
    # Blocks belonging to one scenario are perfectly correlated: either the
    # scenario occurs and every one of its blocks is needed, or it does not and
    # none are. Scoring them independently makes partial coverage of the
    # view-change fabric look valuable when it is worth nothing.
    scenario: str = "happy"

    def need(self) -> int:
        return self.quorum if 0 < self.quorum <= len(self.pairs) else len(self.pairs)


def default_groups(pred: Forecast) -> list[DemandGroup]:
    """Degenerate grouping for forecasters with no protocol model: every pair is
    its own group, which recovers the additive objective exactly."""
    return [DemandGroup(f"pair{p}", {p: b}, c, 1) for p, (b, c) in pred.items()]


def _structural_groups(self: "StructuralForecaster", view: int) -> list[DemandGroup]:
    n = self.c.cfg.n
    q = self.c.quorum_pairs
    now = view - 1
    h = float(np.clip(self._hazard(view, now), 0.0, 1.0))
    groups: list[DemandGroup] = []

    def star(centre: int) -> dict[Pair, float]:
        return {pkey(centre, j): self._msg for j in range(n) if j != centre}

    if self.use_schedule:
        l1 = self.c.leader_known_at(view, now)
        l2 = self.c.leader_known_at(view + 1, now)
    else:
        l1 = l2 = None

    if l1 is not None:
        groups.append(DemandGroup(f"propose@{l1}", star(l1), 1.0 - h, q, "happy"))
    if l2 is not None:
        groups.append(DemandGroup(f"vote->{l2}", star(l2), 1.0 - h, q, "happy"))
    if l1 is None or l2 is None:
        for c in range(n):
            groups.append(DemandGroup(f"maybe@{c}", star(c), (1.0 - h) / n, q, f"maybe{c}"))

    for k in range(1, getattr(self, "horizon", 1)):
        lk_ = self.c.leader_known_at(view + 1 + k, now)
        if lk_ is not None:
            # discounted: the further ahead, the more likely a view change
            # reshuffles the schedule before it is reached
            groups.append(DemandGroup(f"ahead+{k}@{lk_}", star(lk_),
                                      (1.0 - h) ** (k + 1), q, f"ahead{k}"))

    if h > 1e-6:
        # the O(n^2) view-change fabric decomposes into n fan-in blocks, each of
        # which needs only a quorum -- so it is hedgeable at O(n*q) entries
        for i in range(n):
            vc = {pkey(i, j): self._tag for j in range(n) if j != i}
            groups.append(DemandGroup(f"newview->{i}", vc, h, q, "view_change"))
    return groups


StructuralForecaster.groups = _structural_groups
Forecaster.groups = lambda self, view: default_groups(self.predict(view))
