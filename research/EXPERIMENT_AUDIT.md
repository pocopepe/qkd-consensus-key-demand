# Experiment audit

## Per-experiment summary

| Exp | Question | Configuration | n / runs / views | Controls | Primary result | Failure mode found | Paper status |
|---|---|---|---|---|---|---|---|
| **E1** | Does the hub-union model describe real BFT? | CometBFT v0.40.0 `dc83065`; libhotstuff HEAD; logical-message instrumentation | n=4; 6+3+2 runs; 79.6k + 1.5k views | D-core vs D-all message models; induced-rotation arm | `ρ = 0.0000`; error ≤ 0.0013; **both at k=m** | Protobuf decoder discarded 100% of messages (default-valued fields) | **Include** — as the "production systems sit at k=m" result |
| **E2 smoke** | Does relab/hotstuff give k<m? | chainedhotstuff + clique + round-robin | n=4; 1 run; 7,385 views | prediction locked in the task | m=2, k=1, ρ=0, π=0.833333 exactly | `min_vertex_cover` assumed `range(n)`; 1-indexed IDs broke it | Include as pilot |
| **E2 full** | Does π(n) hold across n? | same; + fixed-leader control | n ∈ {4,7,10,16,32}; 50 runs; 11k–48k views/cell | **Fixed-leader control arm**; predictions + script hashes locked pre-run | **max error 4.22e−4**; control π=1.000000 | none (0 failures) | **Core evidence** |
| **E4** | Does π change an engineering decision? | hub-union; per-pair pools | n=16; 6 π × 20 seeds | reactive + structural arms | 256× rate sweep → Δhit 0.0000; waste ∝ 1−π (corr .983) | Flat bit-sizing inflated structural waste | Include (Q1, Q3); **report Q2 as unsupported** |
| **E4-TTL** | Does the ceiling survive TTL>1? | TTL ∈ {1,2,4,8} | n=16; 10 seeds/cell | fresh-vs-stale separation | fresh ≤ π at every TTL; total exceeds π by +0.73 | — | **Include** — the fresh/total distinction |
| **E6** | Does it survive a shared pool? | one shared pool; C ∈ {10, 2.5, 0.75} | n=16; 4 π × 4 TTL × 3 pred × 10 seeds | fifo vs random admission | fresh ≤ π (+0.0043/48 cells); π=1 still starves 26.6% | Regimes first defined on refill → zero contention; deterministic arming was a hidden priority rule | Include |
| **E7** | Does burstiness explain E1/E6? | E1 burst generator on E6 pool | n=16; 3 arms × 2 cap × 4 TTL × 10 seeds | **mean-matched control arm** | INTERACTION NOT CONFIRMED | — | Include as a negative result |
| **E8** | Does hop amplification explain it? | abstract amp ∈{1,2,4,8}; + E1 real topology | n=16; 2 wl × 2 cap × 4 TTL × 10 seeds | **amp=1 regression vs E7: 0.0000** | direction reproduced, magnitude not | Hypothesised mechanism (footprint) was wrong | Include, heavily qualified |
| **E5** | Is Conjecture B true? | analytic + exhaustive + random | 13.5k exhaustive, 40k random | counterexample search | Conjecture **refuted**, replaced by Theorem B | — | **Core evidence** |

---

## Reproducibility

**Good.** Every experiment has a runnable script under `research/`, results are
JSON under `research/results/`, and each report has a README with the exact
commands. E1 and E2 record upstream commits (`dc83065`,
`3179c6e62929294961acbfd9bf8445769716a121`) and the instrumentation diff is
saved (`e2_smoke/instrumentation.diff`, 11 insertions of logging, 0 logic).

**Gap.** The repository is **not a git repository** (`git status` fails). There
is no commit history, so "the code that produced result X" is identified only by
file content at the time of writing. **Initialise a repo and tag before
submission.**

## Randomness and seeds

Seeds are explicit integers (`range(10)` / `range(20)`) passed to
`np.random.default_rng(seed)` and recorded in the result JSON. Runs are
independent in the sense that each constructs a fresh generator from a distinct
seed. **Adequate.**

