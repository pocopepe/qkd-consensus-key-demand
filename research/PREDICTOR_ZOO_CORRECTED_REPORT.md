# Corrected predictor zoo — report

Post-freeze addendum. `research-freeze-v1` (`330b87b6`) is untouched.

---

## 1. Why the rerun was necessary

`THEOREM_B_AUDIT.md` established that `research/predictor_zoo.py` measures
support-**cardinality** persistence at a budget of `m(n−1)`, while the manuscript
defines `π` as **demand-weighted** persistence and states Theorem B's cases on
the nomination budget `B`. The zoo's `pi` column therefore differs from Theorem A
by ~0.015 at `n=16` — 0.5517 against `π(16,2,1) = 17/30 = 0.5667`.

The manuscript's §5 places predictor coverage in the same table as `π`. That
comparison is only legible if `π` means the same thing in both, so the experiment
was rerun under the manuscript's definitions. The theorem was **not** changed;
the audit had already confirmed it valid.

---

## 2. Corrected definitions

```
hubs(t) = distinct proposers of views t and t+1
d_t(p)  = |{h in hubs(t) : h incident to p}|        in {1, 2}
S(t)    = {p : d_t(p) > 0}
D_t     = Σ_p d_t(p) = |hubs(t)| · (n−1)
K_t     = |S(t)| = |hubs(t)|·(n−1) − C(|hubs(t)|,2)

B_t     = K_t = |S(t)|                              nomination budget
π_t     = Σ_{p ∈ S(t−1)} d_t(p) / D_t
cov_t   = Σ_{p ∈ top-B} d_t(p) / D_t
```

Hub-to-nonhub pairs carry demand 1; the hub-to-hub pair carries 2. Coverage is
normalised by `D_t`, **never** by `|S(t)|` and never by cardinality intersection.

**Tie-break, explicit and identical for every predictor:** sort by `(−score,
pair)` with `pair` the `(min,max)` integer tuple — descending score, then
ascending pair. No result depends on dict insertion order. Recorded in the
result metadata under `definitions.tie_break`.

---

## 3. Configuration

| | |
|---|---|
| `n` | 16, 32 |
| Schedules | round_robin, shuffled_epoch, vrf, weighted |
| Views | 600, burn-in 120 (479 scored transitions per configuration) |
| Seeds | `[0]` — **persisted explicitly**; matches the frozen zoo's single `seed=0` |
| RWC predictors | `ewma0.5`, `ewma0.7`, `last`, `freq` |
| Non-RWC predictors | `markov1`, `periodic`, `oracle` |
| Budget | `B_t = |S(t)|` |

**One documented addition.** The frozen zoo used EWMA at `α = 0.5` only. Lag-1
dominance requires `w₁ > Σ_{s≥2} w_s`, and for EWMA that is `α > ½` **strictly**,
so `α = 0.5` sits exactly on the class boundary. A second arm at `α = 0.7` was
added so that check B is evaluated on a predictor genuinely inside the class.
`α = 0.5` is retained and reported, never excluded. No other parameter changed.

### Pre-run gates (all passed; the script exits non-zero on any failure)

```
m == 2                                              ok
|S| == 29                                           ok
B  == 29                                            ok
D  == 30                                            ok
exactly C(m,2)=1 hub-hub pair carries demand 2      ok
pi(round-robin,n=16) == 17/30                       ok   0.566666666666667
coverage denominator is D, not |S|                  ok   cov(all of S) = 1.000000
coverage uses demand weights                        ok   single-pair cov = d/D = 0.033333
```

---

## 4. Results

Demand-weighted, `B = |S(t)|`, seed 0.

