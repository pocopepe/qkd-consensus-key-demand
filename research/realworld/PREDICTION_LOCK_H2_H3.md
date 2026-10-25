# Prediction lock — H2 (participation-corrected π) / H3 (schedule expectation)

Written and hashed **before** any Aptos epoch data beyond the single sample
block/epoch used for Phase-0 feasibility checking (G0.1/G0.2) is pulled or
analyzed. Nothing below may be changed after observing the held-out results;
deviations are reported as errors, not revisions. Follows the same discipline
as `research/results/e2_full/PREDICTION_LOCK.md`.

## Locked model

Asymmetric star, chained-rotation, generic (L(t-1), L(t), L(t+1) distinct):
propose-star of L(t) complete (broadcast, participation-independent), vote-star
of L(t+1) partial (only actual round-t signers, from the measured
`previous_block_votes_bitvec`).

    pi_p(n, p) = [1 + p(n-2) + p(1+p)] / [(n-1)(1+p)]

reduces exactly to the frozen Theorem A value pi(n,2,1) at p=1 (verified to
machine precision, `research/realworld/pi_p_model.py`).

## Primary falsifier — H2/H3: is signer absence memoryless or sticky?

This is the primary, most powerful test, measured directly from consecutive
`previous_block_votes_bitvec` values, not through aggregate pi_p (which the
verification script showed has weak discriminating power at Aptos's actual
validator count, ~85-100).

**Prediction locked:** for validators absent at round t, the fraction also
absent at round t+1 will be measured on a held-out sample of epochs (epoch
range TBD at pull time, recorded in the results file, chosen to exclude the
single epoch 17314 already inspected during Phase 0).

- **IID model predicts:** that recurrence rate ≈ (1-p), i.e. absence at t+1 is
  independent of absence at t.
- **Sticky model predicts:** that recurrence rate is close to 1 (same
  validators keep missing).

**Falsification criteria (locked):**
1. If measured recurrence rate is within 0.05 of (1-p): **IID supported**,
   sticky refuted.
2. If measured recurrence rate exceeds (1-p) + 0.15: **sticky supported**
   (or a third, uncorrelated-but-non-iid mechanism -- reported as such, not
   forced into either bucket).
3. If it falls between those bands: **inconclusive**, reported as such.
4. Secondary corroborating check: aggregate measured pi (via the existing,
   frozen `research/e1_analyze.py` extraction logic, reused not rewritten)
   should sit closer to pi_p(n_actual, p_actual) [computed per-epoch from the
   measured mean participation] than to the full-participation pi(n,2,1),
   IF and only if measured p is materially below 1. Given the weak
   discriminating power shown above, a MISS on this secondary check alone
   does NOT overturn a clear result on falsifier #1-3.
5. A single anomalous epoch is to be investigated, not treated as failure of
   the whole hypothesis, matching E2's precedent.

## What would make this uninteresting (checked, not assumed)

If Aptos's measured participation p is close to 1 across the sampled epochs
(mirroring the Cosmos Hub G0.4 finding of near-zero absence), H2/H3 degenerate
to "the original theorem holds, participation correction not needed" --
itself a reportable finding (a third production system landing near-degenerate
participation, alongside CometBFT/libhotstuff from E1 and possibly Cosmos Hub
from G0.4), not a failure of the plan.

## Analysis code

SHA-256 of `research/realworld/pi_p_model.py` at lock time (unchanged, this
is the pi_p closed-form/simulation file, not the fetch script):

    00acf59c5f2cca280d23e0e7e346aa3fd0da775f2aae670045b51febdc79c88a

## Correction made before any held-out data was analyzed (2026-09-17/18)

