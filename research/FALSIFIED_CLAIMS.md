# Falsified claims

Kept deliberately. Several of these corrections are stronger results than the
hypotheses they replaced, and the record of how they were caught is
methodological evidence in its own right.

---

## F1 — "EWMA is anti-correlated with real consensus demand"

**Original claim.** Theorem 1's anti-correlation result extends from an isolated
impulse train to real star-structured demand.

**Falsified by.** `verify_theory.py` T2, first run. Measured correlation over
the full pair matrix is **positive** for α ≳ 0.5 (+0.39 at n=16, α=0.9).

**Why.** Real demand is not an isolated impulse train — a pair is hot on four
phases of the cycle — and correlation over all pairs is dominated by the many
pairs correctly predicted to be zero, which flatters any smoother.

**Corrected.** Theorem 1 holds for the impulse case only. The operative
statement for real demand is the **persistence ceiling** (T7), measured at the
budget rather than by correlation. The corrected version explains the measured
EWMA coverage of 0.520 against a predicted ceiling of 0.567.

---

## F2 — "Faster smoothing overshoots more on bursts"

**Original claim.** Increasing α trades settling time against overshoot.

**Falsified by.** `verify_theory.py` T3. Under- and over-provision areas are
**equal** for an unbiased filter, and total tracking error falls
**monotonically** in α (37.81 → 15.54 from α=0.1 to 0.9).

**Corrected.** There is no overshoot trade. The real tension is between
workloads: burst error falls monotonically in α while rotation covariance also
falls monotonically in α, so **the burst-optimal α is the rotation-worst α**.
That is a sharper statement than the original.

---

## F3 — Conjecture B: "for every RWC predictor, cov ≤ π"

**Original claim.** `cov ≤ π` universally, with equality for EWMA at `α ≥ ½`.

**Falsified by.** `e5_theorem_b.py` B3. Explicit counterexample under
last-observation weighting: `S(t−2)={a,b,c}`, `S(t−1)={a}`, `S(t)={a,b,c}` gives
`π = 1/3` and `cov = 1`.

**Two errors.** (i) In the constant-support case the relation is an
**equality**, not an inequality. (ii) When the support **grows**, the inequality
**reverses**.

**Corrected.** Theorem B's three-case statement under lag-1 dominance (T7). The
`α ≥ ½` threshold is a corollary of the weight condition, not a premise. Every
protocol modelled here has constant support size, which is why the equality was
observed everywhere and the failure mode never appeared.

---

## F4 — "Required key-generation rate scales with 1−π"

**Original claim.** (E4 pre-registered hypothesis.) Over-provisioning
requirement tracks `1−π`.

**Falsified by.** E4 Q2. Ratio of required rates is **non-monotone** (1.017,
1.696, 1.282, 1.007), `corr = +0.36` over four usable points; two operating
points were unreachable at any rate.

**Corrected.** The cost of `1−π` is paid in **wasted key**, not required rate
(`corr = +0.983`, slope 0.975) — and even that holds only at TTL = 1.

---

## F5 — "hit rate ≤ π" as an unqualified operational statement

**Original claim.** E4's headline.

**Falsified by.** E4-TTL. With TTL = 8 total hit rate exceeds `π` by up to
**+0.7301**.

**Corrected.** `π` bounds **fresh** hits — those served by a reservation created
in the current view. Total hits are additionally bounded by whatever map
capacity the lease induces; live reservations reach **3.77×** the per-view
budget. This is budget inflation, not improved prediction, and the fresh-hit
component stays pinned at `π`.

---

## F6 — "A hoarding penalty fixes the starvation regression"

**Original claim.** Charging γ per bit-hop held would reduce starvation.

**Falsified by.** E1 sweep. Identical starvation to three decimals at γ = 0 and
γ = 1.

**Corrected.** Holding key is a **duration** problem, not a selection problem;
halving the lease restored the reactive starvation rate exactly.

---

## F7 — "Burstiness explains the E1/E6 TTL discrepancy"

