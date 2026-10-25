# Predictor zoo — old vs corrected

Two experiments now measure predictor coverage. **Both are valid.** They measure
different quantities, and this document says which is which so neither is cited
for the other's claim.

---

## The difference in one table

| | **OLD** — `P-predictor-zoo-001` (frozen) | **NEW** — `P-predictor-zoo-corrected-001` |
|---|---|---|
| Persistence | **cardinality** — `\|S(t) ∩ S(t−1)\| / \|S(t)\|` | **demand-weighted** — `Σ_{p∈S(t−1)} d_t(p) / D_t` |
| Budget | `B = m(n−1)` — hard-coded `2(n-1)`; **exceeds** `\|S(t)\|` by `C(m,2)` | `B = \|S(t)\|` — the support cardinality itself |
| Coverage | **cardinality** — `\|top-B ∩ S(t)\| / min(B, \|S(t)\|)` | **demand-weighted** — `Σ_{p∈top-B} d_t(p) / D_t` |
| Demand model | set union; hub-to-hub pair counted **once** | `d_t(p)` = distinct incident hubs; hub-to-hub pair counted **twice** |
| Tie-break | implicit — Python dict insertion order | explicit — `(−score, pair)`, identical for every predictor |
| Matches Theorem A? | **No** — 0.5517 at `n=16` vs `π(16,2,1)=0.5667` | **Yes** — to `1.11×10⁻¹⁶` |
| Matches manuscript Def. 4? | No | Yes |
| Source | `research/predictor_zoo.py` | `research/predictor_zoo_corrected.py` |
| Results | `research/results/P-predictor-zoo-001.json` | `research/results/predictor_zoo_corrected/` |

At `n = 16, m = 2`: `K_t = |S(t)| = 29`, `D_t = 30`, old `B = 30`, new `B = 29`.

---

## What each is good for

**OLD — keep, cite narrowly.** It remains a valid exploratory scope-limit record.
It established the finding that survives every definitional change: **a
periodicity-detecting learner and a first-order Markov learner both beat the
persistence ceiling on a deterministic schedule**, so the bound is class-specific.
That conclusion is robust to weighting and to budget, and is reconfirmed by the
corrected run. Cite the old zoo only as the exploratory pass that raised the
question.

**NEW — cite for every number that appears beside `π`.** Because its `π` is the
`π` of Theorem A and Definition 4, it is the only one of the two whose coverage
figures can be placed in the same table as the theorem.

---

## Why the old numbers are not wrong

The old zoo is internally consistent: `π` and coverage are both cardinality-based,
so their comparison is meaningful — for the cardinality-weighted quantity. It was
written to answer "does *any* history-based predictor beat the ceiling?", and for
that question the weighting is immaterial. The defect is one of **labelling**, not
of arithmetic: the column named `pi` is not the `π` the manuscript defines.

Its budget, `2(n−1)`, is the size of two stars counted with their shared edge
double-counted. It equals `D_t` numerically, but the code neither derives nor
documents it as a demand total, so it is best read as an off-by-`C(m,2)` support
budget. Its consequence is that `|S(t)| < B` in **100 %** of views in every
configuration, placing the old zoo permanently in Theorem B's `|S(t−1)| < B`
branch, where coverage is bounded **below** by `π`, not above.

That is the whole explanation of the old zoo's six apparent "ceiling exceeded by
EWMA" rows. Under corrected definitions **all six disappear**:

| `n` | schedule | old `ewma − pi` | new `ewma0.5 − π` |
|---:|---|---:|---:|
| 16 | shuffled_epoch | **+0.0013** | −0.0037 |
| 16 | vrf | **+0.0090** | −0.0430 |
| 16 | weighted | **+0.0179** | −0.0701 |
| 32 | shuffled_epoch | **+0.0007** | 0.0000 |
| 32 | vrf | **+0.0027** | −0.0230 |
| 32 | weighted | **+0.0078** | −0.0529 |

No RWC predictor's mean exceeds `π` anywhere in the corrected run.

---

## Neither file was modified

`research/predictor_zoo.py` and `research/results/P-predictor-zoo-001.json` are
byte-identical to `research-freeze-v1`. The corrected experiment is a new script
writing to a new directory. Nothing was overwritten, deleted, or copied forward —
every corrected quantity was recomputed from the corrected definitions.
