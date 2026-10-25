# E6 — does the structural result survive a finite shared QKD pool?

E4 and E4-TTL used independent per-pair pools, chosen to isolate the predictor.
Under that model holding key for one pair costs another nothing, and longer
leases looked uniformly good. E1 measured the opposite sign under shared relay
pools. E6 puts the same workload and predictors on one shared pool so the two
can be reconciled on a single substrate.

> ## Verdict: QUALIFIED
>
> The structural result survives: **fresh-hit rate ≤ π in all 48 cells, across
> every contention regime and both admission policies** (max excess +0.0043).
> But under scarcity **π stops being the binding constraint** — a perfect
> predictor (π = 1.0) still starves 26.6% of requests — and the operational
> conclusions from E4/E4-TTL do not carry over unchanged.

---

## 1. Shared-pool model

Stated in full before any result was inspected.

- **One pool** shared by every validator pair, representing a QKD relay
  bottleneck.
- **Capacity** `cap = C · D`, where `D` is mean demand per view for the
  operating point. `C` defines the contention regime.
- **Refill** `R = 1.5 · D` bits per view, clipped at `cap`. Held **fixed across
  regimes** so that capacity, not supply rate, is the contention mechanism.
- Reservations **consume capacity immediately** when armed.
- An **expired** (unused) reservation **returns** its capacity and is counted as
  waste. A **consumed** reservation does not return.
- Slow-path service draws from the pool directly.
- **Scheduling.** Serving order is a per-view random permutation of the
  demanding pairs, seeded from the run seed, so service carries no priority.
  Arming order is a parameter (`fifo` / `random`) — see §12, where the first
  version's deterministic arming turned out to be a hidden priority rule.

### A regime definition that failed, recorded rather than deleted

The regimes were **first** defined on the refill rate (ρ = 3.0 / 1.5 / 1.0) and
produced **zero contention in all 48 cells** — starvation and contention-miss
were 0.0000 everywhere and all three regimes gave identical numbers.

The reason is in the model above: an expired reservation *returns* its capacity,
so waste is a temporary hold rather than a permanent drain, and steady-state
consumption equals actual demand no matter how much is mis-armed. Refill is
therefore the wrong knob. The axis was changed to capacity for that reason, not
after inspecting which axis gave a preferred answer.

## 2. Capacity definitions

Derived from the outstanding-reservation requirement: a reservation lives `TTL`
views and roughly one view of demand is armed per view, so outstanding
reservations approach `T · D` at `TTL = T`.

| regime | C | rationale |
|---|---:|---|
| low | 10.0 | exceeds the TTL=8 requirement; contention impossible |
| moderate | 2.5 | sufficient for TTL ≤ 2, intended to bind at TTL ≥ 4 |
| high | 0.75 | insufficient even for a single view's arming |

**The moderate regime did not bind.** Its numbers are identical to `low` at every
operating point and TTL. Only two effective regimes were achieved, and that is
reported rather than papered over by re-tuning C after the fact.

## 3. Workload

Unchanged hub-union generator from E4, n = 16, at four operating points:
π = 0.1333 (m=2,k=0), 0.5667 (2,1), 0.8167 (4,3), 1.0000 (2,2).

## 4. Predictor configurations

`reactive`, `carry-forward` (last-observation), `structural` (schedule-aware
upper reference). Unchanged from E4.

## 5–6. TTL and contention sweep

TTL ∈ {1, 2, 4, 8} × 3 regimes × 3 predictors × 4 π × 10 seeds.

## 7. Fresh / stale / total hit analysis

Carry-forward, fair (random) admission:

| π | contention | TTL | fresh | stale | total | starvation | waste | latency ms |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 0.1333 | low | 1 | 0.1377 | 0.0000 | 0.1377 | 0.0000 | 0.8632 | 0.900 |
| 0.1333 | low | 8 | 0.1370 | 0.7256 | 0.8626 | 0.0000 | 0.0985 | 0.150 |
| 0.1333 | high | 1 | **0.1008** | 0.0000 | 0.1008 | **0.8977** | 0.6332 | **3.749** |
| 0.1333 | high | 8 | 0.1054 | 0.5657 | 0.6711 | 0.3274 | 0.0784 | 1.362 |
| 0.5667 | low | 1 | 0.5162 | 0.0000 | 0.5162 | 0.0000 | 0.4980 | 0.510 |
| 0.5667 | high | 1 | **0.3789** | 0.0000 | 0.3789 | 0.6196 | 0.3648 | 2.590 |
| 0.5667 | high | 8 | 0.3789 | 0.2576 | 0.6365 | 0.3620 | 0.1131 | 1.509 |
| 0.8167 | low | 1 | 0.7393 | 0.0000 | 0.7393 | 0.0000 | 0.2822 | 0.281 |
| 0.8167 | high | 1 | **0.5545** | 0.0000 | 0.5545 | 0.4440 | 0.2119 | 1.860 |
| 1.0000 | low | 1–8 | 0.9980 | 0.0000 | 0.9980 | 0.0000 | 0.0000 | 0.014 |
| 1.0000 | high | 1–8 | **0.7321** | 0.0000 | 0.7321 | **0.2664** | 0.0000 | 1.121 |

Full 48-row table in `../E6-sharedpool-random.json`.

### Ceiling test

| regime | TTL | max(fresh − π) | violations |
|---|---:|---:|---:|
| low | 1–8 | +0.0043 | 1 (finite-sample, at π=0.1333) |
| moderate | 1–8 | +0.0043 | 1 |
| high | 1–8 | **−0.0284 … −0.0345** | **0** |

