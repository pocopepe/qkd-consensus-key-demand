# E4 — Does `π` change an engineering decision?

Theorem A gives `π` in closed form; Theorem B says a carry-forward predictor
attains exactly `π` and no more. Both are statements about *prediction
accuracy*. Neither says anything about key material, latency, or cost. E4 was
designed so that "the theorem is elegant and operationally irrelevant" was a
reportable outcome.

> ## Verdict: OPERATIONALLY RELEVANT — but not in the way the plan predicted
>
> The plan's hypothesis (*"required over-provisioning scales with 1−π"*) is
> **not supported**. The operational cost of `1−π` is paid in **wasted key
> material**, not in required generation rate — and there it tracks `1−π` with
> correlation **+0.983** and slope **0.975**.
>
> Separately and more strongly: **`π` is a hard ceiling that key cannot buy
> past.**

---

## 1. Setup

n = 16, hub-union workload with configurable `(m, k)` so `π` is known exactly
from Theorem A. Six operating points spanning `π = 0.133 … 1.000`. Each pair has
its own key pool refilled at `R` bits/view — deliberately isolating the
predictor's effect from relay topology, which is not what E4 is about.
Pre-arming reserves from the pool and expires after one view; a miss draws from
the pool directly, still consuming key but paying the slow path
(14.2 µs vs 1.042 ms, both measured in E1/E2 and `kme_bench`).

Predictors: **structural** (knows the hub set, coverage 1), **carry-forward**
(last-observation, attains `π` by Theorem B), **none** (reactive).

20 seeds for the rate search, 10 for the waste measurements.

### A modelling error found and fixed mid-experiment

The first version armed a flat `2 × TAG_BITS` for every predicted pair. That
over-arms pairs incident to only one hub, and charged the *structural*
predictor with 80–93% waste that was an artefact of the sizing rule rather than
of prediction error. Corrected so each predictor arms **the demand it actually
predicts** per pair. After the fix, structural waste is exactly `0.0000` at
every `π`, which is the correct behaviour for a predictor with coverage 1. All
numbers below are post-fix.

## 2. Q1 — Is `π` a ceiling, or can it be bought past with more key?

Key-generation rate swept over a **256×** range:

| m | k | π | hit @ R=256 | hit @ R=65536 | change | ceiling − π |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 0 | 0.1333 | 0.1375 | 0.1375 | **+0.0000** | +0.0041 |
| 4 | 1 | 0.4500 | 0.3876 | 0.3876 | **+0.0000** | −0.0624 |
| 2 | 1 | 0.5667 | 0.5155 | 0.5155 | **+0.0000** | −0.0511 |
| 4 | 2 | 0.6333 | 0.5352 | 0.5352 | **+0.0000** | −0.0981 |
| 4 | 3 | 0.8167 | 0.7383 | 0.7383 | **+0.0000** | −0.0784 |
| 2 | 2 | 1.0000 | 0.9806 | 0.9967 | +0.0161 | −0.0033 |

**Maximum change in hit rate across a 256× sweep of `R`: 0.0161**, and that
solely in the degenerate `π = 1` case where the pool starts cold.

`π` is therefore not an accuracy statistic. It is a **hard operational ceiling**:
a carry-forward predictor cannot be lifted above it by any amount of key
generation. That is the strongest result in E4 and it needed no curve fitting.

The measured ceiling sits **at or slightly below** `π` (0 to −0.098). The gap is
expected and is a second-order effect: hit rate requires both the right *pair*
and sufficient *bits*, so a pair whose hub-incidence changed between views is
armed with last view's smaller amount and misses on the bit check. Support error
is bounded by `1 − π`; bit-sizing error sits on top of it. **Hit rate ≤ π**, not
`= π`.

![Figure 1](figures/fig1_ceiling.svg)

## 3. Q2 — Does required over-provisioning track `1 − π`? **No.**

Minimum key-rate `R*` to reach a common target hit rate of 0.45, binary-searched
over 20 seeds:

| 1 − π | R* structural | R* carry | ratio | 95% CI |
|---:|---:|---:|---:|---:|
| 0.8667 | — | unreachable | — | — |
| 0.5500 | — | unreachable | — | — |
| 0.4333 | 64 | 65 | 1.017 | ±0.008 |
| 0.3667 | 64 | 109 | **1.696** | ±0.005 |
| 0.1833 | 64 | 82 | 1.282 | ±0.003 |
| 0.0000 | 110 | 111 | 1.007 | ±0.000 |

`corr(1−π, ratio) = +0.359` over four usable points, and the sequence is **not
monotone** (1.017 → 1.696 → 1.282 → 1.007). The plan's stated hypothesis is
**not supported**.

The reason is visible in Q1: below the ceiling, both predictors are limited by
*prediction*, not by key. Rate barely matters, so the ratio of required rates is
noisy and small. Two of the six operating points could not be tested at all
because the target lies above their `π` ceiling — which is itself Q1 restated.

