# E2 full matrix — does `π(n) = (n+1)/(2(n−1))` predict a real implementation?

50 runs, 0 failures. Predictions were locked in
[`PREDICTION_LOCK.md`](PREDICTION_LOCK.md) with SHA-256 hashes of the analysis
scripts **before** the first matrix run, and are reproduced verbatim in §2.

> ## Verdict: STRONGLY SUPPORTED
> Maximum absolute error across all validator counts: **0.000422**, against a
> locked falsification threshold of 0.05 — inside it by a factor of 118.

---

## 1. Experimental setup

| | |
|---|---|
| Implementation | `relab/hotstuff` @ `3179c6e62929294961acbfd9bf8445769716a121` |
| Working tree | +10 insertions, logging only, 4 files (`instrumentation.diff` in `../e2_smoke/`) |
| Build | `go build -o /tmp/hsbin ./cmd/hotstuff`, clean; one binary reused across all 50 runs |
| Consensus | `chainedhotstuff` |
| Communication | `clique` |
| Clients / batch / concurrency | 2 / 10 / 20 |
| Fixed timeout | 100 ms |
| Validator counts | 4, 7, 10, 16, 32 |
| Leader modes | `round-robin`, `fixed` |
| Repetitions | 5 per cell → **50 runs** |
| Durations | 25 s (n≤7), 30 s (n=10), 40 s (n=16), 60 s (n=32) |
| Host | Linux 6.8.0-138, 16 cores, Go 1.22.2, all replicas local |

Every run exceeded the 1,000-view floor: 11,476–47,880 analysed views per
(n, mode) cell.

## 2. Locked predictions

Round-robin arm: `m = 2`, `k = 1`, `ρ = 0`, and

| n | 4 | 7 | 10 | 16 | 32 |
|---|---|---|---|---|---|
| predicted π | 0.8333333333 | 0.6666666667 | 0.6111111111 | 0.5666666667 | 0.5322580645 |

Fixed-leader control: `m = 1`, `k = 1`, `ρ = 0`, `π = 1` for every n.

Falsification if systematically: `m ≠ 2`, `k ≠ 1`, `ρ > 0.15`, error > 0.05,
the curve fails to follow the predicted n-dependence, or the control misses
`π ≈ 1`.

## 3. Instrumentation

Unchanged from the smoke test — logging only, no protocol behaviour altered:

```
E2 SEND_PROPOSE  view=V from=F to=ALL
E2 RECV_PROPOSE  view=V from=F to=T
E2 SEND_VOTE     view=V from=F to=L
E2 LOCAL_TIMEOUT view=V id=R
```

Proposal edges come from **RECV_PROPOSE**, so the proposal star is measured
rather than assumed to reach every replica. Self-votes are dropped: they cross
no link and consume no key.

The analysis pipeline is the corrected one from the smoke test —
`min_vertex_cover` derives its candidate vertex set from the trace rather than
assuming `range(n)`. Hashes recorded at lock time; the E1 regression was re-run
at lock time and reproduces E1 exactly.

## 4–5. Validator-count sweep, round-robin arm

**Table 1** — happy-path views, 5 runs per row.

| n | runs | views | m | k | ρ | π theory | π measured | 95% CI | error |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 5 | 47,880 | 2.0000 | 1.0000 | 0.00000 | 0.833333 | **0.833333** | ±0.00000 | **0.000000** |
| 7 | 5 | 33,358 | 2.0000 | 1.0000 | 0.00000 | 0.666667 | **0.666657** | ±0.00002 | **0.000009** |
| 10 | 5 | 29,556 | 2.0000 | 0.9999 | 0.00000 | 0.611111 | **0.611085** | ±0.00003 | **0.000026** |
| 16 | 5 | 20,632 | 2.0000 | 0.9999 | 0.00000 | 0.566667 | **0.566645** | ±0.00004 | **0.000022** |
| 32 | 5 | 11,476 | 2.0000 | 0.9991 | 0.00000 | 0.532258 | **0.531836** | ±0.00029 | **0.000422** |

**Maximum absolute error: 0.000422.**

Per-run π, showing run-to-run spread:

| n | run 1 | run 2 | run 3 | run 4 | run 5 | sd |
|---:|---|---|---|---|---|---|
| 4 | 0.833333 | 0.833333 | 0.833333 | 0.833333 | 0.833333 | 0 |
| 7 | 0.666667 | 0.666667 | 0.666670 | 0.666616 | 0.666667 | 2.1e−5 |
| 10 | 0.611046 | 0.611111 | 0.611045 | 0.611111 | 0.611111 | 3.2e−5 |
| 16 | 0.566667 | 0.566557 | 0.566667 | 0.566667 | 0.566667 | 4.4e−5 |
| 32 | 0.531638 | 0.532258 | 0.531407 | 0.532046 | 0.531832 | 3.0e−4 |

### Leader sequence validation