**Original claim.** Long leases are harmful under flash crowds, which is why E1
and E6 disagreed.

**Falsified by.** E7, using E1's own burst generator unchanged. `ΔS` is negative
in **every** arm; `TTL*` differs in 2 of 14 comparisons, both among ties at zero
starvation. A mean-load control further showed most of the bursty penalty is the
1.43× higher mean load, and that variance alone slightly *helps* fresh hit.

**Corrected.** Burstiness is not the mechanism. E8 attributes the discrepancy to
reservation accounting.

---

## F8 — "Amplification harms TTL by increasing occupied resource"

**Original claim.** (E8 pre-registered mechanism.) Larger reservation footprint
crowds the pool.

**Falsified by.** E8 §7. Achieved footprint **falls** with amplification
(0.74 → 0.59 D) and live reservations fall 9× (27 → 3), because capacity caps
them.

**Corrected.** Amplification **prices reservations out of the pool** — arming
failures rise 9.14 → 32.58 per view — and the sign flip additionally requires
**link specificity**, evidenced by successful reservations averaging 1.504 hops
against a structural mean of 2.300.

---

## F9 — "Predictive pre-arming leaks the leader schedule"

**Original claim.** Pre-arming defeats proposer privacy; leakage measured at
top-1 0.534 against a 0.062 baseline.

**Falsified by.** `marginal_leak.py`. The baseline was **chance**, not an
observer who simply watches consensus traffic. Against the correct baseline the
marginal contribution of pre-arming at H = 1 is **+0.0000**, and at larger
horizons it goes **negative** (−0.1875) because a wider pre-arm set is blurrier
than traffic.

**Corrected.** No leakage claim is defensible for chained protocols. A narrower
SSLE-conditional result (+0.88 marginal under subnet gossip) exists but rests on
four experiments that were never run. **Omitted from the paper entirely.**

---

## F10 — "The eBPF instruction budget constrains the pre-arm set"

**Original claim.** (The original project proposal.) `Σ_v c_v ≤ I_max` is a
knapsack dimension.

**Falsified by.** E1 T1. 244 verified instructions, unchanged across a 16,384×
range of map capacity.

**Corrected.** The verifier bounds the program, statically. What binds is map
**update bandwidth**, which is paid per changed entry.

---

## F11 — "Full participation fails badly on a production chain (p ≈ 0.60)"

**Original claim.** (Real-world campaign v1, five Aptos epochs.) The on-chain
vote bit-vector shows ~60% participation and sticky absence, so A8 fails in
production and the full-participation π over-predicts.

**Falsified by.** Weighting the same bits by stake: signed stake lies in
[2/3, 2/3 + largest share] in every round (640 in v1, 60,000 in v2). The vector
is **quorum-truncated**. "Absent" means "not among the first two-thirds of
stake to arrive", not "did not vote".

**Corrected.** The bit-vector is a censored lower bound on the vote star and
cannot test A8. Campaign v2 re-posed every question against what the chain
actually exposes. Withdrawn before it reached the manuscript.
`realworld/PREDICTION_LOCK_V2.md`, `realworld/FINAL_REPORT.md` §1.

---

## F12 — "≥ 98% of stake is visibly live in ≥ 90% of epochs" (pre-registered H9)

**Falsified by.** Campaign v2: 80% of epochs (24/30); minimum 97.67%. Three
validators (0.88% of stake) appear in no certificate and propose nothing in any
of 30 epochs; a fourth (1.3–1.5%) is absent in six.

**Corrected.** A8 *is* violated in production, by a small persistent set — a
far weaker statement than F11 and the opposite of the "production is fully
live" prior behind H9. Reported in the paper as a failed prediction.

---

## F13 — "Under WAN latency votes are lost geographically: a nearby next leader out-races a distant proposal"

**Original claim.** (Written into the manuscript draft after campaign E3.)

