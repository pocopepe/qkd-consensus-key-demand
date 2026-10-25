# E2 smoke test — does relab/hotstuff produce `k < m`?

Single-run smoke test before the full matrix. Predictions were locked in the
task before the trace was inspected and are reproduced verbatim in §11.

> ## Verdict: PASS — proceed to full E2

---

## 1. Exact configuration

```
go run ./cmd/hotstuff run \
  --replicas 4 --clients 2 --batch-size 10 --max-concurrent 20 \
  --consensus chainedhotstuff --communication clique --leader-rotation round-robin \
  --duration 20s --fixed-timeout 100ms \
  --log-level info --log-pkgs "comm:debug,synchronizer:debug,votingmachine:debug"
```

Runs: 1. Host: Linux 6.8.0-138, Go 1.22.2, all replicas local.

## 2. Commit

`relab/hotstuff` @ `3179c6e62929294961acbfd9bf8445769716a121` (2026-07-14),
working tree clean before instrumentation.

## 3. Instrumentation diff

Logging only; **no protocol behaviour altered**. Full diff in
`instrumentation.diff` (93 lines, 11 insertions of substance, 0 deletions).

| file | change |
|---|---|
| `protocol/comm/clique.go` | logger field + ctor param; log `SEND_PROPOSE` before `sender.Propose`, `SEND_VOTE` before the leader branch |
| `protocol/comm/factory.go` | pass the existing `logger` into `NewClique` |
| `protocol/synchronizer/synchronizer.go` | log `RECV_PROPOSE` in the existing `ProposeMsg` handler; log `LOCAL_TIMEOUT` at the top of `OnLocalTimeout` |
| `twins/node.go` | pass `node.logger` to the changed `NewClique` signature (compile fix) |

Emitted records:

```
E2 SEND_PROPOSE  view=V from=F to=ALL
E2 RECV_PROPOSE  view=V from=F to=T
E2 SEND_VOTE     view=V from=F to=L
E2 LOCAL_TIMEOUT view=V id=R
```

Proposal edges are taken from **RECV_PROPOSE**, so the proposal star is measured
rather than assumed to reach every replica. Self-votes are dropped: a replica
voting for itself crosses no link and consumes no key.

## 4. Number of views

| | |
|---|---|
| views with demand | **7,385** (range 1–7,387) |
| happy-path views | 7,382 |
| views with a local timeout | 28 recorded; 3 fell inside the analysed window |
| proposals sent | 7,385 |
| proposal receipts | 22,155 = 7,385 × 3 |
| votes sent | 29,540 = 7,385 × 4 |
| pairwise records | 44,310 |

Comfortably above the ≥1000-view requirement.

## 5. Leader sequence

First 16 views: `2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 1, 2, 3, 4, 1`

All four replicas propose. **The leader changed on 399 of 399 consecutive view
pairs (100.0%)** — genuine per-view rotation, unlike either E1 implementation.

## 6. Timeout fraction

**28 / 7,385 = 0.00379 (0.38%)**. The happy path dominates, so the two
populations are reported separately rather than merged.

## 7–10. Measured `m`, `k`, `ρ`, `π`

| split | views | \|S\| | m | k | ρ | π measured |
|---|---:|---:|---|---|---:|---|
| all views | 7,384 | 5.000 | **2.0000 ± 0.0000** | **1.0000 ± 0.0000** | **0.000000** | **0.833333 ± 0.000000** |
| happy-path only | 7,382 | 5.000 | **2.0000 ± 0.0000** | **1.0000 ± 0.0165** | **0.000000** | **0.833333 ± 0.002744** |
| timeout only | 3 | 5.000 | 2.0000 ± 0.0000 | 0.5000 ± 0.5000 | 0.000000 | 0.750000 ± 0.083333 |

`ρ = 0` exactly: the support is a union of two stars with no missing edge, on
every one of 7,384 views.

## 11. Comparison with the locked prediction

Locked before the run:

> `m = 2, k = 1, ρ = 0`, and `π(4) = (4+1)/(2(4−1)) = 5/6 = 0.833333`

