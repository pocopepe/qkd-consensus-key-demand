# Theorem B audit — budget semantics

Triggered by a notation collision found while drafting §3: the manuscript's
notation lock defines `K` as "per-view support size = prediction budget", but the
two are not the same number in the frozen code. This document traces the
implementations, restates the theorem correctly, and reports what changes.

**No experiment was rerun. No frozen result was modified.** The exhaustive
searches below are mathematical checks written to a scratch directory; they
produce no artefact under `research/results/`.

---

## 1. Actual implementation semantics

Two frozen programs bear on Theorem B, and **they do not use the same
definitions**.

### 1.1 `research/e5_theorem_b.py` — the verification of record

| Aspect | Implementation | Line |
|---|---|---|
| Demand | `chained_demand()` builds a **dict**, `d[p] += B` once per incident hub, so the hub-to-hub pair carries **2.0** | 119–124 |
| Budget | `K = len({p for p in d})` — the number of **distinct pairs**, i.e. `\|S(t)\|` | 136 |
| Selection | `sorted(sc, key=lambda p: (-sc[p], p))[:K]` — deterministic tie-break on pair identity | 81 |
| Coverage | `sum(demand.get(p,0.0) for p in top) / tot` — **demand-weighted** | 82 |
| Denominator | `tot = sum(demand.values())` — total demand `D_t` | 78 |
| `π` | `sum(v for p,v in demand.items() if p in prev)/tot` — **demand-weighted** | 85–87 |
| Duplicates | impossible; `sc` and `demand` are keyed by pair | — |

**E5 is internally consistent and correct.** Budget = `|S(t)|`, and both coverage
and `π` are demand-weighted, matching Definition 4 of the manuscript.

### 1.2 `research/predictor_zoo.py` — the scope-limit experiment

| Aspect | Implementation | Line |
|---|---|---|
| Demand | `demand()` returns `star(a) \| star(b)` — a **set union**, no multiplicity | 64–65 |
| Budget | `K = 2 * (n - 1)` — a **constant**, not derived from the support | 163 |
| Selection | `sorted(pred_scores, key=lambda p: -pred_scores[p])[:K]` — **no secondary key**; ties resolved by dict insertion order | 71 |
| Coverage | `len(set(top) & actual) / min(K, len(actual))` — **cardinality-weighted** | 72 |
| `π` | `len(d & prev) / max(len(d), 1)` — **cardinality-weighted** | 170 |

**The zoo measures a different quantity.** Its `pi` column is
support-cardinality persistence, not the demand-weighted `π` of Definition 4,
and its budget exceeds the support size.

---

## 2. Definitions: `K`, `B`, `D`

$$K_t = |S(t)| \qquad B = \text{predictor nomination budget} \qquad D_t = \sum_p d_t(p)$$

For a hub-union support with `m` hubs, the `\binom{m}{2}` hub-to-hub pairs are
shared between two stars, so

$$K_t = m(n-1) - \binom{m}{2}, \qquad D_t = m(n-1).$$

At `n = 16, m = 2`: `K_t = 29`, `D_t = 30`. The zoo's budget is `2(n-1) = 30`.

**Verdict on the zoo's `B`: category (D), "something else."** It is neither a
support budget nor a deliberate demand budget. It numerically equals `D_t`, but
the code neither computes nor comments on it as a demand total — it is a
hard-coded constant written as `2(n-1)`, which is the size of two stars counted
**with** their shared edge double-counted. It is most accurately described as an
off-by-`\binom{m}{2}` support budget. In E5 the budget is unambiguously
category (A), a support budget, computed as `len(...)` from the support itself.

**`K` and `B` must therefore be separate symbols.** They are equal in E5 and
differ by exactly 1 in the zoo.

---

## 3. Frozen experiment interpretation

Recomputed from the frozen scripts' deterministic constructions (read-only; no
result file written):

| `n` | schedule | `B` | `\|S\|` range | % views `\|S\|<B` | cardinality `π` | **demand `π`** | zoo `pi` | zoo `ewma` |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 16 | round_robin | 30 | 29–29 | 100% | 0.5517 | **0.5667** | 0.5517 | 0.5517 |
| 16 | shuffled_epoch | 30 | 15–29 | 100% | 0.5546 | **0.5694** | 0.5546 | 0.5559 |
| 16 | vrf | 30 | 15–29 | 100% | 0.6068 | **0.6199** | 0.6068 | 0.6158 |
| 16 | weighted | 30 | 15–29 | 100% | 0.6427 | **0.6546** | 0.6427 | 0.6606 |
| 32 | round_robin | 62 | 61–61 | 100% | 0.5246 | **0.5323** | 0.5246 | 0.5246 |
| 32 | shuffled_epoch | 62 | 61–61 | 100% | 0.5270 | **0.5346** | 0.5270 | 0.5277 |
| 32 | vrf | 62 | 31–61 | 100% | 0.5528 | **0.5600** | 0.5528 | 0.5555 |
| 32 | weighted | 62 | 31–61 | 100% | 0.5966 | **0.6031** | 0.5966 | 0.6044 |