**Falsified by.** Two things in our own data. 84% of E3's missing votes (555 of
663) came from one role, the previous leader, which geography does not predict;
and the framework's latency matrix excludes the race (distant proposal due at
136 ms, next proposal not before 152 ms, yet logged in the opposite order).
Cause: relab sleeps for the emulated delay while holding gorums' per-sender
stream lock, so delays accumulate; a far leader's late vote blocks its own next
proposal to exactly the previous leader.

**Corrected.** Four-line emulation fix (`realworld/e3/emulation_fix.diff`),
campaign repeated on the same geographies under a new lock (E3c): cell
residuals ≤ 1.6e-4. The salvage is a sharper result than the original: with A8
violated, the shortfall depends on *whose* vote is lost — the previous leader's
costs double — and role-wise counting reproduces all 20 E3 runs to 0.0011 where
the uniform correction π_p misses by 0.013.

---

## F14 — "With the emulator fixed, vote participation ≥ 0.999 in every WAN run" (pre-registered C1)

**Falsified by.** E3c: 19 of 20 runs; `wan_n16_g1` reached 0.99893. Residual
loss 137 votes in 13,848 transitions, not role-concentrated (4 from the
previous leader); 113 are replicas that logged no proposal for that view.

**Corrected.** The defect explains nearly all of E3's vote loss, not all of it
to the tolerance set. Reported as a failed prediction.

---

## F15 — "E2's residuals and the drift in k reflect the system under timeouts"

**Original claim.** (Manuscript, E2 threats.) The fall of k from 1.0000 to 0.9991
at n=32, and residuals up to 4.2e-4, were attributed to view changes breaking
hub carry-over, "reasoned from coincidence rather than established".

**Falsified by.** `realworld/reproduce_e2_from_raw.py`, read-only on the frozen
raw traces. The locked analysis discards timeout views and then pairs each view
with the previous *retained* view, so the view after a discarded one is compared
with a predecessor two views back. Restricted to truly adjacent, timeout-free
transitions (142,863), k = 1.0000 at every n and the largest residual is 7.7e-7.

**Corrected.** The residuals are an artefact of the pairing, not of the system.
The locked table is retained as the pre-registered result and the reanalysis is
reported beside it. On loopback the measured value equals the
specification-derived one, which is why the wide-area and production campaigns
carry the evidential weight.

---

## F16 — "Only the previous leader's lost vote costs double" (Proposition, two-role form)

**Original claim.** The role-dependent vote-loss proposition charged two carried
units for a vote lost by the previous leader L(t-1) and one for every other
validator, and the E3d lock (R1/R2) evaluated that two-role expression.

**Falsified by.** An independent review of the proof, confirmed by
`realworld/e3/role_loss_check.py` (brute force, n=16, one role at a time): a
vote lost by the leader two views ahead, L(t+2), also costs two units, because
in view t+1 the pair {L(t+1), L(t+2)} carries both the proposal and the vote of
L(t+1), and neither is carried once the pair is missing from view t. With 5% loss
on that role only, the two-role form misses by 1.6e-3; the corrected form agrees
to within simulation error for every role.

**Corrected.** The proposition now has double-cost roles {L(t-1), L(t+2)}.
On the held-out E3d data only 4 of 971 missing votes came from L(t+2), so no
verdict changes: `e3d_posthoc_roles.py` gives a largest residual of 0.0007
(0.0009 as locked) and the corrected form is closest in 15 of 15 lossy runs
(14 of 15 as locked). The locked figures stay in the paper as the pre-registered
result, with the corrected ones in a footnote.

---

## F17 — "Aptos mainnet operates at k<m in production" (H1 interpretation)

**Original claim.** Aptos sends votes to the next leader, so its proposal-and-vote
path is chained rotation (m=2, k=1), and a 98% distinct-leader rate shows the
k<m regime in production. The paper's abstract, Section VI and conclusion said so.