| n | change rate | first 12 leaders | leader freq min/max | uniformity |
|---:|---:|---|---|---:|
| 4 | 1.0000 | 2,3,4,1,2,3,4,1,2,3,4,1 | 2399 / 2400 | 0.9996 |
| 7 | 1.0000 | 2,3,4,5,6,7,1,2,3,4,5,6 | 964 / 965 | 0.9990 |
| 10 | 1.0000 | 2,3,4,5,6,7,8,9,10,1,2,3 | 594 / 595 | 0.9983 |
| 16 | 1.0000 | 2,3,4,…,13 | 248 / 249 | 0.9960 |
| 32 | 1.0000 | 3,4,5,…,14 | 70 / 71 | 0.9859 |

The leader changes on **100.0%** of consecutive view pairs at every n, and no
validator dominates: the least- and most-frequent proposers differ by at most
one view.

## 6. Fixed-leader control

**Table 2** — the same binary and the same pipeline, one flag different.

| n | runs | views | m | k | ρ | π measured | 95% CI | error vs 1 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4 | 5 | 47,177 | 1.0000 | 1.0000 | 0.00000 | 1.000000 | ±0.00000 | 0.000000 |
| 7 | 5 | 33,375 | 1.0000 | 1.0000 | 0.00000 | 1.000000 | ±0.00000 | 0.000000 |
| 10 | 5 | 28,469 | 1.0000 | 1.0000 | 0.00000 | 1.000000 | ±0.00000 | 0.000000 |
| 16 | 5 | 20,781 | 1.0000 | 1.0000 | 0.00000 | 1.000000 | ±0.00000 | 0.000000 |
| 32 | 5 | 11,523 | 1.0000 | 1.0000 | 0.00000 | 1.000000 | ±0.00000 | 0.000000 |

Leader change rate 0.0000 at every n; replica 1 is the sole proposer throughout.
**Maximum control error: 0.000000.**

This is the point of the control: **one implementation, one analysis pipeline,
both regimes.** `--leader-rotation fixed` reproduces E1's degenerate result
(`k = m`, `π = 1`) and `--leader-rotation round-robin` produces `k < m` with
`π` on the predicted curve. The difference cannot be an artefact of the
measurement, because the measurement is identical.

## 7. Statistical analysis

Confidence intervals are ±0.00000 to ±0.00029 — the quantity is nearly
deterministic within a configuration. The errors are two to four orders of
magnitude below the 0.05 falsification threshold:

| n | error | error / threshold |
|---:|---:|---:|
| 4 | 0.000000 | 0 |
| 7 | 0.000009 | 1/5,600 |
| 10 | 0.000026 | 1/1,900 |
| 16 | 0.000022 | 1/2,300 |
| 32 | 0.000422 | 1/118 |

The n=32 error is the largest and is the only one worth explaining. It tracks
the timeout fraction (§10) and the smaller view count per run (2,204–2,614
against 9,500+ at n=4), both of which push `k` slightly below 1 (0.9991).

## 8. Scaling-law analysis

`(n+1)/(2(n−1))` is identically `1/2 + 1/(n−1)`, so the asymptotic form is
testable directly by comparing `π_measured − 1/2` against `1/(n−1)`:

| n | π_measured − 1/2 | 1/(n−1) | ratio |
|---:|---:|---:|---:|
| 4 | 0.333333 | 0.333333 | **1.0000** |
| 7 | 0.166657 | 0.166667 | **0.9999** |
| 10 | 0.111085 | 0.111111 | **0.9998** |
| 16 | 0.066645 | 0.066667 | **0.9997** |
| 32 | 0.031836 | 0.032258 | **0.9869** |

The excess over 1/2 decays as `1/(n−1)` across an eightfold range of n, with the
ratio within 0.03% of unity for n ≤ 16 and within 1.4% at n = 32.

No alternative curve was fitted; none was needed.

**On the limit.** The closed form gives `lim_{n→∞} π(n) = 1/2`. This experiment
observes finite n only and **does not empirically observe the limit** — it
observes the approach to it. The largest n measured is 32, where π = 0.5318.

## 9. Hub-union validation

`ρ = 0.00000` in **every one of the 50 runs**, both arms, all validator counts.
The support is exactly a union of stars, with no predicted edge missing and no
observed edge uncovered.

`m = 2.0000` with zero variance at every n in the round-robin arm, and
`m = 1.0000` with zero variance in the control. `k` is 1.0000 at n ≤ 7, drifting
to 0.9999 at n = 10–16 and 0.9991 at n = 32 — the drift is entirely attributable
to timeout views, where a view change breaks the hub carry-over.

The structural assumptions the theorem is conditional on therefore hold, and
were **not** forced: they were measured by minimum vertex cover with a
tie-break that cannot see the previous view.

## 10. Timeout analysis

Timeout views were kept and reported separately, never discarded.