Three facts follow.

1. **The zoo's `pi` equals the cardinality persistence in all eight rows**, to
   four decimals. It is not the demand-weighted `π`.
2. **The recomputed demand-weighted `π` reproduces Theorem A exactly** on the
   deterministic schedule: `0.5667 = 17/30 = π(16,2,1)` and
   `0.5323 = 33/62 = π(32,2,1)`. This is an independent confirmation that
   Theorem A and the E1/E2 measurements are demand-weighted and mutually
   consistent — the discrepancy is confined to the zoo.
3. **`|S(t)| < B` in 100% of views, in every configuration** — including
   round-robin, where `29 < 30`. The zoo never operates in the equality case.

---

## 4. Correct theorem statement

> **Theorem B.** Let a recency-weighted counting predictor score each pair by
> `score_t(p) = Σ_{s<t} w_{t−s} · 1[p ∈ S(s)]`, with `w ≥ 0` independent of pair
> and view, and let it nominate the `B` highest-scoring pairs. Let demand
> `d_t ≥ 0` with `D_t = Σ_p d_t(p) > 0`, and let
> `π_t = (Σ_{p∈S(t−1)} d_t(p)) / D_t` and
> `cov_t = (Σ_{p∈top-B} d_t(p)) / D_t`. If the weights satisfy **lag-1
> dominance**, `w₁ > Σ_{s≥2} w_s`, then
>
> ```
> |S(t−1)| = B  ⟹  cov_t = π_t
> |S(t−1)| > B  ⟹  cov_t ≤ π_t
> |S(t−1)| < B  ⟹  cov_t ≥ π_t
> ```

**The cases are on the budget `B`, not on `K = |S(t)|`.** `K` does not appear in
the theorem at all. It enters only because E5 chooses `B = K`.

**Assumptions required:** `w ≥ 0`, independent of pair and view; the tail
`Σ_{s≥2} w_s` converges; dominance is **strict**; `d_t ≥ 0`; `D_t > 0`. No
assumption on the demand weights beyond non-negativity, and none on `|S(t)|`.

### Proof

Under strict dominance a pair in `S(t−1)` scores at least `w₁`, and a pair not in
`S(t−1)` scores at most `Σ_{s≥2} w_s < w₁`. Every member therefore outranks every
non-member, with no tie across the boundary. Hence

- `|S(t−1)| = B` ⟹ `top-B = S(t−1)`;
- `|S(t−1)| > B` ⟹ `top-B ⊊ S(t−1)`;
- `|S(t−1)| < B` ⟹ `top-B ⊋ S(t−1)`.

Because `d_t ≥ 0`, the set function `A ↦ Σ_{p∈A} d_t(p)` is monotone under
inclusion. Applying it to the three containments and dividing by `D_t` gives the
three cases. Ties **within** `S(t−1)` are immaterial: cases 1 and 3 do not depend
on which members are chosen, and case 2 needs only `top-B ⊆ S(t−1)`. ∎

### Why unequal demand weights do not break it — the critical question

They cannot, and the reason is structural. The RWC score depends only on set
membership `1[p ∈ S(s)]`; it never reads `d_t`. So the ranking — and therefore
the containment relation between `top-B` and `S(t−1)` — is fixed independently of
the weights. The weights enter only afterwards, through a monotone non-negative
set function applied to both sides of an inclusion. Any `d_t ≥ 0` gives the same
three cases, including the hub-union pattern where hub-to-hub pairs carry 2 and
all others carry 1.

### Verification (mathematical, not empirical)

**B decoupled from `|S(t)|`, unequal weights** — 5-element universe, all
`(S(t−2), S(t−1), S(t))` triples, four demand patterns (uniform; one
double-weight pair; two double-weight pairs; strictly increasing), five dominant
weight vectors, `B ∈ {1..6}`:

```
tested 3,574,920 combinations
  case eq: 0 violations
  case le: 0 violations
  case ge: 0 violations
```

This closes a real gap: E5's own searches (B4, B5) set `K = len(S0)` in every
instance, so **neither ever tested `B ≠ |S(t)|`**, and B4 used uniform demand
throughout.

**The `K`-version is false when `B ≠ K`.** Stating the cases on `K = |S(t)|`
while the budget is `B ≠ K` admits counterexamples on a 2-element universe under
last-observation weighting:

