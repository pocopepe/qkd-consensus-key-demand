# Real-world validation — final report (2026-09-19)

Supersedes the 2026-09-18 version of this file, whose headline claim is
**withdrawn** (see §1). Everything here was pre-specified: hypotheses, numeric
bands and SHA-256 of the code were written before the corresponding data
existed (hashes held by the author; Cycle-3 locks also pushed to the hosted repository first). Locks: `PREDICTION_LOCK_V2.md`, `PREDICTION_LOCK_H7.md`,
`e3/PREDICTION_LOCK_E3.md`, `e3/PREDICTION_LOCK_E3C.md` (v1: `PREDICTION_LOCK_H1.md`, `PREDICTION_LOCK_H2_H3.md`).
`audit_paper_numbers.py` ties all 140 numbers quoted in the paper to the result
files below.

## 1. What was withdrawn, and why

Campaign v1 (5 epochs) read Aptos's `previous_block_votes_bitvec` as validator
participation (p ≈ 0.60) and concluded that full participation (A8) fails badly
in production. Weighting the same bits by stake shows the signed stake lies in
[2/3, 2/3 + largest share] in **every** round — 640 rounds in v1, 60,000 in v2.
The bit-vector is quorum-truncated. "Absent" means "not among the first 2/3 of
stake to reach the aggregating leader", not "offline". The paper defines the
support on messages *sent*; a late vote is still a message. v1's measured
recurrence stands as a measurement; its interpretation does not. The error was
found by self-review, before anything reached the manuscript.

## 2. Campaign v2 — Aptos mainnet, 30 held-out epochs × 2000 rounds

**Correction (2026-09-22, F17):** Aptos broadcasts votes to all validators
(AIP-89), so Aptos's own proposal-and-vote support is at k=m. H1's reading as
"k<m in production" is withdrawn; the statistics below are properties of the leader
schedule, and the schedule-implied pi is that of chained rotation driven by the
Aptos leader sequence.

Files: `v2_fetch.py`, `v2_analyze.py`, `v2_independent_verify.py`, `raw_v2/`,
`V2_RESULTS.json`, `v2_positive_control.json`, `V2_POSTHOC.json` (exploratory).

| ID | Claim | Locked band | Measured | Verdict |
|---|---|---|---|---|
| H1 | production runs at k<m | CI lower ≥ 0.90 | 0.9818 [0.9806, 0.9829] | held |
| H1q | repeat-leader rate = Σsᵢ² | ratio CI ⊂ [0.8, 1.2] | 1.085 [1.015, 1.155] | held (CI excludes 1) |
| H3 | schedule π = stake closed form | diff CI ⊂ ±0.002 | +0.0010 [0.0002, 0.0018]; 0.5291 vs 0.5281 (generic 0.5120) | held |
| H8 | bit-vector quorum-truncated | ≥ 99% of rounds | 100% of 60,000 | held |
| H2R | QC membership not IID | CI lower − (1−p) ≥ 0.15 | 0.760 vs 0.403 | held |
| H2b | static heterogeneity explains it | residual CI ⊂ ±0.05 | +0.020 [0.015, 0.025] (94% of gap) | held (CI excludes 0) |
| H10 | low fault rate | ≤ 1% rounds | 0.027% (16 rounds) | held |
| H6 | no learner beats π on the real schedule | excess ≤ 0.02; 0 Theorem-B violations | closest −0.0013; 0 / 28,800 | held |
| **H9** | ≥ 98% stake seen live in ≥ 90% of epochs | | **80%** (min 97.67%, mean 98.84%) | **FAILED** |

H9's failure is informative: 3 validators (0.88% stake) appear in no QC and
propose nothing in all 30 epochs; a fourth (1.3–1.5%) is absent in six. A8 is
violated in production by a small persistent set.

Rigor: positive control at campaign size passes every band; independent
verifier (no shared code, hashed before the primary ran) matches all 11
per-epoch statistics to 1.1e-16; event-stream fetch path validated
bit-identical to the v1 transaction path (0/133). Exploratory, *not*
pre-specified: renormalising stake over active validators moves H1q to
1.064 [0.993, 1.134].

New theory, tested by H3: for i.i.d. stake-weighted leaders, q=Σsᵢ², r=Σsᵢ³,
E[π] = (2q−r) + (q−r)·n/(2(n−1)) + (1−3q+2r)·(n+1)/(2(n−1)).