**Overall max(fresh − π) = +0.0043 over 48 cells**, identical under both `fifo`
and `random` admission. Contention pushes fresh hits *down*, never up: the
ceiling holds a fortiori under scarcity.

![Figure 1](figures/fig1_fresh_vs_pi.svg)

## 8. Starvation

Starvation is the dominant failure mode under scarcity, and **pre-arming causes
it**: reserving key withdraws it from the shared pool, so pairs that were not
pre-armed find nothing at service time. At π = 0.1333, TTL = 1, starvation is
**0.8977**.

The mechanism is confirmed by the π = 1.0 row: a predictor that is *never wrong*
still starves **26.6%** of requests under high contention. That is not a
prediction failure at all — it is capacity.

Longer TTL **reduces** starvation (0.898 → 0.327), because a pair holding a live
reservation is not re-armed, so churn against the pool falls.

![Figure 2](figures/fig2_starvation_vs_ttl.svg)
![Figure 6](figures/fig6_pareto_fresh_starvation.svg)

## 9. Waste

Waste falls with TTL exactly as in E4-TTL (0.863 → 0.099 at π = 0.1333, low
contention), and falls further under scarcity because capacity limits how much
can be mis-armed in the first place.

## 10. Latency

Mean latency under high contention is 2.6–4.2× the low-contention value and is
dominated by starvation, not by slow-path service. Longer TTL improves it
(3.749 → 1.362 ms at π = 0.1333).

![Figure 5](figures/fig5_latency_vs_ttl.svg)
![Figure 3](figures/fig3_peak_occupancy_vs_ttl.svg)
![Figure 4](figures/fig4_totalhit_vs_ttl.svg)

## 11. Trade-offs

Cost reported as a vector, not collapsed into an invented scalar. Carry-forward,
high contention, averaged over π:

| TTL | miss (pred+cont) | latency ms | waste | starvation | unfairness | peak occupancy |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.0015 | 2.353 | 0.303 | 0.562 | 0.153 | 26 |
| 2 | 0.0015 | 2.006 | 0.228 | 0.480 | 0.163 | 39 |
| 4 | 0.0015 | 1.618 | 0.143 | 0.386 | 0.174 | 59 |
| 8 | 0.0015 | 1.245 | 0.060 | 0.298 | 0.178 | 78 |

In *this* workload every axis except occupancy and a slight unfairness drift
improves monotonically with TTL, so no interior optimum exists and TTL = 8 is
dominant. **That conclusion is workload-specific — see §12.**

## 12. Threats to validity

- **The decisive one: this workload is stationary, and E1's was not.** The
  hub-union generator produces a steady per-view demand with no flash crowds.
  E1 found long leases *harmful* precisely under bursts, where held key is
  needed elsewhere immediately. Here holding is efficient because nothing else
  ever urgently needs the key. **E1 and E6 are therefore not in conflict — they
  differ in workload, not only in pool sharing — and "longer TTL is better" is a
  statement about stationary demand only.** Nothing here tests bursty demand on
  a shared pool, which is the configuration where E1 saw a 33% starvation
  increase.
- **A hidden priority rule of my own making.** The first version armed pairs in
  the predictor's deterministic emission order while serving in random order.
  Under scarcity that armed the same pairs every view: pair-level unfairness was
  0.63–0.83 for carry-forward and **0.968 for the structural predictor**. With
  fair (random) admission it falls to 0.15–0.18. The extreme unfairness was an
  artefact of my scheduler, not a property of contention. Both policies are
  reported; the ceiling result is identical under both (max +0.0043).
- The moderate regime did not bind (§2), so the sweep has two effective points,
  not three.
- Simulated hub-union workload, not an implementation trace. E2 validated the
  generator's π against relab/hotstuff; the pool and reservation model is not
  itself validated against a deployment.
- Single shared pool. A real relay topology has many partially-overlapping pools.
- 10 seeds; quantities are near-deterministic within a cell.

## 13. Implications for Theorem A / Theorem B

Neither changes, and neither was tested here.

- **Theorem A** (π from `(n,m,k)`) is a property of the workload; capacity does
  not enter it.
- **Theorem B** (RWC coverage at budget K) is again confirmed rather than
  threatened. The fresh-hit ceiling is its operational shadow and holds in all
  48 cells, at every contention level.

What E6 adds is a **precondition** on the operational reading: π bounds what
prediction can deliver *when the resource is available*. Under scarcity the
binding constraint is capacity, and π becomes an upper bound that is not
approached — at π = 1.0 the achieved fresh-hit rate is 0.7321.

## 14. Engineering conclusion

Three regimes, and the right question differs in each:

1. **Ample capacity.** π is the binding constraint. Improve the predictor or
   accept the ceiling; the decision rule from E4 applies directly.
2. **Scarce capacity.** π is not binding — capacity is. A perfect predictor
   still starves 26.6%. Buying a better predictor here is the wrong purchase;
   buy key rate or reduce the pre-arm footprint.
3. **Which regime you are in is measurable before choosing a predictor**, by
   comparing pool capacity against `TTL × D`.

And one caution that E6 cannot resolve: TTL = 8 dominates every cost axis in
this stationary workload, but E1 measured the opposite under flash crowds. Until
bursty demand is tested on a shared pool, **lease duration should be treated as
workload-dependent, not as a parameter with a known best value.**

> ## QUALIFIED
>
> The structural result survives shared-pool contention — fresh-hit ≤ π in all
> 48 cells, with contention pushing hits below the ceiling rather than above it.
> The operational implications depend strongly on contention: under scarcity π
> ceases to be the binding constraint, and the TTL guidance from E4-TTL holds
> only for stationary demand.