The fetch/analysis script (`fetch_aptos_bitvecs.py`) was found to mislabel
which round `previous_block_votes_bitvec` describes: the field on the
block-metadata tx whose own `round` is r carries votes FOR round r-1, not
round r. This mattered for which proposer got excluded from the "absent"
tally each round. Fixed by re-keying by the round the votes actually
describe. Also added: an epoch-level bootstrap CI (resampling epochs, not
raw transitions, per the main plan's stats standard) instead of a bare
point-estimate-vs-band comparison; a randomized within-epoch start offset
(seeded, fixed before any data was read) to avoid confounding genuine
variation with epoch-boundary transition effects; forced unbuffered output
for real-time visibility.

**Why this does not invalidate the lock.** The only run made before this
correction produced zero usable epochs -- every one hit Aptos's anonymous-IP
rate limit (429, all 5 candidate epochs) before any analysis logic ran on
real data. No conclusion was ever drawn from the buggy version. This mirrors
the main project's own precedent: the E2 `min_vertex_cover` bug was found and
fixed before the real 50-run campaign, not after, and is disclosed rather
than hidden.

Updated SHA-256 of `fetch_aptos_bitvecs.py` (post-correction, pre-held-out-run):

    52b0a46bdad2aaee06c3c4a83395a4be78b492cfc49b6d6e4a2d58a05f1f9128

## Second update: infrastructure hardening for the production run (2026-09-18)

Raised epoch count 3->5 (matching what the bootstrap CI actually requires),
added inter-epoch spacing (300s, honest respect for the observed rate-limit
window instead of reactive-backoff-and-hope), raw per-round data persistence
to disk per epoch (auditability -- an independent script recomputes from
this, not from the same in-memory objects), incremental checkpointing after
every epoch, a hard overall deadline, and timestamped unbuffered logging.

**None of `analyze_epoch`, `epoch_bootstrap_ci`, `popcount_bits`, or
`analyze_proposer_rotation` -- the functions that determine the scientific
conclusion -- changed in this pass.** Only orchestration (fetching, spacing,
logging, persistence) changed. Recorded as a distinct hash regardless, so
the lock always names exactly the bytes that ran:

    3930b8328916cc0ca9c8d7c16dc2ae8fe7e86f0f8e1bd7c0ec8ae7e555c049e5

This is the hash of the script actually used for the production held-out
run reported in the final results.

## Third update: resume support after a session-teardown data loss (2026-09-18)

The first production run (launched via `nohup ... &; disown`, hash
`3930b832...`) survived only epoch 17265 (already persisted to
`raw/epoch_17265.json`, fully verified) before the shell session that owned
its process group was torn down mid-run, killing it partway through epoch
17276's rate-limit backoff. Rather than blindly relaunch a fresh 5-epoch run
that would re-fetch epoch 17265 for no reason, added resume support: `main()`
now scans `raw/epoch_*.json` at startup, recomputes each cached epoch's stats
through the SAME `analyze_epoch`/`analyze_proposer_rotation` functions (not
hand-copied numbers), excludes those epochs from re-selection, and only
fetches `EPOCH_COUNT - len(cached)` new ones.

**None of `analyze_epoch`, `epoch_bootstrap_ci`, `popcount_bits`, or
`analyze_proposer_rotation` changed in this pass** -- same guarantee as the
second update. Only orchestration changed (resume scanning, cache-aware
epoch selection, deadline scaling). Verified via a deliberately short,
killed-early smoke test (not a production run) before trusting it: correctly
detected epoch 17265 as cached, reported "need 4 more," and selected 4 new
non-overlapping candidate epochs (17266, 17280, 17294, 17308).

**Why this does not invalidate the lock.** The resume logic has not yet
processed any of the 4 still-needed epochs -- it was only exercised against
already-verified epoch 17265 (recomputing, not re-deciding, its stats) and a
smoke test that was killed before any new epoch was fetched. No held-out
epoch has been analyzed with this version of the code yet as of this
correction.

Updated SHA-256 of `fetch_aptos_bitvecs.py` (post-resume-support, this is
the hash of the script used for the relaunch that will complete the
production run):

    9a55969625450020645b4be20ee3caf464cc6b1c3526e0a35c347aa9d138b6cf

## What is NOT locked yet

- The exact held-out epoch range for the full pull (pick after this lock is
  committed, record the choice, don't cherry-pick after seeing results).
- H1 (does k<m dominate on Aptos) and H6 (predictor zoo on the real schedule)
  are separate hypotheses with their own locks, written when their analysis
  code is ready -- not bundled here to avoid one large lock file covering
  unrelated claims.

## Post-hoc note (2026-09-19): interpretation withdrawn, measurement stands

Stake-weighting the v1 bit-vectors showed signed stake in [2/3, 2/3+s_max] in
every round: the vector is quorum-truncated, so "p" above is QC inclusion, not
participation, and the STICKY verdict says nothing about A8. The locked label is
kept as the record of what the locked code returned. See `FINAL_REPORT.md` §1
and `PREDICTION_LOCK_V2.md`, which re-poses the question.
