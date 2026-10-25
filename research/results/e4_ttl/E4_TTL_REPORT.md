# E4-TTL — does the operational ceiling survive multi-view reservations?

E4 measured `hit rate ≤ π` with one-view reservations. That is exactly the
condition under which the live reservation set equals what the predictor armed
this view, so Theorem B's budget-`K` statement carries over to hit rate. This
experiment removes that condition.

> ## Verdict: OUTCOME C — the prediction ceiling holds; TTL is a budget and cost
> ## dial, not an accuracy dial
>
> Counting only genuine predictions, **no TTL produces a hit rate above π**
> (max excess +0.0044 at every TTL). Counting stale reservations as well,
> **the total hit rate exceeds π by up to +0.73**, and the mechanism is
> measured directly: live reservations rise to **3.77 ×** the per-view budget.
> E4's headline "hit rate ≤ π" was therefore a TTL = 1 statement and must be
> qualified. The underlying prediction ceiling is untouched.

---

## 1. Setup

Workload, predictors, `n`, and the demand process are imported **unchanged**
from `research/e4_operational.py` — the hub-union generator, six operating
points, three predictors. Only reservation lifetime and instrumentation differ.

Key rate fixed at **R = 8192 bits/pair/view**, the E4 Q3 operating point. E4 Q1
established hit rate is flat from R = 256 to R = 65536, so R is not binding and
was not re-tuned per TTL.

10 seeds per cell; 6 operating points × 4 TTLs × 3 predictors.

### The distinction the experiment turns on

| | |
|---|---|
| **fresh hit** | served by a reservation created **in the current view** — an actual successful prediction |
| **stale hit** | served by a reservation created in an **earlier** view, still alive, that happens to match current demand |

A stale hit is not prediction. It is a larger effective budget. Counting the two
together would manufacture a ceiling violation out of bookkeeping, which is
precisely the failure mode this experiment was built to avoid.

## 2. TTL configurations

`TTL ∈ {1, 2, 4, 8}` views. A reservation created at view `t` expires at
`t + TTL`. A pair already holding a live reservation is not re-armed, so longer
TTLs shift arming work from fresh to carried-over entries.

## 3. Results

Carry-forward predictor (structural and reactive in `E4TTL-001.json`):

| π | TTL | hit (total) | fresh | stale | hit − π | occupancy | K | occ/K | waste | key/demand |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1333 | 1 | 0.1377 | 0.1377 | 0.0000 | +0.0044 | 29.0 | 29 | 1.00 | 0.8638 | 1.8638 |
| 0.1333 | 2 | 0.3638 | 0.1377 | 0.2261 | +0.2305 | 54.0 | 29 | 1.86 | 0.6437 | 1.6437 |
| 0.1333 | 4 | 0.6397 | 0.1365 | 0.5032 | +0.5063 | 84.1 | 29 | 2.90 | 0.3375 | 1.3375 |
| 0.1333 | 8 | 0.8635 | 0.1371 | 0.7264 | **+0.7301** | 109.2 | 29 | **3.77** | 0.0989 | 1.0989 |
| 0.4500 | 1 | 0.3882 | 0.3882 | 0.0000 | −0.0618 | 54.0 | 54 | 1.00 | 0.6478 | 1.6478 |
| 0.4500 | 8 | 0.8752 | 0.3331 | 0.5420 | +0.4252 | 118.6 | 54 | 2.20 | 0.0113 | 1.0113 |
| 0.5667 | 1 | 0.5164 | 0.5164 | 0.0000 | −0.0503 | 29.0 | 29 | 1.00 | 0.4983 | 1.4983 |
| 0.5667 | 8 | 0.8099 | 0.4820 | 0.3280 | +0.2433 | 88.9 | 29 | 3.07 | 0.1451 | 1.1451 |
| 0.6333 | 1 | 0.5361 | 0.5361 | 0.0000 | −0.0972 | 54.0 | 54 | 1.00 | 0.4983 | 1.4983 |
| 0.6333 | 8 | 0.8593 | 0.4449 | 0.4144 | +0.2259 | 115.2 | 54 | 2.13 | 0.0262 | 1.0262 |
| 0.8167 | 1 | 0.7395 | 0.7395 | 0.0000 | −0.0772 | 54.0 | 54 | 1.00 | 0.2824 | 1.2824 |
| 0.8167 | 8 | 0.8306 | 0.6294 | 0.2012 | +0.0139 | 101.7 | 54 | 1.88 | 0.0507 | 1.0507 |
| 1.0000 | 1–8 | 0.9983 | 0.9983 | 0.0000 | −0.0017 | 29.0 | 29 | 1.00 | 0.0000 | 1.0000 |

## 4. Ceiling analysis

| TTL | max(total hit − π) | violations | max(fresh − π) | fresh violations |
|---:|---:|---:|---:|---:|
| 1 | +0.0044 | 1 | +0.0044 | 1 |
| 2 | **+0.2305** | 4 | +0.0044 | 1 |
| 4 | **+0.5063** | 4 | +0.0031 | 1 |
| 8 | **+0.7301** | 5 | +0.0038 | 1 |

Two different statements, and they diverge sharply:

- **Total hit rate is not bounded by π once TTL > 1.** Violations grow with TTL,
  reaching +0.73 at TTL = 8.
- **Fresh hit rate is bounded by π at every TTL.** The maximum excess is +0.0044
  and does not grow with TTL — the single flagged "violation" is the π = 0.1333
  point, where measured fresh hits are 0.1377 against π = 0.1333, a discrepancy
  of the same size as the finite-sample gap already present at TTL = 1.

