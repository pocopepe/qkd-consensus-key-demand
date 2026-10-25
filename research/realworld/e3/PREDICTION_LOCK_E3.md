# Prediction lock — E3 (chained HotStuff under emulated WAN latency and faults)

Written 2026-09-18T12:18:00Z, before any E3 campaign run. Development used three
short smoke runs only (n=8, n=64 WAN; n=16 one silent proposer; 20–40 s each,
ad-hoc geographies with seeds not used by the campaign), kept out of the
campaign and not counted as evidence.

## Why E3 exists

E2 validated π(n,2,1) on loopback with zero faults, where agreement to 4e-4
is close to guaranteed. E3 asks whether the structure and the value survive
conditions that can break them: real inter-city latencies (relab's built-in
WonderProxy matrix, 217 cities, injected per message at the receiver), a
different random geography per run, and silent-proposer faults. Unlike the
Aptos arm, every proposal reception and every vote *sent* is observed, so
A8 is measured here, not assumed and not censored.

Same instrumented source tree as E2 (worktree diff byte-identical to the frozen
`research/results/e2_smoke/instrumentation.diff`), same frozen parser
(`research/e2_parse.py`), same frozen structural analyser
(`research/e1_analyze.py::analyze`, unmodified).

## Design

- WAN arm: n ∈ {8, 16, 32, 64} × 5 geographies (city sample seeded
  `e3-geo-<n>-<g>`), round-robin rotation, 120 s, dynamic view timeout.
- Fault arm: n=16, same 5 geographies, silent proposers f=1 (id 4) and
  f=5 (ids 2,5,8,11,14 — non-adjacent in rotation order).
- Single 16-core host; load average recorded before/after every run and
  reported, since CPU contention is a confound for timeouts.

## A correction to the inherited "happy-path" statistic

The frozen analyser pairs each view with the previous *retained* view. Filtering
timeout views first therefore manufactures false adjacencies. That is
immaterial in E2 (≤ 21 timeout views in ≥ 11k) but not under WAN (15% of views
in the n=64 smoke). E3 runs `analyze()` on **all** views and afterwards selects
**adjacency-correct happy transitions**: view v counts only if v and v−1 are
both present and neither had a local timeout.

## Locked predictions and falsifiers

| ID | Prediction | Supported if | Refuted otherwise |
|---|---|---|---|
| P1 | The hub-union structure survives WAN latency | m=2 in ≥ 99% of happy transitions in every run, and mean ρ ≤ 0.05 in every run | |
| P2 | Spec-derived π(n,2,1) holds within E2's original locked tolerance, and any deviation is downward (incomplete stars) | per-n cell mean \|π_happy − π(n,2,1)\| ≤ 0.05 **and** π_happy ≤ π(n,2,1)+0.002 in every cell | |
| P3 | The participation-corrected π_p(n, p̂), p̂ = measured vote participation in the same views, is closer to the measurement than π(n,2,1) | closer in ≥ 80% of runs with p̂ < 0.995 (NOT_TESTABLE if < 5 such runs) | |
| F1, F5 | Silent proposers act only through lost hub carry-over: all-views π = (1−g)·π(n,2,1) + g·π(n,2,0), g = f/(n−f). Zero fitted parameters: 0.537778 (f=1), 0.369697 (f=5) | every run within ±0.03 | |

P3 is a one-measured-parameter model and is labelled as such; P2, F1, F5 use no
measured input. Smoke values (not evidence): n=8 π_happy 0.6249 vs 0.6429
(π_p 0.6362); n=64 0.5156 vs 0.5159; f=1 π_all 0.5387 vs 0.5378, post-fault
views exactly π(16,2,0)=0.1333.

## Hashes at lock time

    e3_driver.py                  de3294a13ad20c18e0d9c925dadb6637716d88d1f3921b7ae852b441744e35a5
    e3_analyze.py                 18408e0479c80ff74fe4cc545663cedcef4f491b8f3d4f3218b5b79949e214cf
    ../../e1_analyze.py           5cbfb8d28f70e97285ee09d9e29ccb0a2d7a8efde57c898334b09caeb055d4e9
    ../../e2_parse.py             b771493e02020ba6adf2e74b3e303944c18a06254a08bc29cb99cb36b8a2c2de
    ../pi_p_model.py              00acf59c5f2cca280d23e0e7e346aa3fd0da775f2aae670045b51febdc79c88a
    hotstuff binary               c7269ecd0c1e02f71d5a69b1c96d1ec21dbbf1e5c8faa29fa8494139c45c2a51

## Limits fixed in advance

Emulated, not real, WAN: latency is a per-message sleep at the receiver on one
host; no loss, jitter, or bandwidth limits. Round-robin rotation only. Faults
limited to silent proposers. n ≤ 64.

## Amendment 1 — post-run, instrumentation artefact found (2026-09-19T00:24Z)

The locked analysis was run first, unchanged, on the raw traces
(`E3_RESULTS.json`): P1, P2, F1, F5 SUPPORTED; P3 NOT_TESTABLE (2 eligible runs).

Inspection then showed proposal-reception counts above n−1 per view in some
runs. Cause: when a proposal arrives before the replica has entered its view,
relab re-dispatches the same `ProposeMsg` through the same handler
(`eventloop.DelayUntil`), so the frozen E2 logging line fires twice for one
network message. It cannot occur without latency: the frozen E2 traces contain
1 such duplicate in 2,543,313 proposal records. In E3 it is 733 of 827,404
records (0.089%). The paper defines demand per logical message, so the
de-duplicated trace is the correct measurement. The **same, unmodified, hashed**
`e3_analyze.py` was re-run on de-duplicated copies (`raw_dedup/`,
`E3_RESULTS_DEDUP.json`); after de-duplication no run exceeds n−1
proposal receptions per view (max 1.000; exactly complete in 13 of 20 WAN
runs, minimum 0.9984). [An earlier wording of this amendment said "exactly
complete in all 30 runs"; that was wrong and is corrected here.] No verdict changes; residuals shrink slightly
(max cell residual 0.0089 → 0.0070). Both result files are kept and both are
reported. No band, script, or run was changed.

Also disclosed: host load reached 25.6 during `wan_n16_g3`/`g4` from an
unrelated process; those runs are retained (their residuals, −0.0048 and
+0.0005, are unremarkable). The f=5 fault runs completed only 33–39 views each
in 120 s because five silent leaders stall the view-timeout clock; the F5
verdict rests on 177 views in total and is reported with that caveat.