| case | `S(t−2)` | `S(t−1)` | `S(t)` | `K` | `B` | `π` | `cov` |
|---|---|---|---|---:|---:|---:|---:|
| equality | `{a}` | `{b}` | `{a}` | 1 | 2 | 0.0000 | 1.0000 |
| `≤` | `{a}` | `{b,c}` | `{a}` | 1 | 3 | 0.0000 | 1.0000 |
| `≥` | `{a}` | `{a,b}` | `{a,b,c}` | 3 | 1 | 0.6667 | 0.3333 |

The first row is decisive: `|S(t−1)| = 1 = K`, so the `K`-version asserts
`cov = π = 0`, while the measured coverage is 1.

---

## 5. Relationship to the E5 results

**E5's numerical results stand unchanged.** Every check it ran used `B = |S(t)|`,
where the frozen statement and the corrected statement coincide.

| E5 check | Status after audit |
|---|---|
| B1 — dominance ⟺ `α > ½` | Sound. Note the weight vector is truncated at `T = 24`, so `α = 0.5` registers as dominant by `≈ 6×10⁻⁸`; in the infinite series it is exactly the boundary. Worth a footnote, not a correction |
| B2 — constant support ⟹ `cov = π` to `<1e-12` | Sound. `B = K = \|S(t)\|` and `\|S(t−1)\| = \|S(t)\|`, so this is case 1 |
| B3 — counterexample to the original conjecture | Sound and unaffected |
| B4, B5 — 13,500 + 40,000 instances, 0 violations | Sound **but incomplete**: `B = \|S(t)\|` always. Now extended by the 3.57M-combination search above |
| B6 — "measurements match the corrected theorem exactly" | **Reasoning is wrong, assertion happens to hold.** It asserts equality for round-robin, but with `B = 30 > \|S(t−1)\| = 29` the theorem guarantees only `cov ≥ π`. Equality was observed, not predicted. It also compares against the zoo's cardinality-weighted `pi` |

---

## 6. The above-`π` rows — what they mean

Question: is EWMA at `0.6158` against `π = 0.6068` (n=16, VRF) a violation?

**Answer: (B), expected behaviour because `B > |S(t−1)|`** — with a second,
independent cause.

1. **The budget exceeds the support in 100% of views**, in every configuration,
   because `B = m(n−1) = 30` while `K_t = m(n−1) − \binom{m}{2} = 29`. That is
   case 3, which predicts `cov ≥ π`. Every above-`π` row is the predicted
   direction.
2. **On stochastic schedules the support also varies.** When `sched[t] ==
   sched[t+1]` the two stars coincide and `|S(t)|` drops from `2n−3` to `n−1`
   (29 → 15 at `n = 16`). This deepens case 3 and explains why the excess is
   largest on `weighted` (0.6606 vs 0.6427), where a few validators lead
   repeatedly, and vanishes on round-robin, where consecutive leaders always
   differ.

It is **not** a theorem violation, not a normalisation artefact, and not an
implementation error. It is the `|S(t−1)| < B` branch behaving exactly as stated.

Round-robin showing `cov = π` exactly is consistent — case 3 permits equality —
but it is not *guaranteed* by the theorem, and the manuscript must not present it
as a confirmation of the equality case.

---

## 7. The periodicity counterexample — unaffected

The periodicity learner reaches coverage `1.0000`. This does not contradict
Theorem B, for a reason independent of everything above: its score is a table
keyed on `t mod P`, so its weights depend on the view index, violating the
requirement that `w` be independent of `t`. It is not an RWC predictor. The same
applies to `markov1` (0.9742), whose score is keyed on the previous view's
highest-degree vertex.

**Does `B > K` affect this?** No, and the result is robust in both respects:

- On round-robin the support is exactly periodic with period `n`, so predicting
  `S(t−n)` reproduces `S(t)` exactly; coverage is 1.0 for any `B ≥ K_t`, hence
  also at `B = K_t = 29`.
- Against the **demand-weighted** `π = 0.5667` rather than the cardinality
  `0.5517`, coverage is still 1.0.

The class restriction stands under either weighting and either budget. This is
the one conclusion in the zoo that is entirely insensitive to the defects found
here.

---

## 8. Does any numerical result change interpretation?