## 3. H7 — frozen provisioning loop on real leader sequences

`h7_provisioning.py`, `H7_RESULTS.json`. Ten epochs, frozen `e4_operational.run`
unmodified. Carry-forward hit rate varies by exactly 0.0000 across the 256×
key-rate sweep; ceiling 0.5117 never exceeds the schedule-implied rate 0.5176
(gap ≤ 0.0135); schedule-aware predictor 1.0000. All three predictions held.
(The first-draft comparison target was wrong — caught on synthetic data and
fixed before any real epoch was run; recorded in the lock.)

## 4. E3 and E3c — emulated WAN latency and silent proposers

`e3/`: relab's 217-city one-way latency matrix, a different seeded geography per
run, same instrumented tree / parser / analyser as E2. Run **twice**, each under
its own lock (`PREDICTION_LOCK_E3.md`, `PREDICTION_LOCK_E3C.md`), because the
first run exposed an emulator defect.

**The defect (self-found).** In E3, 84% of missing votes (555/663) came from the
*previous leader*. The latency matrix rules out the geographic race first written
into the paper draft. relab sleeps for the emulated delay while holding gorums'
per-sender stream lock, so delays accumulate: a far leader's late vote for view
t−2 blocks its own proposal for view t to exactly the previous leader. Fix:
`e3/emulation_fix.diff` (4 lines, emulation layer only), separate binary
`hotstuff_e3c`. E3c repeats E3 on the **same geography seeds** (paired runs).

E3c (per-message delay) — primary result:

| n | transitions | π pred | π measured (mean ± sd) | residual | votes | timeouts | E3 residual | E3 votes |
|---|---|---|---|---|---|---|---|---|
| 8 | 3996 | 0.6429 | 0.6430 ± 0.0002 | +1.6e-4 | 0.9996 | 2.6% | −0.0070 | 0.9899 |
| 16 | 3820 | 0.5667 | 0.5668 ± 0.0002 | +1.1e-4 | 0.9997 | 3.9% | −0.0011 | 0.9980 |
| 32 | 3137 | 0.5323 | 0.5323 ± 0.0000 | +0.1e-4 | 0.9996 | 6.4% | −0.0014 | 0.9976 |
| 64 | 2895 | 0.5159 | 0.5158 ± 0.0000 | −0.3e-4 | 0.9997 | 9.5% | −0.0003 | 0.9997 |

E3c verdicts: **C1 FAILED narrowly** (vote participation ≥ 0.999 in 19/20 runs;
one at 0.99893; residual loss 137 votes in 13,848 transitions, not
role-concentrated). C2 held (cells ≤ 1.6e-4, worst run 5.0e-4, m=2 ≥ 99.89%,
ρ ≤ 0.0011). C3 held (f=1 0.5376 ± 0.0004 vs 0.5378; f=5 0.3721 ± 0.0008 vs
0.3697; max 0.0034). **f=5 still rests on 250 views** (480 s runs yield ~50
views; the view timer backs off).

E3 verdicts (serialised emulator; kept as a record of the protocol with A8
violated): P1, P2, F1, F5 held (max cell residual 0.0070, always below; worst
run −0.0243); **P3 (π_p) NOT TESTABLE** — 2 eligible runs in E3, 0 in E3c. π_p
is not validated and the paper says so.

Exploratory, not pre-specified (`e3/e3_posthoc_prevleader.py`): losing the
previous leader's vote costs a carried unit now *and* next view; any other lost
vote costs only the latter. Role-wise counting reproduces all 20 E3 runs to
0.0011 (π_p: 0.013; π(n,2,1): 0.024). A8 sensitivity is role-dependent.

Other problems found and disclosed:
1. Frozen "happy-path" partition fabricates adjacencies when timeouts are common;
   E3/E3c use adjacency-correct transitions (in the lock, before the campaign).
2. relab re-dispatches early proposals through the same handler, so E2's log line
   fires twice (E2: 1 of 2.5M; E3: 733 of 827,404; E3c: 81 of 890,023).
   De-duplication was post hoc in E3 (both result files kept) and pre-specified
   in E3c. No verdict depends on it.
3. Host load spikes from an unrelated process: 25.6 (E3, two n=16 runs), 54.6
   (E3c, two n=32 runs, residuals 0.0000). Runs retained.

