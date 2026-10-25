# E8 — multi-hop reservation amplification

E7 ruled out burstiness as the explanation for the E1/E6 discrepancy. The
remaining candidate, read from E1's source, is the reservation accounting model.
E8 tests it.

> ## Verdict: MECHANISM PARTIALLY SUPPORTED
>
> Amplification systematically changes the TTL trade-off in the predicted
> direction. Under scarce capacity, `ΔS = S(TTL=8) − S(TTL=1)` rises
> **monotonically** toward zero as the factor grows — `−0.2621 → −0.1278 →
> −0.0588 → −0.0241` — and under **E1's actual relay topology it crosses zero**
> (`+0.0030`), reproducing E1's direction: longer leases stop helping and begin
> to hurt.
>
> The **magnitude** is not reproduced. E1 reported a 33% starvation increase
> from pre-arming; the sign flip here is `+0.003` to `+0.018`. The discrepancy
> is explained qualitatively, not quantitatively.

---

## 1. Resource models

| model | reservation locks | blocks |
|---|---|---|
| **A/B pool** | `amp × B` from one fungible pool, `amp ∈ {1,2,4,8}` | nobody in particular |
| **C topo** | `B` on **every hop** of the actual relay path | `h` specific links |

**Model A/B is an abstract amplification factor, not a topology.** It reproduces
E1's footprint arithmetic while deliberately omitting link specificity, so the
two halves of the mechanism can be separated.

**Model C imports E1's mechanism unchanged** from `qkdnet/topology.py`
(`ring_with_chords`, per-link pools, `reserve`/`release`/`consume` over
`path_links`). Here `h` is not chosen — the topology gives 39 links and a
**structural mean of 2.300 hops** over 120 pairs (distribution 1:28, 2:48, 3:29,
4:11, 5:3, 6:1).

**Capacity normalisation.** Model B has one pool of `C·D`. Model C is given the
same *aggregate* capacity spread over its links, `C·D/L` each, with refill
`1.5·D/L` each. A reservation therefore removes the same total from the same
budget in both; only the requirement that capacity sit on `h` *specific* links
differs.

## 2. Experimental setup

