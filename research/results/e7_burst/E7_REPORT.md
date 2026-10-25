# E7 — burstiness × TTL × shared QKD capacity

E6 found TTL = 8 dominant on a stationary workload with a shared pool. E1 found
the opposite — long leases harmful — under flash crowds. E7 puts E1's own burst
generator on E6's own pool, holding everything else fixed, to test whether
workload dynamics explains the difference.

> ## Verdict: INTERACTION NOT CONFIRMED
>
> TTL* differs between stationary and bursty demand in only **2 of 14**
> metric × capacity comparisons, and both are in the ample-capacity regime where
> starvation is essentially zero (0.0000 vs 0.0570). The sign of the TTL effect
> on starvation is **the same in every arm**: longer leases reduce starvation by
> −0.24 to −0.29 under scarcity.
>
> **Burstiness does not explain the E1/E6 discrepancy.** §5 identifies what does.

---

## 1. Workload definitions

| | |
|---|---|
| **W1 stationary** | E6 hub-union generator, unchanged. Demand multiplier 1.0 every view. |
| **W2 bursty** | Identical support; per-view demand multiplier drawn from E1's `BurstyWorkload` (`simulator/engine.py`), unchanged. Measured over 200k draws: **8.67% of views carry a 6× multiplier, mean multiplier 1.4336**. |

The burst raises **magnitude per pair**, not support. The set of pairs demanding
key in a view is identical between W1 and W2 for the same seed.

**W2n bursty mean-matched** — a diagnostic arm, not part of the specified
matrix. W2 carries 1.4336× W1's mean load, so a TTL reversal under W2 could be
caused by higher mean load rather than by burstiness. W2n divides the multiplier
by its mean so mean load matches W1 exactly and only variance differs. Reported
separately in §6.

## 2. Shared-pool model

Unchanged from E6: one shared pool, capacity `C · D`, refill `1.5 · D` per view,
reservations consume immediately, expired reservations return capacity and count
as waste, random admission and random service order. Full specification in
`../e6_shared_pool/E6_REPORT.md` §1.

Capacities fixed in advance and not retuned: **ample C = 10.0**, **scarce
C = 0.75**.

## 3. Experimental matrix

3 workload arms × 2 capacities × 4 TTLs × 2 predictors × 4 π × 10 seeds.
Pool capacity, refill rate, predictors, n = 16, seeds, and demand normalisation
are identical across workloads; only the burst multiplier differs.

## 4. Results

Carry-forward predictor, averaged over π:

| workload | capacity | TTL | fresh | total | starvation | waste | latency ms | occupancy |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| stationary | ample | 1 | 0.5980 | 0.5980 | 0.0000 | 0.4111 | 0.426 | 35 |
| stationary | ample | 8 | 0.5617 | 0.8756 | 0.0000 | 0.0737 | 0.139 | 89 |
| stationary | scarce | 1 | 0.4417 | 0.4417 | 0.5570 | 0.3026 | 2.330 | 27 |
| stationary | scarce | 8 | 0.4505 | 0.7038 | **0.2950** | 0.0597 | 1.234 | 77 |
| bursty | ample | 1 | 0.5621 | 0.5621 | 0.0570 | 0.4002 | 0.648 | 35 |
| bursty | ample | 8 | 0.5067 | 0.7996 | 0.0495 | 0.0745 | 0.380 | 89 |
| bursty | scarce | 1 | 0.4023 | 0.4023 | 0.5945 | 0.2182 | 2.493 | 27 |
| bursty | scarce | 8 | 0.4098 | 0.6458 | **0.3507** | 0.0538 | 1.476 | 78 |

Full 96-row table in `../E7-burst-001.json`.

### The ceiling still holds

| workload | max(fresh − π) | cells |
|---|---:|---:|
| stationary | +0.0044 | 32 |
| bursty | **+0.0013** | 32 |
| bursty mean-matched | +0.0018 | 32 |

Bursty demand does not lift fresh hits above π; if anything the bound is tighter.

## 5. TTL × workload interaction

**TTL\* per metric**, argmin/argmax over TTL ∈ {1,2,4,8}:

| workload | capacity | starve | waste | lat mean | lat p95 | occupancy | fresh | total |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| stationary | ample | 1 | 8 | 8 | 1 | 1 | 1 | 8 |
| stationary | scarce | 8 | 8 | 8 | 1 | 1 | 8 | 8 |
| bursty | ample | **8** | 8 | 8 | **8** | 1 | 1 | 8 |
| bursty | scarce | 8 | 8 | 8 | 1 | 1 | 8 | 8 |

**TTL\* differs in 2 of 14 comparisons**, both in the ample regime. In that
regime stationary starvation is exactly 0.0000 at every TTL, so "TTL\* = 1" is an
artefact of ties among zeros rather than a preference.

**Direction of the TTL effect on starvation** — the quantity E1 measured:

| workload | capacity | TTL=1 | TTL=2 | TTL=4 | TTL=8 | 1 → 8 |
|---|---|---:|---:|---:|---:|---:|
| stationary | scarce | 0.5570 | 0.4757 | 0.3828 | 0.2950 | **−0.2621** |
| bursty | scarce | 0.5945 | 0.5214 | 0.4351 | 0.3507 | **−0.2438** |
| bursty matched | scarce | 0.4077 | 0.3075 | 0.2049 | 0.1206 | **−0.2871** |
| bursty | ample | 0.0570 | 0.0581 | 0.0540 | 0.0495 | −0.0075 |