| quantity | predicted | measured | agreement |
|---|---|---|---|
| m | 2 | 2.0000 ± 0.0000 | exact |
| k | 1 | 1.0000 ± 0.0000 | exact |
| ρ | 0 | 0.000000 | exact |
| π | 0.833333 | 0.833333 ± 0.002744 | **\|Δ\| = 0.000000** |

Success condition `|π_measured − 0.833333| < 0.05` is met with a margin of
0.05, i.e. the error is below the resolution of the criterion.

Timeout views land at `k = 0.5`, `π = 0.75`, which the formula also covers:
`π(4, m=2, k=0) = 2/3` and `π(4, m=2, k=1) = 5/6`, and the three observed views
mix the two. With three views this is an observation, not a measurement, and it
is reported as such.

## 12. Representative per-view graphs

`figures/fig_e2_view_graphs.svg` — four consecutive views, minimum vertex cover
highlighted:

| view | leader | next leader | cover | edges |
|---|---|---|---|---|
| 201 | 2 | 3 | {2, 3} | 5 |
| 202 | 3 | 4 | {3, 4} | 5 |
| 203 | 4 | 1 | {1, 4} | 5 |
| 204 | 1 | 2 | {1, 2} | 5 |

Consecutive covers share exactly one vertex — `{3}`, `{4}`, `{1}` — which is
`k = 1` of `m = 2`, visible directly in the graphs.

## 13. Unexpected behaviour

**A bug in the analysis code, found because `m` and `k` disagreed with a `π`
that was already exact.**

The first analysis run reported `m = 2.5 ± 0.5`, `k = 2.0 ± 0.71`, `ρ = 0.083`
while `π` came out at exactly 0.833333. That combination is not physically
possible — `π = 5/6` is what `m=2, k=1` predicts — so the disagreement pointed
at the measurement rather than the system.

Cause: `min_vertex_cover` in `research/e1_analyze.py` searched candidate
vertices over `range(n)` = `{0,1,2,3}`. CometBFT and libhotstuff number replicas
from 0, so E1 was unaffected. **relab/hotstuff numbers them from 1**, so vertex
4 could never be selected; for view 102 the true cover `{3,4}` was unreachable
and the search returned `{1,2,3}` of size 3 instead.

Fix: derive the candidate vertex set from the edges present in the trace rather
than assuming `range(n)`. `π` was never affected, because it is computed from
demand directly and never touches the cover.

**Regression check.** Re-running E1 with the fix reproduces E1 exactly —
libhotstuff `m=1, k=1, π=1.0000`; CometBFT `m=2.991, k=2.990, π=1.0000` — so no
previously reported result changes.

Two smaller notes:

- The `SEND_VOTE` count is `4 × views`, including the leader's self-vote, which
  is logged before the self-collection branch. Dropped in parsing, as it crosses
  no link.
- An earlier trial without client load was timeout-dominated (`no command
  batch`, views advancing by TC rather than QC). The reported run uses
  `--clients 2 --batch-size 10`, which holds the timeout fraction at 0.38%.

## 14. Verdict

> ## PASS — proceed to full E2

Every locked prediction was met exactly: `m = 2`, `k = 1`, `ρ = 0`, and
`π = 0.833333` against a predicted `0.833333`.

The significance is what E1 could not deliver: **this is the first measurement
of the non-degenerate regime `k < m` in a real consensus implementation.** E1
validated Theorem A only where `k = m` and the `m(m−k)` term vanishes; here that
term is active and the formula is correct.

What the smoke test does *not* yet establish, and what the full matrix must:

- `π(4) = 0.833333` is a single point. The prediction that matters is the
  **`n`-dependence**, `π(n) = (n+1)/(2(n−1))`, which needs `n ∈ {7, 10, 16, 32}`.
  A one-point match is consistent with several wrong formulas.
- One run. Repetitions are needed for confidence intervals, though the observed
  variance is near zero.
- The `--leader-rotation fixed` control arm has not been run and must be, to
  show the same binary spans both regimes.
- The timeout population has three views. Either configure to produce more, or
  report it as unmeasured.