n = 16; the E6/E7 hub-union generator; π ∈ {0.1333, 0.5667, 0.8167, 1.0};
carry-forward and structural predictors; random admission and random service
order; refill `1.5·D`. Capacities `C = 0.75D` (primary) and `2.5D` (secondary
control), not retuned per `h`. TTL ∈ {1,2,4,8}. Workloads: stationary (E6) and
bursty (E7, E1's generator unchanged). 10 seeds.

## 3–4. Regression control

`amp = 1` must reproduce E6/E7 before anything at `amp > 1` is interpreted:

| workload | TTL=1 | TTL=2 | TTL=4 | TTL=8 |
|---|---|---|---|---|
| E8 amp=1, stationary | 0.5570 | 0.4757 | 0.3828 | 0.2950 |
| E7 stationary | 0.5570 | 0.4757 | 0.3828 | 0.2950 |
| E8 amp=1, bursty | 0.5945 | 0.5214 | 0.4351 | 0.3507 |
| E7 bursty | 0.5945 | 0.5214 | 0.4351 | 0.3507 |

**max |E8(amp=1) − E7| = 0.0000 — PASS.**

## 5–6. Central result

`Δ = metric(TTL=8) − metric(TTL=1)`. Negative means longer TTL helps.

**Stationary, scarce (C = 0.75D):**

| model | ΔS (starvation) | ΔW (waste) | ΔL (latency ms) | fresh @TTL=1 | armFail/view @TTL=1 |
|---|---:|---:|---:|---:|---:|
| pool amp=1 | −0.2621 | −0.2430 | −1.0956 | 0.4417 | 9.14 |
| pool amp=2 | −0.1278 | −0.2424 | −0.5338 | 0.2197 | 22.26 |
| pool amp=4 | −0.0588 | −0.2244 | −0.2458 | 0.1033 | 29.06 |
| pool amp=8 | −0.0241 | −0.1840 | −0.1005 | 0.0435 | 32.58 |
| **topo (E1)** | **+0.0030** | −0.0246 | **+0.0029** | 0.0503 | 31.35 |

**Bursty, scarce:** −0.2438 → −0.1181 → −0.0531 → −0.0215, topo **+0.0035**.

### Monotonicity

| workload / capacity | ΔS across amp = 1,2,4,8 | monotone ↑ | topo |
|---|---|---|---|
| stationary / scarce | −0.2621 −0.1278 −0.0588 −0.0241 | **yes** | **+0.0030** |
| bursty / scarce | −0.2438 −0.1181 −0.0531 −0.0215 | **yes** | **+0.0035** |
| stationary / moderate | +0.0000 −0.1187 −0.0980 −0.0485 | no* | **+0.0177** |
| bursty / moderate | −0.0118 −0.1245 −0.0983 −0.0475 | no* | **+0.0172** |

\* The moderate-capacity rows begin at a degenerate point: at `amp = 1` there is
**zero starvation at every TTL**, so `ΔS = 0` is a tie among zeros rather than a
measurement. From `amp = 2` onward both rows are monotone increasing
(−0.119 → −0.098 → −0.049 and −0.125 → −0.098 → −0.048).

**The real topology flips the sign in all four arms.**

![Figure 1](figures/fig1_starvation_vs_ttl_by_amp.svg)
![Figure 4](figures/fig4_dS_vs_amp.svg)

## 7. Occupancy analysis

| amp | armFail/view | peak footprint / D | peak reservations | fresh |
|---:|---:|---:|---:|---:|
| 1 | 9.14 | 0.74 | 27 | 0.4417 |
| 2 | 22.26 | 0.73 | 14 | 0.2197 |
| 4 | 29.06 | 0.69 | 6 | 0.1033 |
| 8 | 32.58 | 0.59 | 3 | 0.0435 |

**Achieved footprint does not scale with amplification.** It is flat-to-falling
(0.74 → 0.59), because capacity caps it. Peak reservations *fall* by 9×.

This falsifies the naive reading of the mechanism — "bigger footprint crowds the
pool" — and replaces it with a sharper one in §11.

![Figure 2](figures/fig2_footprint_vs_amp.svg)

## 8. Starvation analysis

Starvation at TTL = 1 rises with amplification (0.557 → 0.780 → 0.896 → 0.956,
stationary/scarce) and the *benefit* of raising TTL shrinks toward nothing. By
`amp = 8` the entire TTL sweep moves starvation by 0.024; at `amp = 1` it moved
it by 0.262.

## 9. Waste analysis

`ΔW` stays negative at every amplification — longer leases always reduce waste,
because a held reservation gets more chances to be consumed. But the magnitude
falls (−0.243 → −0.184), and in the topology arm it is nearly flat (−0.025),
because so little is successfully reserved in the first place.

## 10. Latency analysis

`ΔL` follows `ΔS` closely: −1.096 → −0.534 → −0.246 → −0.101 ms, and **+0.003 ms
in the topology arm**. Latency is dominated by starvation, so the two move
together.

![Figure 3](figures/fig3_ttl_latency_effect_vs_amp.svg)

## 11. Mechanism validation

The hypothesis as posed was that amplification increases *simultaneous occupied
resource*. **It does not** (§7). The measured mechanism is different and
tighter:

> Amplification **prices reservations out of the pool**. Each reservation costs
> `h ×` more to make, so arming failures rise 3.6× (9.14 → 32.58 per view) and
> the number of live reservations falls 9× (27 → 3). With almost nothing
> reserved, TTL has almost nothing to extend, and its benefit collapses toward
> zero.

The topology arm adds the second half — **link specificity**. Model B at
`amp = 2` and the topology at mean 2.30 hops have comparable footprint
arithmetic, but only the topology flips `ΔS` positive. The difference is that a
path needs capacity on `h` *particular* links: aggregate headroom does not help
if the specific hops are held.

Direct evidence: mean hops of **successful** reservations in the topology arm is
**1.504** against a structural mean of **2.300**. Short paths win under
contention and long paths are systematically shut out — a selection effect that
cannot occur in a fungible pool. (Runs in which no reservation succeeded
contribute 0 to that mean, so 1.504 is a lower bound.)

## 12. Comparison against E1

| | E1 | E8 topology arm |
|---|---|---|
| direction of TTL effect on starvation | longer lease **worse** | longer lease **worse** (ΔS = +0.003 … +0.018) |
| magnitude | pre-arming raised starvation up to **33%**; halving the lease restored the reactive rate exactly | sign flip of **+0.003 to +0.018** |
| mechanism | multi-hop reservation on shared links | reproduced |

The direction is reproduced; the magnitude is not, by roughly an order of
magnitude. Candidate reasons, none tested here: E1 used its own consensus demand
model rather than the hub-union generator; E1's pools were sized per link from
decoy-BB84 rates rather than normalised to aggregate `C·D`; and E1 compared
pre-arming against a **reactive** baseline, whereas E8 compares TTL values
within pre-arming.

## 13. Threats to validity

- **The abstract arm is explicitly not a topology.** Model A/B tests the
  footprint arithmetic E1's code implies; it does not reproduce E1's physical
  relay structure. Only Model C does, and it is the arm that flips the sign.
- **Magnitude is unexplained** (§12). The mechanism is identified, not
  quantified against E1.
- The topology arm is near-saturated under `C = 0.75D` (armFail 31.35/view), so
  its numbers describe a heavily congested regime; the `+0.003` flip is small
  partly because there is so little successful reservation to differentiate.
- Capacity normalisation across models is a choice (§1); a different split
  between per-link capacity and link count would change the comparison.
- One topology (`ring_with_chords`, seed 3). Path-length distribution is a
  property of it.
- Simulated throughout; π was validated against relab/hotstuff in E2, the pool
  and topology models were not.
- 10 seeds; per-row CIs are in the JSON.

## 14. Verdict

> ## MECHANISM PARTIALLY SUPPORTED

Multi-hop reservation amplification **does** change the relationship between TTL
and shared-resource contention, in the predicted direction and monotonically:
the TTL benefit attenuates from −0.262 to −0.024 as the factor grows from 1 to
8, and under E1's actual relay mechanism it inverts to +0.003 … +0.018. The
regression control at `amp = 1` reproduces E6/E7 exactly (0.0000).

Two qualifications keep this from being full support. The magnitude of E1's
effect is not reproduced — a sign flip of +0.003 against E1's 33% starvation
increase. And the mechanism is not the one hypothesised: amplification does not
raise occupied resource (it falls), it raises **arming failure**, and the final
sign flip requires **link specificity**, which only the real-topology arm has.

The E1/E6 discrepancy is therefore **correctly attributed** to reservation
accounting rather than to workload dynamics — E7 ruled out burstiness, E8
identifies the responsible mechanism — but a quantitative reconciliation with E1
would need E1's own demand model and link sizing, which is a further experiment.