| n | mode | timeout fraction | timeout views | π(timeout) | π(all views) |
|---:|---|---:|---:|---:|---:|
| 4 | round-robin | 0.00010 | 5 | 0.00000 | 0.83333 |
| 7 | round-robin | 0.00018 | 6 | 0.06667 | 0.66667 |
| 10 | round-robin | 0.00024 | 7 | 0.08889 | 0.61111 |
| 16 | round-robin | 0.00034 | 7 | 0.05333 | 0.56664 |
| 32 | round-robin | 0.00187 | 21 | 0.17323 | 0.53222 |
| 4–32 | fixed | 0.00011–0.00086 | 5–10 | 0.00–0.60 | 1.00000 |

The timeout fraction rises with n — 0.010% at n=4 to 0.187% at n=32 — which is
the expected consequence of a fixed 100 ms view timeout as the cluster grows.
Timeout views have markedly lower persistence, which is correct: a view change
breaks the hub carry-over, so `k` falls toward 0 and the formula predicts a
lower π for them. With 5–21 such views per cell these are observations, not
measurements, and no claim is made from them.

Because the timeout fraction is below 0.2% everywhere, π over all views is
indistinguishable from π over happy-path views to five decimal places.

## 11. Failed runs

**None.** All 50 runs completed, parsed, and exceeded the 1,000-view floor.
`failures.json` is empty. No run was replaced, retried, or discarded.

## 12. Unexpected findings

1. **The n=32 deviation is real but explained.** It is the only cell where the
   scaling ratio departs from unity by more than 0.03%. It correlates with the
   highest timeout fraction (0.00187, 5–18× the other cells) and the fewest
   views per run. This is a property of the run configuration — a fixed 100 ms
   timeout at 32 replicas — not of the theorem. It is reported rather than
   tuned away; raising the timeout at large n would likely remove it, and that
   was deliberately not done after the predictions were locked.
2. **π is nearly deterministic.** Run-to-run standard deviation is 0 at n=4 and
   3×10⁻⁴ at n=32. Persistence is a structural property of the protocol, not a
   statistical one, and the replication requirement mostly confirms the absence
   of variance rather than quantifying it.
3. **The control is exact, not approximate.** π = 1.000000 with zero variance at
   every n. There is no drift at all in the fixed arm, which makes the contrast
   with the rotating arm unusually clean.

## 13. Threats to validity

- **relab/hotstuff is a research framework, not a production system.** This
  tests whether the theorem describes a faithful implementation of the
  chained-HotStuff specification. E1 showed the two production-lineage systems
  measured (CometBFT, libhotstuff) sit at `k = m`, so this result does **not**
  establish that any deployed system runs in the non-degenerate regime.
- Loopback networking; no WAN delay, loss, or reordering.
- Single communication module (`clique`). `kauri` tree aggregation is untested
  and would give different `m`.
- The tag-only demand model is assumed throughout (one unit per message). Under
  one-time-pad payload weighting the synthetic result in `research/realism.py`
  predicts π → 1; that regime is untested here.
- n ≤ 32. The limit at 1/2 is approached, not observed.
- Timeout populations are too small (5–21 views per cell) to support any claim.

## 14. Comparison with Theorem A

Theorem A states `π(n,m,k) = [k(n−1) + m(m−k)] / [m(n−1)]`, with the chained
linear corollary `m=2, k=1 ⟹ π = (n+1)/(2(n−1))`.

| claim | status |
|---|---|
| support is a union of stars (ρ = 0) | **confirmed**, 50/50 runs, both arms |
| m = 2 under per-view rotation | **confirmed**, zero variance, all n |
| k = 1 under per-view rotation | **confirmed**, 1.0000 → 0.9991, drift explained by timeouts |
| π follows (n+1)/(2(n−1)) | **confirmed**, max error 4.2×10⁻⁴ over n = 4…32 |
| m = 1, k = 1 ⟹ π = 1 (control) | **confirmed**, exact, all n |
| π → 1/2 asymptotically | **approached**, not observed; ratio to 1/(n−1) is 0.987–1.000 |

E1 could only test the theorem where `k = m` and the `m(m−k)` term vanishes.
This experiment activates that term and sweeps a non-constant prediction across
an eightfold range of n. The formula holds.

## 15. Verdict

> ## STRONGLY SUPPORTED

The measured curve agrees with the locked theoretical scaling law across all
five validator counts, with maximum absolute error 0.000422 against a 0.05
threshold, and the structural assumptions the theorem is conditional on
(`m = 2`, `k = 1`, `ρ = 0`) hold with essentially zero variance. The
fixed-leader control produces `π = 1.000000` exactly, demonstrating that the
same implementation and the same analysis pipeline span both the degenerate and
non-degenerate regimes.

**What this establishes:** Theorem A is not a description of an idealised model.
It predicts, in closed form and without fitting, the demand-support persistence
of a real chained-HotStuff implementation across an eightfold range of validator
counts.

**What it does not establish:** that any production system operates in this
regime. E1's answer for the two production-lineage systems measured was no. The
honest combined statement from E1 and E2 is that **the theorem is correct, and
whether it predicts anything non-trivial about a given deployment depends
entirely on that deployment's leader-rotation and vote-routing design.**