## 4a. E3d — held-out test of role-dependent vote loss (new proposition)

`e3/PREDICTION_LOCK_E3D.md`, `e3/raw_d/`, `e3/E3D_RESULTS.json`. The post-hoc
accounting found on E3 became Proposition "Role-dependent vote loss" in the
paper: with mu_a missing votes per view from the previous leader and mu_o from
non-leaders, pi = (n+1 - 2 mu_a - mu_o) / (2(n-1) - mu_a - mu_o). E3 was
development data, so it was tested on 24 NEW geographies (n = 8, 16, 32) using
the serialised emulator deliberately as a reproducible source of vote loss.

| ID | Prediction | Band | Measured | Verdict |
|---|---|---|---|---|
| R1 | formula reproduces the measurement | within 0.002 in every run | max 0.0009 (24 runs, 15,498 transitions) | held |
| R2 | role matters, not only total loss | closest in >= 80% of lossy runs and mean residual <= half of pi_p's | 14 of 15; 0.0003 vs 0.0026 (pi_p) vs 0.0049 | held |
| R3 | loss concentrated on the previous leader | >= 60% of missing votes | 75% (729 of 971) | held |

Disclosed: I first wrote the lock claiming the formula was closest in "all 9"
lossy development runs; it was 8 of 9, and the original 90% win band would have
failed on the development data itself. Corrected as a dated amendment three
minutes after launch, with `raw_d/` empty and nothing analysed. The held-out
result (14/15 = 93%) would have passed the original band too.

**Correction to the proposition (2026-09-21, F16).** A review of the proof found
that a vote lost by the leader two views ahead, L(t+2), also costs two carried
units. `e3/role_loss_check.py` confirms it by brute force; the paper's
Proposition 1 now has double-cost roles {L(t-1), L(t+2)}. Re-split on the same
E3d transitions (`e3/e3d_posthoc_roles.py`, not pre-specified): 729 votes from
L(t-1), 4 from L(t+2), 0 from L(t), 238 from others; largest residual 0.0007,
closest in 15 of 15 lossy runs. No locked verdict changes.

Also post hoc (`v2_posthoc_spread.py`): the stake-weighted corollary predicts
an SD of 0.0021 for the mean of a 2000-round window; the 30 Aptos epochs show
0.0022. The scatter in the Aptos figure is explained, not just the mean.

## 4b. Cosmos Hub — production participation on an uncensored record

`cosmos/`: 30 seeded windows × 300 consecutive blocks = 9,000 blocks, May 2025 to
September 2026, n = 180. A CometBFT commit lists every validator slot with an
explicit absent flag, so unlike Aptos it is not cut off at two-thirds. Cosmos Hub
gossips votes (k=m, π=1), so this measures A8 only. Lock:
`cosmos/PREDICTION_LOCK_COSMOS.md`; independent verifier hashed before analysis,
agrees to 1.1e-16.

| ID | Claim | Measured | Verdict |
|---|---|---|---|
| CH0 | record not quorum-truncated | signed power ≥ 0.90 in 8,999/9,000 blocks (min 0.753) | held |
| CH1 | A8 holds closely | 0.9933 [0.9890, 0.9966] by count; 0.9979 [0.9960, 0.9992] by power | held |
| CH2 | absence is not IID | recurrence 0.592 vs 0.0067 | held |
| **CH2b** | static per-validator rates explain it | 0.536 observed vs 0.435 predicted; +0.101 [0.019, 0.197] | **inconclusive** |
| CH3 | low fault rate | 13/9,000 blocks (0.14%) in a round > 0 | held |

All 180 sign in 45.6% of blocks; 1.2 absent on average; worst window 0.9501; in
11/30 windows some validator signs nothing. Downtime here is bursty, unlike
Aptos certificate membership where static rates explained 94%.

## 4c. E2 recomputed from the frozen raw traces (read-only)

`reproduce_e2_from_raw.py`, output in `E2_REPRODUCTION.txt`. Every entry of the
paper's E2 table reproduces to six decimals. **New finding:** the locked E2
analysis drops timeout views and then pairs each view with the previous
*retained* one. Restricting to truly adjacent, timeout-free transitions
(142,863 of them) gives k = 1.0000 at every n and a largest residual of 7.7e-7.
The residuals printed in the paper (up to 4.2e-4 at n=32) and the k drift are
produced by that pairing, not by the system. Reported in the paper as a
reanalysis outside the lock; the locked figures are retained.

