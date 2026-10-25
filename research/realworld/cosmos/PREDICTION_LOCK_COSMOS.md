# Prediction lock — Cosmos Hub campaign (production participation, uncensored record)

Written 2026-09-19T07:47:43Z, before any campaign window was fetched. Development
data: 5 heights inspected in Phase 0 (33,000,000–33,010,000) and 54 blocks
inspected while writing the fetcher (33,034,110–33,034,149) — every one showed
180/180 precommits. Analysis code was exercised on synthetic windows only.

## Why this campaign exists

The Aptos arm cannot test full participation (A8): its on-chain vote record is
quorum-truncated. A CometBFT commit is not. It lists every validator slot with
an explicit flag (commit / nil / absent), collected by the next proposer until
it proposes. "Absent" still means "no precommit arrived in time", so this is a
lower bound on participation — but one that is not cut off at two-thirds.
Cosmos Hub gossips votes, so it sits at k=m with π=1 and nothing here tests the
closed form; the campaign measures A8 on a production validator set of ~180.

## Design

30 windows of 300 consecutive blocks, window starts drawn by seeded sample
(`cosmos-window-select-2026-09-19`) from the public node's retained history
(~18 months), 200,000 blocks clear of both ends. 9,000 blocks. Bootstrap over
windows (5,000 resamples), as in the Aptos campaigns. Absentees are recovered
as (validator set) − (addresses present); power weights are those at window
start (or at the last mid-window re-fetch), an approximation stated here.
All fetched windows are analysed; none is dropped after being seen.

## Locked predictions

| ID | Prediction | Supported if |
|---|---|---|
| CH0 | The commit record is not quorum-truncated | signed power ≥ 0.90 in ≥ 99% of blocks |
| CH1 | A8 holds closely in production | participation CI lower bound ≥ 0.98 by count **and** ≥ 0.99 by voting power |
| CH2 | Absence is validator-specific, not IID (replicates the Aptos finding on an uncensored record) | recurrence − (1−p): CI lower bound ≥ 0.15; NOT_TESTABLE if < 5 windows contain any absence |
| CH2b | Static per-validator rates explain that recurrence | second-half observed − first-half-rate prediction: CI ⊂ ±0.05 |
| CH3 | Low fault rate | ≤ 1% of blocks committed in a round > 0 |

Honest prior, recorded so it cannot be adjusted later: CH0 and CH3 likely hold;
CH1 is uncertain (the Aptos liveness prediction failed at 97.7–99.1% of stake);
CH2b is uncertain (validator downtime may be bursty rather than static).

## Hashes at lock time

    cosmos_fetch.py              949aa7e3e919f3dbd88c974f47f7f1d2c73c41776b8d9bcff75d745d1c5f88ab
    cosmos_analyze.py            92936ed9c8dab2e13fbe98b6e384601cc6e19e6501ec96dcca2e7e9882cfa5ee
    ../fetch_aptos_bitvecs.py    9a55969625450020645b4be20ee3caf464cc6b1c3526e0a35c347aa9d138b6cf   (bootstrap routine, reused)

## Amendment 1 — independent verifier hashed before the analysis ran (08:00:35Z)

`cosmos_independent_verify.py` shares no code with `cosmos_analyze.py` (exact
rational arithmetic) and was checked on the synthetic development windows only.
Recorded while the fetch was still in progress (5 of 30 windows on disk) and before
`cosmos_analyze.py` had been run on any of them.

    cosmos_independent_verify.py   8dfb4e9a2cafec5ef23e55e9593d0d03bd710901a5ed81a96f36d89274267f38

## Amendment 2 — fetch parallelised, locked fetcher unchanged (08:11:27Z)

The sequential fetch was network-bound (about 2% of one core, 2.4 min per
window). After 9 of 30 windows it was stopped and the remaining 21 were split
across four workers by `cosmos_fetch_sharded.py`, a wrapper that imports the
locked `cosmos_fetch.py` unmodified (hash above still verifies) and only
decides which of the already-recorded windows each worker takes. Same seeded
window list, same per-block logic, no analysis. Nothing had been analysed.

    cosmos_fetch_sharded.py        164edf87e34a70e833588395eb38d7e19da003bd155e578e1865767905081518

## Outcome (2026-09-19T08:25Z) — recorded after the locked pipeline ran

30/30 windows, 9,000 blocks (2025-05-08 to 2026-09-05), 0 inconsistent blocks,
2 mid-window validator-set re-fetches, no throttling. All hashes verified before
analysis; independent verifier agrees to 1.1e-16 on every statistic.
- CH0 SUPPORTED: signed power ≥ 0.90 in 8,999/9,000 blocks (min 0.753).
- CH1 SUPPORTED: participation 0.9933 [0.9890, 0.9966] by count, 0.9979
  [0.9960, 0.9992] by power. 45.6% of blocks carry all 180; 11/30 windows contain
  a validator that signs nothing.
- CH2 SUPPORTED: recurrence 0.592 vs 0.0067 under independence.
- **CH2b INCONCLUSIVE**: observed 0.536 vs 0.435 from first-half rates; residual
  +0.101 [0.019, 0.197] straddles ±0.05. Downtime is bursty, unlike Aptos QC
  membership where static rates explained 94%.
- CH3 SUPPORTED: 13/9,000 blocks (0.14%) committed in a round > 0.
