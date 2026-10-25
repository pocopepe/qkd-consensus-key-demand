# Prediction lock — campaign v2 (Aptos mainnet, held-out, publication-scale)

Written 2026-09-18T11:31:15Z, **before any v2 epoch was fetched**. The fetcher
(`v2_fetch.py`) contains no analysis, so it cannot see a result; the analyser
(`v2_analyze.py`) was developed only against **sample A** = the epochs already
seen (17314 in Phase 0; 17265, 17266, 17267, 17286, 17305 in campaign v1),
which are excluded from v2 by construction. Nothing below may change after
the held-out data is seen; deviations are reported as errors, not revisions.

## Why a v2 exists (a correction to v1, stated first)

Post-hoc inspection of the v1 data with stake weights showed that in **every**
round of all five v1 epochs the stake that signed lies in
[0.6667, 0.6941] = [2/3, 2/3 + largest validator share]. The on-chain vote
bit-vector is therefore **quorum-truncated**: the aggregating leader stops at
the first 2/3 of stake to arrive. v1's "participation p = 0.60" is *not*
validator participation, and "absent" means "not among the fastest 2/3 of
stake to reach the next leader", not "offline". v1's locked verdict label
(recurrence far above the IID band) stands as a measurement; its
*interpretation* as a failure of full participation (A8) does **not**, and is
withdrawn in `FINAL_REPORT.md`. The paper's support S(t) is defined on
messages sent; a late vote is still a message. The bit-vector is a censored
lower bound on the vote star and cannot test A8.

v2 re-poses the questions so that each is answerable from what the chain
actually exposes, and scales the sample ~90x using the NewBlockEvent stream
(validated bit-identical to the v1 transaction path on sample-A epoch 17286:
0/133 mismatches in round, proposer, bit-vector, failed-proposer list).

## Design

- 30 epochs drawn by seeded shuffle (`v2-epoch-select-2026-09-18`) from all
  epochs in the fullnode's retained history, excluding sample A, the still-open
  newest epoch, and anything within 2M blocks of the prune horizon.
- 2000 consecutive blocks per epoch from a seeded random offset
  (`v2-offset-2026-09-18`), never starting at the reconfiguration block.
- Uncertainty: bootstrap over **epochs** (5000 resamples), as in v1.
- If fewer than 30 epochs are obtainable, all obtained epochs are analysed and
  the shortfall is reported; no epoch is dropped after its data is seen.

## Locked hypotheses and falsification bands

| ID | Claim | Statistic | Supported if | Refuted if |
|---|---|---|---|---|
| H1 | Production operates at k<m | distinct-proposer rate over consecutive rounds | 95% CI lower bound ≥ 0.90 | CI upper ≤ 0.10 (else MIXED) |
| H1q | Leader election is i.i.d. stake-weighted, so repeat rate = Σsᵢ² (spec-derived, no fit) | per-epoch observed repeat rate / Σsᵢ² | CI ⊂ [0.8, 1.2] | CI entirely outside |
| H3 | A3 holds in expectation: schedule-implied π equals the closed form E[π] = q + (q−r) + (q−r)·n/(2(n−1)) + (1−3q+2r)(½+1/(n−1)), q=Σsᵢ², r=Σsᵢ³ | per-epoch (implied − predicted) | CI ⊂ [−0.002, +0.002] | CI entirely outside |
| H8 | Vote bit-vector is quorum-truncated | fraction of rounds with signed stake ∈ [2/3, 2/3+s_max] | ≥ 0.99 pooled | < 0.99 |
| H2R | QC membership is not IID across validators (replication of v1 at scale, v1 bands) | absence recurrence vs (1−p) | CI lower − (1−p) ≥ 0.15 | within 0.05 of (1−p) |
| H2b | Recurrence is explained by *static per-validator heterogeneity*, with no temporal memory | second-half observed recurrence − Σaᵢ²/Σaᵢ from first-half rates | CI ⊂ [−0.05, +0.05] | CI entirely outside |
| H9 | Censoring-robust liveness: nearly all stake is demonstrably live | stake seen signing or proposing within the 2000-round window | ≥ 0.98 in ≥ 90% of epochs | otherwise |
| H10 | Production fault rate is low | pooled fraction of rounds carrying a failed-proposer index | ≤ 0.01 | > 0.01 |
| H6 | The real schedule leaks no structure to history-based learners | frozen zoo predictors on the real proposer sequence (600 views, 120 warm-up, B=|S(t)|) | no learner's CI-upper excess over mean π > 0.02; 0 per-view Theorem-B violations for `last`, `ewma0.7` | any learner exceeds, or any violation |