## 4d. Cycle 3 (2026-09-21/22) — three held-out campaigns and one amendment

Full table, generated from the result files: `cycle3/CYCLE3_RESULTS.md`. Locks pushed before their data existed.

- **E3T, targeted single-role vote suppression** (72 runs, n = 16, 32; 8,766 votes suppressed). T2 held: which validator
  loses a vote matters as Proposition 1 predicts. D = 0.00644 [0.00545, 0.00727] against 0.00635 predicted at n = 16,
  and 0.00321 [0.00294, 0.00348] against 0.00328 at n = 32, while the role-blind form predicts 6e-5 and 2e-5. T1, T3,
  T4 and T6 held. **T5 failed as locked** (0.00221 > 0.002): the pipeline omitted proposal de-duplication (F19). Post
  hoc on de-duplicated traces T5 gives 0.00107, and T2/T3 are unchanged. An independent script reproduces D to 2e-17.
- **C1, Proposition 1 under real correlated absence** (Cosmos Hub absence patterns from 200,000 held-out blocks).
  C1A held: R <= 0.021 in all six round-robin cells, against a band of 0.15. C1B (stake-weighted schedules, where
  leaders repeat) is descriptive, with R 0.036–0.215.
- **V3, held-out Aptos replication** (40 new epochs, 240,000 rounds). Every v2 verdict recurs, including H9's
  predicted failure. D1 and D2 hold, so stake-only Corollary 2 is measurably misspecified for Aptos. Amendment 1
  (AIP-1 reputation classes): AW1 held, and the excess repeat rate is explained (ratio 1.016 [0.988, 1.045]).
  **AW2 failed as locked**: persistence is not measurably improved (F20).
- **QKD feasibility** (`qkd/QKD_FEASIBILITY.md`): per-view one-time-pad tag demand against measured field key rates
  (Cambridge, Tokyo), at view rates measured on Aptos and Cosmos Hub; a design is infeasible only above the ring's
  cut-bound ceiling (F21).

## 4e. Standing key stock on the Aptos leader schedule (2026-10-10; a calculation, not a pre-specified test)

`stock/stock_levels.py` asks how deep a pool each validator pair must keep if pools are refilled a fixed number of
views after use (chained rotation, votes to the next leader). It was written against four epochs (commit 3ed25f1) and
run once on the other 66: 46.2 million tags, results in `stock/STOCK_RESULTS.json`, checked by
`audit_stock_numbers.py`.

| Relay time (views) | Round-robin | Aptos, 99% on time | Aptos, 99.9% on time |
|---|---|---|---|
| 1 | 3 | 3 | 3 |
| 2 | 4 | 4 | 5 |
| 5 | 4 | 4 | 6 |
| 10 | 4 | 6 | 8 |
| 20 | 4 | 8 | 10 |
| 50 | 4 | 12 | 16 |

Depths are uniform, in tags per pair. Depths chosen from each pair's stake-derived demand distribution meet the same
targets with up to 24% less stock. Leaders drawn independently by stake reproduce the measured on-time share to within
0.0034 in all 180 combinations of relay time and depth. Under round-robin, four tags per pair serve every message up to
a relay time of n - 1 views.

