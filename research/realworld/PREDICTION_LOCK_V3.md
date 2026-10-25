# Prediction lock — V3: held-out replication on Aptos mainnet (Cycle 3)

Written 2026-09-21T20:17Z, **before any held-out epoch is fetched** (only the epoch choice exists).
Amendments are dated and appended below, never edited in.

## Design (fixed)

- 40 completed epochs, drawn by seeded shuffle (`v3-epoch-select-2026-09-22`) from the 76 retained epochs never
  examined before; the 36 already examined (sample A and campaign v2) are excluded by construction. Chosen:
  17270, 17279, 17280, 17283, 17284, 17285, 17287, 17292, 17293, 17297, 17298, 17299, 17300, 17301, 17303, 17304,
  17307, 17308, 17315, 17319, 17322, 17324, 17325, 17327, 17328, 17331, 17332, 17339, 17343, 17345, 17347, 17348,
  17349, 17350, 17351, 17352, 17353, 17354, 17356, 17360 (raw_v3/_epoch_table.json).
- 6000 consecutive rounds per epoch at a seeded offset (`v3-offset-2026-09-22`): 240,000 rounds, four times
  campaign v2's 60,000.
- Analysis: the locked `v2_analyze.py`, unchanged, run through `v3_analyze.py` (parallel per-epoch computation,
  then v2's own verdict code). On two v2 epochs the wrapper reproduces the archived v2 per-epoch results exactly.
- Aptos's own proposal-and-vote support is at k = m (AIP-89: votes are broadcast). Every statistic here is a
  property of the leader schedule or of the quorum-certificate record, not of Aptos's message-level persistence.

- Fetching: oldest epochs first (retained history is pruned from the old end; an epoch from campaign v2 had
  already been pruned when this lock was written). Optional API key, adaptive pacing, and retry passes; none of
  these can change which data is fetched. Any chosen epoch that cannot be fetched is reported as missing, with no
  substitution. An optional full-epoch archive (raw_v3_full/) is not read by this lock's analysis.

## Predictions

**Replication (v2's code and bands, unchanged):** the v2 verdicts recur:
H1 K_LT_M_DOMINANT (distinct-leader rate, CI lower bound >= 0.90) · H1q STAKE_COLLISION_SUPPORTED
(repeat rate / sum s_i^2, CI within [0.8, 1.2]) · H3 SUPPORTED (schedule pi - Corollary 2, CI within +-0.002) ·
H8 QUORUM_TRUNCATED (>= 99% of rounds) · H2R NON_IID · H2b STATIC_HETEROGENEITY_EXPLAINS (residual CI within
+-0.05) · H10 LOW_FAULT_RATE (<= 1% of rounds) · H6 NO_LEARNER_EXCEEDS_PI (margin 0.02) ·
**H9 LIVENESS_BOUND_FAILS** (fewer than 90% of epochs show >= 98% of stake live; predicted to fail again, because
v2 traced its failure to validators that never participate).

**Directional (the two misfits the reviewers flagged; read from V3_RESULTS.json's intervals):**
- D1: the repeat-leader rate exceeds the stake-collision value: H1q's 95% CI lower bound > 1.
- D2: the schedule-driven persistence exceeds Corollary 2 (stake only): H3's 95% CI lower bound > 0.
If D1 and D2 hold, the paper states that Corollary 2 is measurably misspecified for Aptos. An activity-weighted form
of Corollary 2 (reputation classes of AIP-1) will be specified in a dated amendment, calibrated on the v2 epochs
only, **before** any code that computes it reads raw_v3; it is not part of this lock.

## Data that existed when this lock was written

The v2 campaign's 30 epochs and sample A (all excluded here), and the epoch choice above. No round of any chosen
epoch has been fetched.

## Revision history

- 2026-09-21T20:26Z: revised **before any held-out epoch was fetched** — fetcher gained key support, adaptive pacing and an
  archive mode (hash updated). Its request path returned data identical to the archived v2 data on epoch 17323.

## Hashes at lock time

    v3_fetch.py                  9bc4104b345f4ff61e382acf917e897d0b9c4dbad16affe70587f60ede2b4257
    v2_fetch.py (imported)       52542364bb12c4a3568b24ff2d33455eb9e519a72ba4255e8903b1f5ecd1aa6a
    v3_analyze.py                128f463fcd2a1adff9e10289fbac4b36c3356b3d6d1dce147385c2e52ade73d1
    v2_analyze.py (imported)     5deb73ed54a43ce2096451286ab20972aafd95df8d8587883772d55ef207109f
    raw_v3/_epoch_table.json     1382a59b321346c98685569993f7d8ac878d736c676ca8b0abc2f2d73e765a75

## Amendment 1 (2026-09-21T20:47Z): activity-weighted Corollary 2 — locked before any code computing it read raw_v3

Written while raw_v3 is being fetched; cor2_activity.py has read **only** raw_v2 (development epochs).
Design (cor2_activity.py): AIP-1's ProposerAndVoterV2 rule — per round r, weight 1 if the validator's proposer
failure rate over rounds (r-10n-20, r-20] exceeds THR, 10 if it had no proposer rounds there and no
quorum-certificate votes over (r-n-20, r-20], else 1000; times stake; independent draw per round. Evaluated rounds
are those whose proposer window lies inside the fetched data. THR = 0.10, calibrated on raw_v2 (results were
insensitive to THR in 0.05–0.50). Stake-only Corollary 2 is computed on the same rounds.

| ID | Prediction | Band | Development value (raw_v2) |
|---|---|---|---|
| AW1 | activity weighting reduces the repeat-leader misfit | per-epoch (ratio_stake - ratio_activity): 95% CI lower bound > 0 | +0.0215 [+0.0184, +0.0252] |
| AW2 | activity weighting brings Corollary 2 closer to the schedule-driven persistence | per-epoch (\|diff_stake\| - \|diff_activity\|): 95% CI lower bound > 0 | +0.0001 [-0.0001, +0.0002] (not significant: may fail) |
| AW3 | descriptive | ratio_activity and diff_activity reported with intervals; if ratio_activity's CI still excludes 1, the paper states that activity weighting explains only part of the excess | ratio 1.0446 [0.9495, 1.1381] |

    cor2_activity.py                            6f72c5a4ea6bf08d76517191fb56ff511121a9dfe31cb9dd27134b213c361b6e
    cor2_activity_v2_calibration.json           c507eea6ab6cb9e09b8d3cc924d0d9886690c0db5be3d1891156cc393187ad67