One caveat: within a run, the same `rng` drives workload, admission order and
service order. That is documented but means those three streams are correlated
across a run. It does not bias the comparisons, which share seeds across arms.

## Statistics

- **E2** reports mean, per-run values, and 95% CI (±0.00000–0.00029). Adequate.
- **E4–E8** report means over 10–20 seeds; CIs are computed and stored in JSON
  but are **not surfaced in every printed table**. Quantities are
  near-deterministic within a cell (sd ≈ 1e-4), so this is a presentation gap,
  not an inferential one.
- **No hypothesis tests.** Given effect sizes of 0.2–0.7 against sds of 1e-3,
  significance testing would be theatre. Effect sizes and CIs are the right
  reporting and are present.

## Parameter selection — the honest accounting

Parameters chosen **before** observing results: E2's locked π values and script
hashes; E6's capacity regimes (first attempt); E7's capacities; E8's amp sweep
and capacities.

Parameters changed **after** observing results, each documented in the relevant
report:
- **E6**: contention regimes were redefined from refill-rate to capacity after
  the first definition produced zero contention in all 48 cells. The new
  definition was derived from the outstanding-reservation requirement, not
  tuned for an outcome. *Disclosed in the E6 report §1.*
- **E4**: bit-sizing changed from a flat amount to per-pair predicted demand
  after it was found to inflate structural waste. *Disclosed in E4 §1.*
- **E6**: admission order parameterised (fifo/random) after the deterministic
  order was found to be a hidden priority rule. **Both are reported.**

None of these changed a headline direction. All are recorded in the reports;
none should be removed for the paper.

## Prediction locking

**E2 only.** `PREDICTION_LOCK.md` fixes the five π values, the falsification
criteria, and SHA-256 hashes of all three analysis scripts, together with a
regression check against E1 traces, before the first matrix run. That is the
strongest methodological artefact in the project and should be cited in the
paper's evaluation section.

E4–E8 state hypotheses in advance in their task specifications but do not hash
the analysis code. Weaker, and worth saying so.

## Implementation modifications

- **libhotstuff**: `#include <cstdint>` added to five headers (GCC 13
  compilation fix). No behaviour change. Disclosed.
- **relab/hotstuff**: +10 insertions, logging only, 4 files. Full diff saved.
  Disclosed.
- **CometBFT**: no source modification; log level raised and scoped to
  `p2p:debug`, and `timeout_commit` lowered to 100 ms for wall-clock reasons.
  Both disclosed.

## Measurement validity

The key question: does the measured quantity correspond to the theoretical one?

- `π` is computed **demand-weighted** from the trace, matching the definition.
  Independently recomputed here from `n16_roundrobin_run1.json` without the
  shared code: **0.566558** against a reported 0.566645 and a predicted
  0.566667. **Valid.**
- `m` is the **minimum vertex cover** of the observed support — determined, not
  chosen — with a lexicographic tie-break that cannot see the previous view, so
  `k` cannot be inflated. **Valid.**
- `ρ` is over-prediction residual, and being 0 means the star-union model
  predicts no edge that is absent. **Valid.**
- **fresh vs stale hits** is the one measurement that carries the whole
  operational argument, and it is defined by the reservation's creation view, a
  recorded field, not by a latency threshold. **Valid.**

## Simulation limitations — which conclusions rest only on simulation

| Conclusion | Basis |
|---|---|
| T1–T9, Theorem B | Analytic + exhaustive/random verification |
| `ρ = 0`, m, k, π in real systems (E1, E2) | **Real implementations** |
| Instruction count, commit cost, fast-path latency | **Real kernel measurement** |
| KME fetch latency | **Real implementation**, loopback |
| π as a hit-rate ceiling (E4) | Simulation only |
| Waste ∝ 1−π (E4) | Simulation only |
| Fresh/total distinction (E4-TTL) | Simulation only |
| Shared-pool contention, TTL, amplification (E6–E8) | Simulation only |

**Everything in C4 and C5 is simulation.** The real-system evidence covers the
communication-structure claims (C1–C3) and the kernel/KME measurements, and
nothing else.