**Falsified by.** Reading the specification, which is the paper's own method.
Aptos Improvement Proposal AIP-89 (Accepted) describes the current protocol as
"All the other validators receive the block r and broadcasts a vote on r", after
which "All the validators create a quorum certificate". With broadcast votes the
per-view support is the complete graph: m=n-1, k=m, pi=1. The earlier claim came
from the 2022 whitepaper and from Jolteon's original design, not from the
deployed protocol.

**Corrected.** Aptos is at k=m, like Cosmos Hub and both instrumented open-source
implementations; only chained HotStuff with per-view rotation and unicast votes
(relab/hotstuff) is observed at k<m. The Aptos leader schedule remains a valid
production test of the stake-weighted corollary (chained rotation driven by the
real leader sequence), and every locked Aptos statistic is unchanged. The
whitepaper citation was replaced by AIP-1 (proposer selection) and AIP-89.

---

## F18 — "With per-message delay, residuals up to 1.6e-4 (worst run 5.0e-4) and a residual vote loss of 137 votes reflect the system"

**Original claim.** The wide-area campaign (E3c) reported cell residuals +1.6e-4, +1.1e-4, +1.1e-5 and -2.9e-5 at
n = 8, 16, 32 and 64, a worst run of 5.0e-4, and a failed prediction ("vote participation >= 0.999 in every run";
minimum 0.9989) attributed to 137 lost votes, "in 113 cases the replica logged no proposal for that view".

**Falsified by.** Found while arming Cycle 3 (`realworld/e3/reanalysis_final_view.py`, post hoc). The locked analysis
counted each run's final view, which the run's duration limit truncates: in one run that view held a single message
(pi = 1), and it held few of its votes. Dropping only the final view:
- cell residuals become 1.1e-16, 0.0, 2.6e-6 and -2.9e-5; the worst run is 7.9e-5;
- the only run below 0.999 participation (0.99893) becomes 1.00000; the minimum over 20 runs is 0.99937;
- 65 of the 137 missing votes lie in truncated final views; the genuine residual loss is 72 votes in 13,837
  transitions (13,848 with the final views).
The vote-loss campaign (E3d) is affected the same way: 15 runs counted as lossy become 12, and Proposition 1 remains
the closest expression in all of them (mean residual 3.4e-4 against 3.3e-3 for the role-blind form).

**Corrected.** The locked verdicts stay on the record as locked (C1 failed as locked). The paper reports the
reanalysis beside them, labelled post hoc: under per-message delay, the prediction holds to within 3e-5 in every
cell, and participation is at least 0.9994 in every run. Cycle-3 analyses exclude the final view by design.

---

## F19 — "With no suppression, the targeted-loss campaign (E3T) reproduces Corollary 1 to within 0.002 in every run"

**Original claim.** Locked prediction T5 of `realworld/e3/PREDICTION_LOCK_E3T.md`: the 12 runs without suppression match
the no-loss value (n+1)/(2(n-1)) to within 0.002.

**Falsified by.** The locked E3T run: maximum deviation 0.00221 (`realworld/e3/E3T_RESULTS.json`). Root cause, found
after the run: the E3T pipeline omitted the de-duplication step (`e3c_dedup.py`) that E3c and E3d apply, so a view whose
proposal the emulator re-dispatches and logs twice counts one message twice. In t_n16_g5_none, validator 3's vote to
leader 1 is missing every 16th view, and the next view carries a duplicate proposal record.

**Corrected.** T5 stays REFUTED as locked. Post hoc, the same locked analyser on de-duplicated traces (285 of
2,413,156 records removed; `E3T_RESULTS_DEDUP_POSTHOC.json`) gives T5 max 0.00107, T1 max 0.00057, and unchanged
T2/T3 verdicts. The headline role effect (T2) does not depend on de-duplication. The paper reports both.

---

## F20 — "Weighting stake by AIP-1's reputation classes brings Corollary 2 closer to Aptos's schedule-driven persistence"

**Original claim.** AW2 in Amendment 1 of `realworld/PREDICTION_LOCK_V3.md` (per-epoch |diff_stake| - |diff_activity|,
95% CI lower bound > 0), flagged in the lock as likely to fail on the development data.

