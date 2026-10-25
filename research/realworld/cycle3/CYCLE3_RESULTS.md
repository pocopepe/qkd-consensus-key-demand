# Cycle 3 — results against the locks

Generated from the result files named in each section (no hand-typed numbers). Locks: `e3/PREDICTION_LOCK_E3T.md`,
`theory/PREDICTION_LOCK_C1.md`, `PREDICTION_LOCK_V3.md` (with Amendment 1). The three locks were pushed before any of their held-out data existed; Amendment 1 was pushed while raw_v3 was being
fetched and before any code computing it read raw_v3.

## E3T — targeted single-role vote suppression (`e3/E3T_RESULTS.json`; 72 runs, n = 16 and 32, 6 geographies)

| ID | Band | Measured | Outcome |
|---|---|---|---|
| T1 | \|resid\| <= 0.002 in every lossy run | max 0.00153 over 60 runs | SUPPORTED |
| T2 (n=16) | CI of D excludes 0 and \|D - D_pred\| <= 0.5 D_pred | D = 0.00644 [0.00545, 0.00727]; D_pred 0.00635; role-blind 0.00006 | SUPPORTED |
| T2 (n=32) | CI of D excludes 0 and \|D - D_pred\| <= 0.5 D_pred | D = 0.00321 [0.00294, 0.00348]; D_pred 0.00328; role-blind 0.00002 | SUPPORTED |
| T3 (n=16) | \|a-g\|, \|b-other\| <= 0.5 D_pred = 0.00318 | +0.00032, -0.00024 | SUPPORTED |
| T3 (n=32) | \|a-g\|, \|b-other\| <= 0.5 D_pred = 0.00164 | -0.00011, -0.00013 | SUPPORTED |
| T4 | blind arm: both forms within 0.002, every run | max 0.00147 (Prop. 1), 0.00120 (role-blind) | SUPPORTED |
| T5 | none arm: Corollary 1 within 0.002, every run | max 0.00221 | **REFUTED** |
| T6 | selection guard within 0.10 per arm | a 0.129 vs 0.105; g 0.138 vs 0.103; b 0.122 vs 0.095; other 0.132 vs 0.102; blind 0.131 vs 0.098 | SUPPORTED |

**T5 failed as locked.** Cause, found after the locked run: the E3T pipeline omitted the de-duplication step (`e3c_dedup.py`)
that E3c/E3d apply to proposals the emulator re-dispatches, so a view whose proposal record is doubled counts one message twice.
Post hoc, the same locked analyser on de-duplicated traces (`e3/E3T_RESULTS_DEDUP_POSTHOC.json`; 285 of 2,413,156 records removed):
T5 max 0.00107 (SUPPORTED), T1 max 0.00057, T4 0.00057/0.00040;
D = 0.00644 (n=16), 0.00321 (n=32); every other verdict unchanged. Recorded as F19.

Independent cross-check (`e3/e3t_crosscheck.py`, no shared code with the analysers): D agrees with the locked values to 2e-17.

## C1 — Proposition 1 under real correlated absence (`theory/C1_RESULTS.json`; Cosmos Hub, 100 held-out windows per cell)

| Cell | R | mean \|effect\| | lost votes / view | distinct-leader share | Outcome |
|---|---|---|---|---|---|
| rr_random_n16 | 0.0109 | 2.87e-04 | 0.0152 | 1.000 | ok |
| rr_random_n32 | 0.0102 | 2.83e-04 | 0.0329 | 1.000 | ok |
| rr_random_n64 | 0.0058 | 3.28e-04 | 0.0798 | 1.000 | ok |
| rr_stress_n16 | 0.0114 | 2.32e-03 | 0.1221 | 1.000 | ok |
| rr_stress_n32 | 0.0159 | 1.10e-03 | 0.1290 | 1.000 | ok |
| rr_stress_n64 | 0.0211 | 5.37e-04 | 0.1333 | 1.000 | ok |
| stake_random_n16 | 0.1465 | 2.05e-04 | 0.0125 | 0.216 | descriptive |
| stake_random_n32 | 0.1276 | 1.36e-04 | 0.0162 | 0.420 | descriptive |
| stake_random_n64 | 0.0361 | 2.99e-04 | 0.0750 | 0.579 | descriptive |
| stake_stress_n16 | 0.2154 | 1.96e-03 | 0.1258 | 0.134 | descriptive |
| stake_stress_n32 | 0.0504 | 1.07e-03 | 0.1310 | 0.437 | descriptive |
| stake_stress_n64 | 0.0445 | 5.40e-04 | 0.1343 | 0.655 | descriptive |