The carry-forward manager was then evaluated by the same code on the same 66 epochs (`stock_levels.py forecast`,
`stock/FORECAST_RESULTS.json`): it arms the pairs of the previous view with enough key for any demand and releases
what is unused after one view, holding 0.094 tags per pair. With no relay delay it serves 52.9% of tags on time (the
schedule's pi); with a delay of one view or more it serves 5.7% on Aptos and 2.4% under round-robin, flat in the delay,
because the pairs it keys are those of a view two leaders old. Figure `fig-stock` in the paper plots both policies on
one axis (share served late against standing key per pair).

A cold referee read objected that releasing unused key is a strawman. `stock_levels.py retain` evaluates the
demand-following manager that keeps what it ordered (pools start empty, every tag reordered after use, nothing
released; `stock/RETAIN_RESULTS.json`): 98.7% on time at delta = 1 holding 2.28 tags/pair, 97.8% at 5 with 3.80,
95.0% at 50 with 8.41. It behaves as a uniform stock of the same standing key and reaches neither the 99% nor the
99.9% target at any relay time in the table; the specification-sized depths do, with one to two more tags. The
paper now presents both baselines. The relay time is a parameter, not a measurement, and the calculation assumes link pools
that never run dry. This replaces the earlier argument that prediction is needed because reservations are scarce
(`../FALSIFIED_CLAIMS.md`, F22).

CORRECTION (2026-10-11, F23). The statement above that the keep-what-it-ordered manager "reaches neither the 99% nor
the 99.9% target" is an artefact of scoring single epochs from empty pools. `stock/retain_warm.py` shows the late share
falling from 4.5% in the first quarter of an epoch to 0.14% in the last (delta = 1), and at most 0.38% late over
end-to-end runs of 74,000 and 202,000 views, ending at 3.1-14.3 tags per pair, about the depths the specification gives
for 99.9%. Such a manager finds the depth by serving late; the specification gives it beforehand.

CORRECTION (2026-10-11, F24). `stock_levels.retain` and `stock/retain_warm.py` counted one tag, not two, on the pairs
of a validator that leads two consecutive views (1.8% of views), so their demand totals were 0.9% below those of the
stock runs they are compared with. Both are fixed and rerun. The keep-what-it-ordered manager within one epoch:
98.6% on time at delta = 1 holding 2.52 tags/pair, 97.7% at 5 with 3.94, 94.9% at 50 with 8.54. By quarter at
delta = 1 the late share is 4.9%, 0.41%, 0.23%, 0.16%; end to end it is late at most 0.38% and ends at 3.6-3.7,
6.2-6.6 and 13.6-14.7 tags per pair. The earlier figures in this section are superseded.

PER-VIEW SCORING (2026-10-11, post hoc; `stock_levels.py views` -> `stock/VIEW_RESULTS.json`). A view counts as on
time if validators holding more than two thirds of the stake received the proposal and returned their votes without
waiting for key. The per-view simulation reproduces every uniform-depth tag share of `STOCK_RESULTS.json` exactly
(checked in `audit_stock_numbers.py`). At the depths of the pool-depth table the share of views agrees with the share
of tags: 3 tags at delta = 1: 99.96% of views; 4 at 5: 99.3%; 12 and 16 at 50: 99.0% and 99.96%. Below those depths
views fare worse than tags, because the pools of a leader's star run short together: 4 tags at delta = 50 serve 59%
of tags and 21% of views. At delta = 100 views (3.7 s) 20 tags serve 99.4% of views and 24 serve 99.95%. The
keep-what-it-ordered manager: 98.0% of views within an epoch at delta = 1 (99.85% in the second half), 93.7% at 50
(99.5% in the second half).

BLOCK REFILL, RING RELAY TIMES, TIMEOUTS (2026-10-11, post hoc; `stock/stock_refill.py` -> `stock/REFILL_RESULTS.json`).
Periodic review: every pool topped up to its depth once per period of 10 / 30 / 60 / 90 s (268 / 804 / 1608 / 2412
views at 26.8 views/s, sixteen random phases per epoch, COMPLETE periods only; a first run that kept the truncated
periods at epoch ends gave depths 7-10% too low and was caught by a fact check before publication). Least uniform
depth for 99% of tags on time: 31 / 80 / 154 / 228 tags per pair; for 99.9%: 40 / 103 / 195 / 287. The mean demand
per period matches 4vT/n within 1% (12.6 / 37.9 / 75.8 / 113.7 against 12.8 / 38.3 / 76.6 / 114.8), so the 99% depth
is about twice the mean. Ring: validators in index order on a ring, pair delay =
hops x d_hop; at d_hop = 1 / 2 / 5 views (farthest pair 42 / 84 / 210 views) the least uniform depth for 99% is
9 / 13 / 25 and depths from each pair's own distance and stake (quantile rule of stock_levels) average 6.5 / 9.2 /
15.4 (99.9%: 12 / 18 / 33 against 8.8 / 12.0 / 19.2). Timeouts: a broadcast timeout round puts two tags on every
pair, so depth z absorbs floor(z/2) consecutive rounds. Self-checks: the per-pair fill with equal delays reproduces
stock_levels.fill; a one-rotation period under round-robin is served fully at depth 4.

RELAY TIME THROUGH THE ETSI 014 KME (2026-10-11; `kme/relay_latency.py` -> `kme/RELAY_LATENCY.json`). One 128-bit key
relayed over h hops, each hop = Get key at the sender and Get key with key IDs at the receiver over a pooled
mutual-TLS connection, loopback, 200 relays per setting. p99: 4.7 ms (1 hop), 164 ms (42 hops); with a 1 ms sleep
per hop 253 ms at 42 hops; with 5 ms, 371 ms (under 10 views). Per-hop base about 3.4 ms at p50. A lower bound on a
real network (no QKD devices, no WAN); used in Section VIII-D to place the rows of the pool-depth table.

## 5. What this does and does not establish

Does: Theorem 1's closed form matches every instrumented k<m run (chained HotStuff with unicast votes, emulated);
Proposition 1 predicts the effect of lost votes by role, both under targeted suppression (E3T) and, in simulation
under round-robin rotation, under replayed real absence patterns (C1); the Aptos leader schedule matches the stake-weighted corollary to about 6e-4, but
leaders repeat measurably more than stake alone predicts, consistent with AIP-1's reputation classes (which do not
measurably improve the persistence prediction); no history
learner finds structure in real schedules; key supply cannot move the carry-forward ceiling on real demand.