**Falsified by.** `realworld/COR2_ACTIVITY_V3.json` (40 held-out epochs): +0.00012 [-0.00001, +0.00026].

**Corrected.** The paper claims only what held: the reputation classes explain the excess repeat-leader rate (AW1
held; the activity-weighted ratio's CI contains 1), but they do not measurably improve the persistence prediction,
whose stake-only misfit on the same rounds is itself not significant.

---

## F21 — "On 45 km links vote broadcast fails from n = 16" (QKD feasibility read a guaranteed rate as a ceiling)

**Original claim.** `realworld/qkd/QKD_FEASIBILITY.md` and the paper's QKD feasibility subsection (commit 2a17666)
treated v_max = 2R/(128 D), derived from the trusted-relay ring's guaranteed per-pair share B >= 4R/[N(N-1)], as the
highest sustainable view rate, and so reported broadcast as failing wherever v_max fell below Aptos's 26.8 views/s.

**Falsified by.** Self-review after an independent review of the paper flagged the formula's assumptions. A guaranteed
share gives a rate the ring can always sustain, not a ceiling. The ceiling is a cut through the ring's midpoint:
(n/2)^2 pairs share two links, so an even share is at most 8R/n^2 and no routing exceeds v_cap = v_max * 2(n-1)/n.
With it, broadcast at n = 16 on the 304 kbps link (v_max 18.6, v_cap 34.9) is undetermined, not infeasible.

**Corrected.** `feasibility.py` reports both v_max and v_cap, with an enumeration check of the cut bound. The paper
calls a design infeasible only above v_cap. The central conclusion stands: on Cambridge-grade links votes sent to the
next leader are guaranteed up to n = 100, while broadcast is guaranteed at n = 32 and infeasible at n = 64 (v_cap 16.7).

## F22 — "Stock is not the scarce resource; arming every pair holds 21 times as many reservations as a view uses" (why a key manager must predict)

**Original claim.** The paper's system model (commit 62c5ede) answered the objection that key can simply be stored on
every pair by saying that armed reservations, not stock, are scarce: one view of chained rotation uses 165 of the 3486
pairs at n = 84, so keeping every pair armed holds 21 times as many reservations as a view uses. Prediction was
presented as necessary on that ground.

**Falsified by.** Self-review: the reservation budget is a parameter of our own simulator, and no measurement showed
that a standing pool on every pair is expensive. `realworld/stock/stock_levels.py` then measured it on the Aptos leader
sequences (written against four epochs, run on the other 66; 46.2 million tags). With pools refilled as they are used,
3 tags per pair serve 99.95% of tags on time when replenishment takes one view, 4 serve 99% at five views, 12 at fifty,
and 16 serve 99.9% at fifty; 16 tags per pair are 7.1 Mbit at n = 84, 12.5 s of the cluster's consumption. Under
round-robin rotation four tags per pair serve everything up to a lead of n - 1 views. Two intermediate readings were
also wrong: a first calculation with a fixed-rate refill suggested that 99% needs 16 tags and 25% extra supply and that
stake-aware allocation gains a great deal; under replace-what-was-used no extra supply is needed and depths chosen by
stake save at most 24% of the stock.

**Addendum (later the same day).** The same script evaluated the carry-forward manager under the same relay
delays (`stock_levels.py forecast`): it serves pi (52.9%) only when key ordered after a view is in place for the
next one, and 5.7% with a delay of one view or more. So the earlier paragraph was wrong twice over: standing stock
is cheap, and the manager it defended does not work at all in the setting (relay delay) where pre-positioning is
needed.

**Second addendum (2026-10-11).** A referee read called the released-key carry-forward a strawman. The variant
that keeps what it ordered was then measured by the same code (`stock_levels.py retain`): 95–98.7% on time, holding
2.3–8.4 tags/pair, i.e. a stock policy whose depth is set by use; it reaches 99% at no relay time, where the
specification-sized depths do. Both baselines are in the paper.

**Corrected.** The paragraph is replaced. The paper now says that a pool on every pair works, gives its depth as a
function of the relay time from the specification (Section VIII-C, `audit_stock_numbers.py`), and presents `pi` as what
a key manager following recent demand without such a stock achieves. Theorem 1 and the validation are unaffected.

## F23 — "A manager that follows demand and keeps what it ordered reaches neither target; use alone cannot set the depth"

**Original claim.** Section VIII-C (commits a64ce65 to 20161aa) said of the demand-following manager that keeps the key
it ordered: it serves 98.7%, 97.8% and 95.0% of tags on time at relay times of 1, 5 and 50 views, "reaches neither
target at any relay time in the table", and "use alone cannot reach a target". The second addendum of F22 repeated it.

**Falsified by.** A referee read (2026-10-11, `~/code/paper-sources/deep/REFEREE_REPORT_2026-10-11.md`, M3b) pointed
out that the shortfall matches a cold start: the manager begins with empty pools, every late tag adds one tag to a pool
for good, and one held-out epoch holds only about 200 tags of demand per pair. `realworld/stock/retain_warm.py` (post
hoc; same policy; reproduces `RETAIN_RESULTS.json` exactly) confirms it. By quarter of an epoch the late share at a
relay time of one view is 4.5%, 0.28%, 0.19%, 0.14%. With the epochs of one validator set run end to end (74,000 views
at n = 84; 202,000 at n = 85) the manager serves 0.04% to 0.38% of all tags late, under 0.05% in the last tenth, and
ends holding 3.1-3.3, 5.8-6.2 and 13.3-14.3 tags per pair at relay times of 1, 5 and 50 views: about the depths the
specification gives for 99.9% (3, 6, 16 uniform; 3.0, 5.4, 13.4 by stake).

**Corrected.** The paper now says that such a manager finds its depth by serving late, that its shortfall within one
epoch is the start, and that over a long run it settles near the depth the specification gives before the first
view. H2 and the conclusion say "a stock policy that finds its depth by serving late". What the specification still
adds: the depth in advance, for a stated target, without the late tags. `audit_stock_numbers.py` checks the new
numbers against `stock/RETAIN_WARM.json`. The released-key carry-forward result (5.7% under any relay delay) and the
pool-depth table are unaffected.

## F24 — The keep-what-it-ordered baseline undercounted demand when a leader repeats

**Original claim.** `stock_levels.retain` (and `stock/retain_warm.py`, which copied its demand rule) were said to
evaluate the keep-what-it-ordered manager "by the same code" and on the same demand as the pool-depth runs.

**Falsified by.** Writing a per-view simulation (`stock_levels.py views`, 2026-10-11) that must reproduce the tag
counts of `STOCK_RESULTS.json` exactly. It does (46,208,966 tags), while `RETAIN_RESULTS.json` held 45,802,732: the
retain loop iterated over the SET of the two leaders of a view, so a validator leading two consecutive views (1.8% of
views) put one tag instead of two on each of its pairs.

**Corrected.** Both scripts now iterate over the pair of leaders. Rerun: within one epoch the manager serves 98.6%,
97.7% and 94.9% of tags on time at relay times of 1, 5 and 50 views (was 98.7, 97.8, 95.0), holding 2.52, 3.94 and
8.54 tags per pair (was 2.28, 3.80, 8.41); late share by quarter at one view 4.9%, 0.41%, 0.23%, 0.16% (was 4.5,
0.28, 0.19, 0.14); end to end at most 0.38% late (unchanged), ending at 3.6-3.7, 6.2-6.6 and 13.6-14.7 tags per pair
(was 3.1-3.3, 5.8-6.2, 13.3-14.3). The independent per-view simulation gives the same within-epoch shares. The
paper, the stock figure and `audit_stock_numbers.py` carry the corrected values. The conclusion of F23 is unchanged.