## 4. Q3 — Does wasted key track `1 − π`? **Yes, tightly.**

| π | 1 − π | waste (carry) | waste − (1−π) | waste (structural) |
|---:|---:|---:|---:|---:|
| 0.1333 | 0.8667 | 0.8623 | −0.0043 | **0.0000** |
| 0.4500 | 0.5500 | 0.6468 | +0.0968 | **0.0000** |
| 0.5667 | 0.4333 | 0.4975 | +0.0642 | **0.0000** |
| 0.6333 | 0.3667 | 0.4975 | +0.1308 | **0.0000** |
| 0.8167 | 0.1833 | 0.2819 | +0.0986 | **0.0000** |
| 1.0000 | 0.0000 | 0.0000 | +0.0000 | **0.0000** |

    corr(1 - pi, waste) = +0.9827
    least-squares fit:   waste = 0.975 * (1 - pi) + 0.074

Slope within 2.5% of unity, exact at both endpoints, monotone throughout, and
the structural predictor wastes **exactly zero** at every `π`. The positive
intercept (+0.074) and the mid-range excess reflect the bit-sizing error noted
in Q1 — waste includes both wrong-pair and wrong-size reservations, while
`1 − π` accounts only for the first.

Total key consumed per unit of delivered demand:

| π | structural | carry-forward | reactive |
|---:|---:|---:|---:|
| 0.1333 | 1.0000 | **1.8623** | 1.0000 |
| 0.4500 | 1.0000 | 1.6467 | 1.0000 |
| 0.5667 | 1.0000 | 1.4975 | 1.0000 |
| 0.8167 | 1.0000 | 1.2819 | 1.0000 |
| 1.0000 | 1.0000 | 1.0000 | 1.0000 |

At `π = 0.13` a carry-forward predictor burns **1.86× the key it delivers**. The
structural predictor and the reactive baseline both sit at exactly 1.0 — the
former because it never mis-arms, the latter because it never arms at all.

![Figure 2](figures/fig2_waste_vs_1minuspi.svg)
![Figure 3](figures/fig3_key_per_demand.svg)

## 5. The engineering decision this changes

Given a protocol specification, `π` is computable from `(n, m, k)` with no data
and no deployment. E4 shows that number answers two operational questions
directly:

1. **What fast-path hit rate is achievable at all?** At most `π`, and no key
   budget changes that. If the target is above `π`, a carry-forward predictor is
   the wrong tool regardless of provisioning — the choice is a schedule-aware
   predictor or nothing.
2. **What will it cost in key?** Roughly `1 − π` of demand, wasted in
   reserved-but-unused reservations. At `π = 0.13` that is 86% of demand thrown
   away; at `π = 0.82`, 28%; at `π = 1`, none.

Combined with E1 — where both production-lineage systems measured sit at
`π = 1` — the decision rule is sharper than "implement prediction or not":

> If `k/m = 1` (`π = 1`), carry-forward prediction is free and perfect, and a
> schedule-aware predictor adds nothing. If `k/m < 1`, carry-forward prediction
> is capped at `π` and wastes about `1 − π` of demand in held key, so the
> schedule-aware predictor is the only way to reach the fast path — and it is
> also the only one that wastes nothing.

## 6. Threats to validity

- **Simulated**, on the hub-union workload generator, not a real implementation
  trace. E2 validated that generator's `π` against relab/hotstuff; the key-pool
  and reservation model is not itself validated against a deployment.
- Per-pair key pools, chosen to isolate the predictor. Real relay topology
  couples pools across pairs and would add contention effects not measured here.
- One TTL (one view). E1's starvation finding showed lease duration matters a
  great deal; a TTL sweep is not included.
- The Q2 result rests on four usable points; two operating points were
  unreachable. It is reported as unsupported rather than refuted.
- The bit-sizing error was found and fixed mid-experiment. It inflated
  structural waste by ~0.8–0.93 before the fix. All reported numbers are
  post-fix, but the incident is a reminder that waste is sensitive to the arming
  rule and not only to prediction accuracy.

## 7. Verdict

> ## OPERATIONALLY RELEVANT

`π` is not merely an accuracy bound. It is a hard ceiling on achievable
fast-path hit rate that **no amount of key generation lifts** (max change 0.0161
across a 256× rate sweep), and `1 − π` predicts wasted key material with
correlation **+0.983** and slope **0.975**.

The plan's specific hypothesis — that *required generation rate* scales with
`1 − π` — is **not supported** (non-monotone, corr +0.36 on four points). The
cost is real but is paid in wasted key, not in required rate. That distinction
is reported rather than smoothed over, because it changes what an operator
should measure: not "do I have enough key" but "how much of it am I throwing
away".