Fresh hit rate per operating point is essentially flat in TTL, and where it moves
it moves **down**, not up: at π = 0.8167 it falls 0.7395 → 0.6294 as TTL goes
1 → 8. Longer leases mean more pairs are already reserved and therefore skipped
by the arming loop, so prediction work shifts into carried-over entries. No
version of this makes the predictor more accurate.

![Figure 1](figures/fig1_hit_vs_pi.svg)
![Figure 1b](figures/fig1b_freshhit_vs_pi.svg)

## 5. Waste analysis

| TTL | corr(1−π, waste) | slope | intercept | mean waste |
|---:|---:|---:|---:|---:|
| 1 | **0.9827** | **0.9770** | +0.0743 | 0.4651 |
| 2 | 0.9812 | 0.7019 | +0.0184 | 0.2992 |
| 4 | 0.8316 | 0.3426 | +0.0202 | 0.1573 |
| 8 | 0.4842 | 0.0909 | +0.0190 | 0.0554 |

**E4's slope-1 law is a TTL = 1 result.** As the lease lengthens the relationship
flattens toward zero: at TTL = 8 the slope is 0.091 and the correlation has
fallen to 0.48. Mean waste drops 8.4-fold, from 0.465 to 0.055, and total key
per unit demand falls from 1.86 to 1.10 at π = 0.1333.

The mechanism is straightforward: a mis-armed reservation that survives eight
views has eight chances to eventually match demand before expiring, so it is
consumed rather than wasted.

![Figure 2](figures/fig2_waste_vs_1minuspi.svg)
![Figure 3](figures/fig3_hit_vs_ttl.svg)

## 6. Mechanism for the ceiling violation

Directly measured, not inferred. The `occ/K` column is the ratio of live
reservations to the per-view arming budget `K = |S(t)|`:

| TTL | 1 | 2 | 4 | 8 |
|---|---|---|---|---|
| occ/K at π=0.1333 | 1.00 | 1.86 | 2.90 | **3.77** |

Theorem B bounds top-`K` coverage at budget `K`. With TTL = 1 the live set *is*
the top-`K` set, so the bound transfers to hit rate. With TTL = 8 the live set is
up to 3.77 × larger — approximately the union of the last several views' armed
sets — and a bound stated at budget `K` says nothing about coverage at budget
`3.77 K`.

So the violation is **budget inflation, not improved prediction**, and the
fresh-hit column confirms it: the predictive component stays pinned at π while
the total climbs.

**Theorem A and Theorem B are unaffected.** Neither is a statement about hit
rate under multi-view reservations. What requires qualification is E4's
operational corollary.

## 7. Threats to validity

- **The decisive one.** This experiment inherits E4's **per-pair key pools**,
  chosen there to isolate the predictor from relay topology. With independent
  pools, holding key for pair *p* costs pair *q* nothing, so a longer lease is
  nearly free and the results above make long TTLs look uniformly good.
  **E1 measured the opposite under shared link pools**: pre-arming raised
  starvation up to 33% under flash crowds, and *halving* the lease was what
  fixed it. Those two findings are not in conflict — they are measured under
  different contention models — but **the conclusion "longer TTL is better" does
  not transfer to a system with shared relay pools**, and nothing here tests
  that case.
- Map capacity is unbounded in this model. A real deployment caps `M_max`, and
  occ/K = 3.77 would either not fit or would evict.
- Simulated hub-union workload, not an implementation trace. E2 validated the
  generator's π against relab/hotstuff; the reservation model is not itself
  validated against a deployment.
- TTL ∈ {1,2,4,8} only. No claim is made outside that range.
- 10 seeds; the quantities are near-deterministic within a cell (95% CI on hit
  rate is recorded per row in the JSON).

## 8. Implications for Theorem A / Theorem B

Neither theorem changes, and neither was tested here.

- **Theorem A** (`π` from `(n,m,k)`) is a property of the workload. TTL is a
  control-plane parameter and does not enter it.
- **Theorem B** (RWC coverage at budget `K`) is confirmed rather than
  threatened: the fresh-hit ceiling is exactly the operational shadow of the
  budget-`K` statement, and it holds at every TTL.

What must be qualified is **E4's operational claim**, which should now read:

> Fast-path hits *attributable to prediction* are bounded by π, and no key
> budget lifts that bound. Total fast-path hits are additionally bounded by the
> map capacity the reservation lifetime induces; a longer lease raises total hit
> rate by enlarging the live set, at a cost in occupancy — and, under shared key
> pools, at a cost in starvation that this experiment cannot see.

## 9. Verdict

> ## OUTCOME C — TTL changes waste and effective budget, not the prediction ceiling

The structural persistence ceiling survives as a bound on **predicted** hits
across TTL ∈ {1,2,4,8}, with maximum excess +0.0044 and no growth in TTL. The
E4 statement about **total** hit rate does not survive and is now qualified: it
was a TTL = 1 result, and the excess reaches +0.73 at TTL = 8 through a measured
3.77 × inflation of the live reservation set.

This strengthens rather than weakens the engineering story, because it separates
two dials that E4 had fused:

- **π** — set by the protocol's communication structure — determines how much of
  the fast path *prediction* can reach.
- **TTL** — set by the operator — determines how much additional fast path is
  bought by holding reservations longer, and what that costs in occupancy,
  wasted key, and (per E1, unmeasured here) contention.

No claim is made for TTL outside the tested range, and the per-pair-pool caveat
in §7 is the one that most limits what these numbers imply for a deployment.