Sample-A (development) values, for the record and **not** evidence: H1 0.989;
H1q ratio 0.65 (7 repeat events — hints the i.i.d. model may over-predict
repeats; locked as the spec-derived prediction anyway, to be refuted if
wrong); H3 diff −0.0055; H8 1.000; H2R 0.755 vs 0.401; H2b +0.010
(CI too wide at ~65-round halves); H9 0.991; H10 0.000.

## Positive control (bands are attainable)

`v2_positive_control.json`: the full pipeline on synthetic data of the exact
campaign size (30×2000, real stake vector, i.i.d. stake-weighted leaders,
temporally independent heterogeneous quorum-truncated votes) returns
SUPPORTED on every hypothesis (H1q ratio CI [0.917, 1.016]; H3 CI
[−0.0008, +0.0001]; H2b CI [−0.0014, +0.0010]). A refutation on real data
is therefore informative, not an artefact of band width.

## Hashes at lock time

    v2_fetch.py                     6b8eb819027d6c350522b9773c6d33bd668d80064cd962edaf28c6f337431ecc
    v2_analyze.py                   5deb73ed54a43ce2096451286ab20972aafd95df8d8587883772d55ef207109f
    fetch_aptos_bitvecs.py          9a55969625450020645b4be20ee3caf464cc6b1c3526e0a35c347aa9d138b6cf   (source of reused v1 statistics)
    ../predictor_zoo_corrected.py   e2742ba284a6b03f3862e12cdcbc4cfd9cee454477bbc082d32b8dd351c5a810   (frozen, reused unmodified)

## Known limits, fixed in advance

- Proposal reception is not on-chain; H3/H6 concern the **schedule** and the
  hub-union construction under A8, not observed messages.
- H9 is a lower bound on liveness, not a participation measurement.
- One fullnode, one network vantage; retained history only (~11 days).

## Amendment 1 — fetcher robustness, before any v2 data existed (11:32:22Z)

The first launch fetched nothing: the older page of the epoch table is beyond
the fullnode's prune horizon and returns HTTP 410, which the fetcher retried
instead of treating as final. Fixed (410/404 are non-retryable; an unavailable
table page or epoch is logged and skipped, to be reported as a shortfall).
`raw_v2/` was empty at the time of this amendment; the fetcher contains no
analysis; `v2_analyze.py` and every band above are unchanged.

    v2_fetch.py (amended)           52542364bb12c4a3568b24ff2d33455eb9e519a72ba4255e8903b1f5ecd1aa6a

## Amendment 2 — independent verifier hashed before the locked analysis ran (12:14:21Z)

All 30 epochs fetched (2000 contiguous rounds each, one epoch per file, no
shortfall). `v2_independent_verify.py` shares no code with the primary
analysis and was validated on sample A only (exact agreement on 11
statistics, max diff 1.1e-16). Hashed here **before** `v2_analyze.py` was
run on any held-out epoch, so it cannot have been shaped by a result.

    v2_independent_verify.py        cb4b7dbaa35db33122a402a2eeded86cb0d6e934a7305a8a4e398a9e51f3b923

Transparency note: epochs 17310 and 17311 are in the held-out draw. Their
*boundaries* (start/end block heights and timestamps) were read during Phase 0
cost estimation (G0.2); no block content, proposer, or vote data from either
was inspected. They are retained, since dropping epochs after the draw is
exactly what this lock forbids.

## Post-hoc note (2026-09-22): H1's interpretation withdrawn, measurement stands

H1 was stated as "Production operates at k<m" and tested by the distinct-proposer
rate, on the assumption that Aptos sends votes to the next leader. Aptos
Improvement Proposal AIP-89 (Accepted, June 2024) states that every validator
broadcasts its vote and forms the quorum certificate itself. Aptos's own
proposal-and-vote support is therefore the complete graph, at k=m. The locked
statistic (0.9818 [0.9806, 0.9829]) is unchanged and is reported as a property of
the leader schedule only; the schedule-implied pi values (H3) are the persistence
of chained rotation driven by the Aptos leader sequence, not Aptos's own. See
research/FALSIFIED_CLAIMS.md F17.