Does not: measure message-level pi or rho on any production chain (not observable; Aptos broadcasts votes and is
at k = m, F17); validate pi_p; use a real WAN (emulation on one host, with an emulator we had to patch); cover a
production k<m deployment. Aptos's all-to-all layers (Quorum Store, commit votes) are a k = m, pi = 1 workload.

## 6. Open items

- The bibliography (36 entries) passes `paper/tools/check_refs.py` with no FAIL and no WARN.
- The data-availability statement cites Zenodo record 10.5281/zenodo.22886385, which is still an unpublished draft.
- ORCID and the school or department are still to be added.
- `cycle3/UPSTREAM_ISSUE_DRAFT.md` is a draft of the emulator bug report; it has not been posted.
- `raw_v3_full/` (the full-epoch Aptos archive) is not committed; its SHA-256 list is.
- Cosmos Hub was previously treated only as a high-availability control after 5 sampled heights showed 180/180.
  The pre-specified campaigns replace that anecdote; windows were drawn by seed before any data was seen.

## 4f. The QKD key budget of seven production chains (2026-10-12; a calculation from specifications and live counts)
`research/realworld/chains/inputs.json` (patterns with their sources, validator counts and decision rates from the
chains' public interfaces on 2026-10-11/12, saved in `chains/*_live.json`) -> `chains/budget.py` -> `CHAIN_BUDGET.json`.
One 128-bit tag per message per recipient; a block counts as one message per recipient. Supply: the ring bound
8R/n^2 per pair. Results (tags per decision; key rate; link rate a ring needs; decisions per second that 2.22 Mbit/s and
1.8 kbit/s links sustain): Aptos (2n+1)(n-1) = 14,027 at 26.8/s: 48.1 Mbit/s, needs 12.2 Mbit/s, sustains 4.89 and
0.0040; Cosmos Hub 64,619 at 0.169/s: 1.4 Mbit/s, needs 352 kbit/s, sustains 1.07 and 0.00087; Polkadot GRANDPA
717,002 per round (no rate): 0.0966 and 0.000078; Sui Mysticeti n(n-1) = 16,002 per round (no rate): 4.3 and 0.0035;
Solana 2(n-1) = 1,342 at 4.54 slots/s: 779 kbit/s, needs 195 kbit/s, sustains 51.6 and 0.042; Avalanche Snowball
2nKbeta = 472,000 at 1.01/s: 60.8 Mbit/s, needs 15.2 Mbit/s, sustains 0.147 and 0.00012; Ethereum N + 32,768 =
879,145 per 384 s epoch (minimum, direct delivery): 293 kbit/s, but 3.58e11 pairwise pools (46 Tbit for one tag
each). Megabit links sustain Solana (11x margin) and Cosmos Hub (6x); kilobit links sustain none. Message patterns
were read by reader agents with machine-verified quotes (`~/code/paper-sources/deep/batch_{mysticeti,avalanche,grandpa,
ethereum,solana}.md`). Solana's slot time measured at 0.2205 s over 2001 consecutive blocks (2026-10-12), not the
nominal 400 ms. In the paper as Section VIII-E and Table 11; audited in `audit_cycle3_numbers.py`.