| `n` | schedule | `π` | `\|S\|` min–max | ewma0.5 | ewma0.7 | last | freq | markov1 | periodic | oracle |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | round_robin | **0.5667** | 29–29 | 0.5667 | 0.5667 | 0.5667 | 0.1854 | 0.9458 | **1.0000** | 1.0000 |
| 16 | shuffled_epoch | 0.5692 | 15–29 | 0.5655 | 0.5655 | 0.5670 | 0.1781 | 0.3913 | 0.2566 | 1.0000 |
| 16 | vrf | 0.6217 | 15–29 | 0.5787 | 0.5785 | 0.5946 | 0.2399 | 0.4406 | 0.2256 | 1.0000 |
| 16 | weighted | 0.6553 | 15–29 | 0.5852 | 0.5851 | 0.6258 | 0.4688 | 0.5331 | 0.2987 | 1.0000 |
| 32 | round_robin | **0.5323** | 61–61 | 0.5323 | 0.5323 | 0.5323 | 0.0882 | 0.9708 | **1.0000** | 1.0000 |
| 32 | shuffled_epoch | 0.5352 | 61–61 | 0.5352 | 0.5352 | 0.5352 | 0.0710 | 0.3266 | 0.1259 | 1.0000 |
| 32 | vrf | 0.5611 | 31–61 | 0.5381 | 0.5381 | 0.5491 | 0.1272 | 0.3352 | 0.1026 | 1.0000 |
| 32 | weighted | 0.6042 | 31–61 | 0.5513 | 0.5513 | 0.5843 | 0.3621 | 0.4418 | 0.1980 | 1.0000 |

On the two deterministic round-robin rows the support size is constant, so
`|S(t−1)| = B` in every view and Theorem B's equality case applies: `ewma0.5`,
`ewma0.7` and `last` all sit **exactly** on `π`. This is the first time the
equality case has actually been realised in this experiment — the frozen zoo,
with `B = |S(t)|+1`, was never in it.

---

## 5. Comparison with the frozen zoo

| `n` | schedule | `π` old | `π` new | Δ`π` | ewma old | ewma new |
|---:|---|---:|---:|---:|---:|---:|
| 16 | round_robin | 0.5517 | 0.5667 | +0.0149 | 0.5517 | 0.5667 |
| 16 | shuffled_epoch | 0.5546 | 0.5692 | +0.0146 | 0.5559 | 0.5655 |
| 16 | vrf | 0.6068 | 0.6217 | +0.0149 | 0.6158 | 0.5787 |
| 16 | weighted | 0.6427 | 0.6553 | +0.0126 | 0.6606 | 0.5852 |
| 32 | round_robin | 0.5246 | 0.5323 | +0.0077 | 0.5246 | 0.5323 |
| 32 | shuffled_epoch | 0.5270 | 0.5352 | +0.0082 | 0.5277 | 0.5352 |
| 32 | vrf | 0.5528 | 0.5611 | +0.0083 | 0.5555 | 0.5381 |
| 32 | weighted | 0.5966 | 0.6042 | +0.0076 | 0.6044 | 0.5513 |

`π` rises uniformly, by `+0.013` to `+0.015` at `n=16` and `+0.008` at `n=32` —
the hub-to-hub pair's second demand unit, whose relative weight falls as `n`
grows. The frozen zoo's **six** rows in which EWMA appeared to exceed `π`
(`+0.0007` to `+0.0179`) are **all gone**: no RWC predictor's mean exceeds `π` in
any corrected configuration.

---

## 6. Theorem B validation

Checked **per view**, not on means, for RWC predictors satisfying **strict**
lag-1 dominance (`ewma0.7`, `last`):

| Case | Views | Violations |
|---|---:|---:|
| `\|S(t−1)\| = B ⟹ cov = π` | 7,186 | **0** |
| `\|S(t−1)\| > B ⟹ cov ≤ π` | 248 | **0** |
| `\|S(t−1)\| < B ⟹ cov ≥ π` | 246 | **0** |

All three cases are exercised — the stochastic schedules supply the growing and
shrinking support that round-robin cannot.

**`ewma0.5` reported separately, not excluded.** At `α = 0.5` the weights satisfy
`w₁ = Σ_{s≥2} w_s`, so strict dominance fails and the theorem does not apply.
Measured anyway: **0 deviations across 3,840 views.** The reason is that strict
separation still holds in practice — a pair outside `S(t−1)` scores
`(1−α)·score_{t−1} < 0.5` unless it appeared in *every* prior view, which no pair
does under any of these schedules. So `α = 0.5` behaves as if dominant here
without being inside the class. This is a property of the workload, not of the
predictor, and should not be presented as evidence that the boundary case is
safe.

**A caution for §5.** Comparing *mean* coverage to *mean* `π` is not the theorem.
On stochastic schedules the mean of `cov` falls below the mean of `π` (e.g.
0.5787 against 0.6217 at `n=16` vrf) while every individual view satisfies its
case. Averaging mixes the three cases and is not a test of the statement.

---

## 7. Periodicity and markov1 — the class boundary holds