**The sign is negative in every arm.** Longer leases reduce starvation whether
demand is stationary or bursty. E1 measured the opposite sign.

### What actually explains the E1 discrepancy

Not burstiness. The difference is in how a reservation consumes key.

In E1 (`qkdnet/topology.py`), a reservation for a pair `h` hops apart withdraws
the full amount **on every hop of the relay path**:

```python
def reserve(self, src, dst, bits):
    for lk in self.path_links(src, dst):
        lk.reserved_bits += bits
```

So an `h`-hop reservation locks `h × bits` and blocks `h` distinct links, each
of which other pairs' paths may cross. A longer lease multiplies that blocking
across time *and* across the topology.

In E6/E7 there is one fungible pool, so a reservation locks exactly `bits` and
blocks nobody in particular. The amplification is absent by construction.

This is a candidate mechanism identified from the code, **not tested here**. The
appropriate next experiment is multi-hop reservation amplification on a shared
relay topology, holding burstiness fixed — the converse of E7.

## 6. Capacity interaction, and the mean-load control

Capacity dominates burstiness. Under `ample` capacity, starvation is ≤ 0.058 in
every arm and TTL barely matters. Under `scarce`, starvation is 0.30–0.59 and
every metric improves with TTL.

The mean-load control separates variance from level (TTL = 1, scarce):

| metric | stationary | bursty | bursty mean-matched |
|---|---:|---:|---:|
| starvation | 0.5570 | 0.5945 | **0.4077** |
| latency ms | 2.330 | 2.493 | **1.765** |
| fresh hit | 0.4417 | 0.4023 | **0.5454** |

Removing the 1.43× mean-load increase improves every metric — so **most of
bursty's penalty is higher mean load, not burstiness**. Variance alone (matched
arm vs stationary) *helps* fresh hit (0.5454 vs 0.4417), because burst views
concentrate demand on pairs that are already armed. Neither effect changes the
TTL ordering.

## 7. Pareto analysis

Reported as a vector, not collapsed. Scarce capacity, averaged over π:

| workload | TTL | starvation | waste | latency ms | occupancy | fresh |
|---|---:|---:|---:|---:|---:|---:|
| stationary | 1 | 0.5570 | 0.3026 | 2.330 | 27 | 0.4417 |
| stationary | 8 | 0.2950 | 0.0597 | 1.234 | 77 | 0.4505 |
| bursty | 1 | 0.5945 | 0.2182 | 2.493 | 27 | 0.4023 |
| bursty | 8 | 0.3507 | 0.0538 | 1.476 | 78 | 0.4098 |

In both workloads TTL = 8 dominates TTL = 1 on starvation, waste, latency and
fresh hit, and is dominated only on occupancy (77–78 vs 27, a 2.9× increase).
**The Pareto frontier is one-dimensional here: occupancy against everything
else**, and it has the same shape under both workloads. There is no interior
optimum and no workload-dependent crossover.

![starvation](figures/fig_starve_vs_ttl.svg)
![waste](figures/fig_waste_vs_ttl.svg)
![latency](figures/fig_lat_mean_ms_vs_ttl.svg)
![occupancy](figures/fig_peak_occ_vs_ttl.svg)
![mean-load control](figures/fig_meanmatch_control.svg)

## 8. Threats to validity

- **The finding is a negative one, and negative results are weaker.** E7 shows
  burstiness *as generated by E1's own generator* does not reverse the TTL
  effect *on E6's single-pool model*. A different burst shape — longer, deeper,
  or correlated with the hub rotation — might. Only one generator was tested,
  unchanged, as instructed.
- **The identified mechanism (§5) is not tested.** Multi-hop reservation
  amplification is read off E1's source, not measured. It is a hypothesis for
  the next experiment, not a result of this one.
- Single shared pool; real relay topologies have many overlapping pools, which
  is precisely the structure §5 implicates.
- Bursts raise magnitude, not support. A burst that widened the support set
  would stress prediction differently and is not modelled.
- Simulated hub-union workload throughout; π was validated against
  relab/hotstuff in E2, the pool model was not.
- 10 seeds. Starvation CIs are recorded per row in the JSON.

## 9. Implications for engineering guidance

The E6 guidance survives, with its scope now measured rather than assumed:

1. **Under ample capacity**, TTL is nearly irrelevant — starvation ≤ 0.058 at
   every lifetime, in both workloads.
2. **Under scarce capacity**, longer leases help on every axis except
   occupancy, in both workloads. The trade is starvation/waste/latency against
   peak reservations, and it does not change shape when demand becomes bursty.
3. **Burstiness is not the reason to shorten a lease.** If E1's result is to be
   relied on, the reason must be the multi-hop relay structure, and that should
   be established directly before any short-lease recommendation is made for a
   relay deployment.

Lease duration should therefore still not be treated as having a globally
optimal value — but the dependence that has been demonstrated is on **capacity
and topology**, not on burstiness.

## 10. Final verdict

> ## INTERACTION NOT CONFIRMED

Burstiness, as generated by E1's unchanged flash-crowd model, does not reverse
or materially change the effect of reservation lifetime on a shared QKD pool.
TTL\* differs in 2 of 14 comparisons, both among ties at zero starvation, and the
sign of the TTL effect is negative in every arm.

The E1/E6 discrepancy is therefore **not** explained by workload dynamics. The
mechanism identified from E1's source — reservations that withdraw key on every
hop of a relay path, so that a long lease blocks `h` links at once — remains the
open candidate, and testing it is the natural successor to this experiment.