| Result | Changes? | Detail |
|---|---|---|
| Theorem A, `π(n,m,k)` | **No** | Demand-weighted throughout; independently reproduced here as `17/30` and `33/62` |
| E1 `ρ = 0`, `m`, `k`, `π` | **No** | Demand-weighted; unaffected |
| E2 `4.22×10⁻⁴` across `n = 4…32` | **No** | Demand-weighted; unaffected |
| E5 B1–B5 | **No** | Correct at `B = \|S(t)\|`; verification now strictly broader |
| E5 B6 | **Rationale only** | Assertion holds; its stated reason is wrong (see §5) |
| E4, E4-TTL, E6, E7, E8 | **No** | Do not use the RWC coverage definition |
| **Predictor zoo `pi` column** | **Yes — relabelling** | It is cardinality persistence, not `π` of Definition 4. Correct demand-weighted values are in §3 |
| **Predictor zoo `ewma`/`last` columns** | **Yes — reinterpretation** | Measured at `B = K_t + 1` under cardinality weighting. Equality with `pi` on round-robin is a coincidence of that setup, not the equality case of Theorem B |
| Periodicity / markov1 exceeding `π` | **No** | Robust to weighting and budget (§7) |
| `freq` far below `π` (0.194 vs 0.552) | **No** | Uniform weighting fails dominance; the theorem says nothing about it, and no case is claimed |

**No frozen result is mathematically uninterpretable.** The zoo's numbers are
internally consistent measurements of a well-defined quantity — cardinality
persistence at budget `m(n−1)`. They are simply not the quantity the manuscript
calls `π`.

---

## 9. Does any experiment need rerunning?

**Not to preserve correctness — no result is invalid.** But the manuscript has a
choice, and it is the user's to make.

| Option | Effect | Cost |
|---|---|---|
| **A. Relabel** | Report the zoo as cardinality persistence at `B = m(n−1)`, state that it sits in the `\|S(t−1)\| < B` branch, and cite it only for the class restriction (§7), which is robust | None. No rerun. Weaker: Table 5 no longer displays the `π` used elsewhere, and a reviewer comparing 0.5517 to Theorem A's 0.5667 will ask why |
| **B. Rerun the zoo** at `B = K_t` with demand-weighted coverage and `π` | Table 5 then reports the same `π` as the rest of the paper, and lands in the equality case | Breaks the freeze; needs a new tag; ~minutes of compute. The periodicity and markov1 conclusions would not change (§7) |

**Recommendation: B**, because the zoo's role in the manuscript (§5, Table 5,
Fig. 4) is to display predictor coverage *against `π`*, and that comparison is
only legible if `π` means the same thing there as in Theorem A. Option A leaves a
0.015 discrepancy in the paper's most scrutinised table with no visible
explanation.

**I have not rerun it.** Per the standing instruction, a rerun is reported as a
decision, not taken silently.

---

## 10. Required manuscript changes

1. **§0 notation lock** — split `K` and `B`. `K_t = |S(t)|`; `B` = nomination
   budget; note `D_t = Σ_p d_t(p)` and `K_t = D_t − \binom{m}{2}` for hub-union.
   The current lock's "support size = prediction budget" must go.
2. **§5, Theorem B** — state the three cases on `B`. Add that `|S(t)|` plays no
   role. Keep "lag-1 dominance" as a condition on the weight vector.
3. **§5, proof** — add the sentence that RWC scores read only set membership, so
   unequal demand weights cannot affect the ranking; the weights enter through a
   monotone non-negative set function.
4. **§5, verification** — report the extended search (`B` decoupled, unequal
   weights, 3.57M combinations, 0 violations) alongside E5's 13,500 + 40,000, and
   state plainly that E5's own searches fixed `B = |S(t)|`.
5. **§5, Table 5** — label the weighting and the budget explicitly, whichever
   option is chosen in §9.
6. **§5, class restriction** — unchanged in substance; note the robustness in §7.
7. **§3** — already corrected: `K` is defined as `|S(t)|` and nothing else, and
   `B` is introduced as a separate symbol.
8. **Footnote on `α = 0.5`** — the boundary case; dominant only by truncation in
   E5, exactly at the boundary in the recursive zoo implementation. State that
   the reported EWMA is at the edge of the class, not inside it.

---

## Provenance

Working tree at `research-freeze-v1` (`330b87b6`) plus this file.

**Freeze incident, disclosed.** During the §3 drafting turn I executed
`python3 research/general_pi.py` to read its G4 scope-fence output. That script
rewrites `research/results/G-general-pi-001.json` on every run, so it modified a
frozen result file. `git diff` showed the change was confined to the `utc`
timestamp (`2026-08-20T14:10:12` → `2026-08-21T14:42:29`); `formula`,
`asymptote`, and `max_abs_err_vs_simulation` were byte-identical. The file was
restored with `git checkout --` and the working tree now differs from
`research-freeze-v1` only by this audit document. **No scientific value changed**,
but the freeze was breached and the incident is recorded rather than omitted.
Lesson for later turns: several `research/*.py` programs write their result JSON
as a side effect of running, so they must not be executed to inspect output —
read the source or the stored JSON instead.

No other file under `research/results/` was written and no frozen document was
edited. The three verification programs used for this audit live in the session
scratch directory; they import `predictor_zoo` read-only and never call its
`main()`.
