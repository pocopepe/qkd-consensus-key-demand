# Prediction lock — H1 (production k<m regime exists)

Written and hashed before the H1 statistic is computed from any epoch beyond
the single Phase-0 sample block (epoch 17314, round 12449). Reuses the same
raw fetch as H2/H3 (`fetch_aptos_bitvecs.py`) -- `proposer` per round is
already part of every `block_metadata_transaction` pulled for that test, so
no separate network cost is needed; the statistic is computed from data
already collected under the H2/H3 pull, plus any later pulls of the same
shape.

## Locked prediction

For consecutive rounds r, r+1 within an epoch: `distinct_rate` = fraction
where `proposer(r) != proposer(r+1)`.

- If `distinct_rate >= 0.90`: **k<m dominant** (matches E2's locked m=2,k=1
  structure) -- H1 supported, the production regime is non-degenerate.
- If `distinct_rate <= 0.10`: **k=m dominant** (matches E1's degenerate
  finding on CometBFT/libhotstuff) -- H1 refuted, Aptos joins the degenerate
  column, itself a reportable finding (three production systems now landing
  near-degenerate, not two).
- Between 0.10 and 0.90: reported as a **mixed regime**, and the exact rate is
  the finding -- not forced into either bucket. If mixed, `pi` is not a
  constant `(2,1)` case; H3's schedule-expectation framing becomes load-bearing
  rather than optional, matching the schedule-expectation contingency already
  in the main plan.

## Why this is cheap to test honestly

`proposer` is a top-level field on every `block_metadata_transaction`,
identical wire cost to what H2/H3 already pulls. No additional locked-in
compute-unit budget is spent to test this hypothesis; it rides on the same
data.

## Falsification note

A single epoch showing an unusual rate is investigated, not treated as the
final answer -- report the per-epoch rate distribution across whatever epochs
the H2/H3 pull (or a later, larger pull) actually covers, and don't average
away visible epoch-to-epoch disagreement.

## Analysis code

Computed by `analyze_proposer_rotation()`, added to
`research/realworld/fetch_aptos_bitvecs.py` at the same time as this lock.
SHA-256 of the full script at lock time recorded in
`H1_LOCK_SCRIPT_SHA256.txt` in this directory (written by the same commit as
this file).