| `n` | schedule | `π` | periodic | markov1 |
|---:|---|---:|---:|---:|
| 16 | round_robin | 0.5667 | **1.0000** (+0.4333) | **0.9458** (+0.3791) |
| 32 | round_robin | 0.5323 | **1.0000** (+0.4677) | **0.9708** (+0.4385) |

Both exceed `π` decisively on the deterministic schedule, and both are outside
the RWC class: `periodic` keys its table on `t mod P`, so its weights depend on
the view index, violating the requirement that `w` be independent of `t`;
`markov1` keys on the previous view's highest-degree vertex, which is a state
variable, not a lag weight.

This is the conclusion that survived every definitional change — it held under
cardinality weighting at `B = |S(t)|+1` and holds under demand weighting at
`B = |S(t)|`. On stochastic schedules both collapse far below `π`, confirming
that the escape requires a predictable schedule rather than a better estimator.

`freq` (uniform weights over the history) fails lag-1 dominance for every window
`> 2` and is correspondingly far below `π` — mean 0.2151 against mean `π` 0.5807.
The theorem asserts nothing about it, and no case is claimed.

---

## 8. Discrepancies

1. **`ewma0.5` is outside the class it is used to illustrate.** Handled by adding
   `ewma0.7` and reporting both. `α = 0.5` shows 0 deviations for a
   workload-specific reason (§6), which must not be read as the theorem covering
   the boundary.
2. **`ewma0.7` and `ewma0.5` agree to within 0.0002 everywhere.** Coverage is
   insensitive to `α` once separation holds, because the ranking — not the score
   magnitudes — determines the top-`B` set.
3. **`markov1` on round_robin fell** from 0.9741 to 0.9458 at `n=16` and 0.9857 to
   0.9708 at `n=32`. Its predictions are unchanged; the drop is the demand
   weighting, which puts extra weight on the hub-to-hub pair that `markov1`'s
   degree-keyed table misses more often than average. It still exceeds `π` by a
   wide margin, so the conclusion is unaffected.
4. **`shuffled_epoch` at `n=32` has constant support** (61–61), unlike `n=16`
   (15–29), because with `views+4 = 604` and `n = 32` the epoch boundaries
   happened not to produce a repeated consecutive proposer under seed 0. This is
   a single-seed artefact, not a structural property. It means the `n=32`
   shuffled_epoch row sits entirely in the equality case.
5. **Single seed.** The frozen zoo used one seed and this run preserves it for
   comparability. Means on stochastic schedules therefore carry no confidence
   interval. If §5 reports the stochastic rows quantitatively rather than
   directionally, more seeds are needed.

---

## 9. Reproducibility metadata

| | |
|---|---|
| Git commit before run | `330b87b6d69f609f39856ecf44ea806c13494f32` (`research-freeze-v1`) |
| Git commit after run | recorded in the commit that adds this file; tag `predictor-zoo-corrected-v1` |
| Command | `python3 research/predictor_zoo_corrected.py` |
| Script SHA-256 | `e2742ba284a6b03f3862e12cdcbc4cfd9cee454477bbc082d32b8dd351c5a810` |
| Result SHA-256 | `86eca6996635950ee12bf4aeb13c3890129b8837f3bbb474ffd06fd8981df10e` |
| Result path | `research/results/predictor_zoo_corrected/P-predictor-zoo-corrected-001.json` |
| Seeds | `[0]` — persisted in the result JSON under `config.seeds` |
| Python | 3.12.3 |
| NumPy | 1.26.4 |
| Platform | Linux-6.8.0-138-generic-x86_64-with-glibc2.39 |

The result JSON additionally stores the full definition set, the tie-break rule,
every check with its pass/fail and detail string, the (empty) violation list, and
the per-configuration support-size range.

**Caveat.** The script writes its own result file on every run, so re-executing it
changes the `utc` field and therefore the result hash. The hash above pins this
run's output as committed.

---

## 10. The frozen results were not overwritten

`research/predictor_zoo.py` and `research/results/P-predictor-zoo-001.json` are
byte-identical to their state at `research-freeze-v1`. The corrected experiment
is a **new** script writing to a **new** directory,
`research/results/predictor_zoo_corrected/`. Nothing under the frozen
predictor-zoo path was read for writing, and **no old `π` value was copied
forward** — every corrected quantity was recomputed from the corrected
definitions, and the comparison table in §5 is the only place the two appear
together.