C1A (R <= 0.15 in every round-robin cell): **SUPPORTED** (max R 0.0211). C1B: DESCRIPTIVE; stake-weighted schedules with repeated leaders are outside Proposition 1; R is reported per cell with the distinct-leader share.

## V3 — held-out Aptos replication (`V3_RESULTS.json`; 40 epochs x 6000 rounds = 240,000 rounds)

| ID | Band (v2's, unchanged) | Measured | Outcome |
|---|---|---|---|
| H1 | distinct-leader rate CI lo >= 0.90 | +0.98262 [+0.98215, +0.98310] | K_LT_M_DOMINANT (replicates) |
| H1q | repeat / sum s^2 CI within [0.8, 1.2] | +1.04076 [+1.01123, +1.06985] | STAKE_COLLISION_SUPPORTED (replicates) |
| H3 | schedule pi - Cor. 2 CI within +-0.002 | +0.00063 [+0.00004, +0.00123] | SUPPORTED (replicates) |
| H8 | >= 99% of rounds quorum-truncated | 1.0000 (signed stake 0.66667-0.70102) | QUORUM_TRUNCATED (replicates) |
| H2R | absence recurrence vs IID | +0.75871 [+0.75621, +0.76109] vs 0.40277 | NON_IID (replicates) |
| H2b | residual CI within +-0.05 | +0.02233 [+0.01948, +0.02507] | STATIC_HETEROGENEITY_EXPLAINS (replicates) |
| H10 | failed rounds <= 1% | 0.00038 | LOW_FAULT_RATE (replicates) |
| H6 | no learner exceeds pi (margin 0.02) | best learner excess -0.00856; Theorem B violations 0/38400 | NO_LEARNER_EXCEEDS_PI (replicates) |
| H9 | predicted to FAIL again (< 90% of epochs >= 98% live stake) | 0.45 of epochs | LIVENESS_BOUND_FAILS (replicates, as predicted) |
| D1 | H1q CI lower bound > 1 | 1.01123 | SUPPORTED |
| D2 | H3 CI lower bound > 0 | 4.43e-05 | SUPPORTED |

D1 and D2 hold: stake-only Corollary 2 is measurably misspecified for Aptos (leaders repeat more often than stake predicts).

## Amendment 1 — activity-weighted Corollary 2 (`COR2_ACTIVITY_V3.json`; THR = 0.10, 40 epochs)

| ID | Band | Measured | Outcome |
|---|---|---|---|
| AW1 | ratio_stake - ratio_activity: CI lo > 0 | +0.02828 [+0.02525, +0.03139] | SUPPORTED |
| AW2 | \|diff_stake\| - \|diff_activity\|: CI lo > 0 | +0.00012 [-0.00001, +0.00026] | **REFUTED** |
| AW3 | descriptive | ratio_activity +1.01559 [+0.98770, +1.04455]; ratio_stake +1.04387 [+1.01465, +1.07410]; diff_activity -0.00003 [-0.00065, +0.00059]; diff_stake +0.00041 [-0.00021, +0.00101] | descriptive |

AW3: the activity-weighted ratio's CI contains 1, so AIP-1's reputation classes account for the excess repeat rate;
AW2 failed as locked (flagged as likely to fail on the development data): the improvement in persistence is not
distinguishable from zero. On AW's evaluated rounds (each epoch's first 10n+20 rounds excluded) stake-only Corollary 2's
own misfit is not significant either (diff_stake above), so there is little left for the reweighting to remove.
