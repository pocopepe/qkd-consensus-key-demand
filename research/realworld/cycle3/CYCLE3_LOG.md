# Cycle 3 — log (UTC)

## Final summary (2026-09-22)

**Everything ran to completion.**
- E3T: 72 of 72 runs, none invalid.
- Cosmos: 200,000 held-out blocks.
- Aptos: 40 of 40 held-out epochs (240,000 rounds).
- Full-epoch archive: 7.69 M rounds. It is not committed; its SHA-256 list is in RAW_V3_FULL_SHA256.txt.

Every lock hash verified before analysis. Full table: CYCLE3_RESULTS.md.

**What held**
- **E3T T2, the key test.** Which validator loses a vote matters, by the amount Proposition 1 predicts:
  - n = 16: D = 0.00644 [0.00545, 0.00727] against 0.00635 predicted.
  - n = 32: D = 0.00321 [0.00294, 0.00348] against 0.00328.
  - The role-blind form predicts 6e-5 and 2e-5.
  - T1, T3, T4 and T6 also held. An independent script reproduces D to 2e-17.
- **C1A.** Proposition 1 predicts the effect of replayed real Cosmos absences under round-robin rotation (largest R
  0.021, against a bound of 0.15). This is a simulation.
- **V3.** Every Aptos verdict replicated on 40 new epochs, including H9's failure, which was predicted to recur.
- **D1 and D2.** Stake-only Corollary 2 is measurably misspecified.
- **AW1.** The reputation classes remove the excess repeat rate.

**What failed, reported as failed**
- **E3T T5**, the no-suppression baseline (0.0022 against a tolerance of 0.002). The pipeline omitted
  de-duplication (F19); post hoc the deviation is 0.0011.
- **AW2.** Activity weighting does not measurably improve the persistence prediction (F20).

**Errors found and corrected while writing up**
- F18's transition count.
- The paper's printed first-order gap formula (the quoted numbers were right).
- The QKD feasibility read a guaranteed rate as a ceiling (F21). Broadcast at n = 16 on 304 kbps links is
  undetermined, not failed. The Cambridge-grade conclusion is unchanged.

**What changed in the paper**
- New subsections: targeted suppression, replayed absence, the second Aptos sample with the misspecification and
  activity weighting, the uncarried-demand corollary, and QKD feasibility (with its cut-bound ceiling).
- Proposition 1 is restated as a ratio of expectations, with its first-order gap.
- The lock table now covers 34 predictions (29 held, 4 failed, 1 inconclusive), with the data that existed at each
  lock and a second-sample column.
- The wording is "pre-specified" throughout. The abstract (199 words) and conclusion are rewritten.
- One independent review was run. Its 5 MUST items and most SHOULD items are fixed.
- 13 pages, clean build. Every audit passes, and check_refs reports 36 PASS.
- Commits: 0bf736b, 916e7fb, fd08c55, 2a17666, 3c8d362, aa046e8. All pushed.

**Open items**
- Zenodo record 22886385 (DOI 10.5281/zenodo.22886385) holds the files and is still a draft; the acknowledgment
  already cites it, so it should be published before submission.
- The school or department is not yet in the affiliation; ORCID not yet added.
- Co-authorship of the supervising faculty member is undecided; if added, the author block, the acknowledgment and
  the Zenodo record all change.
- The biography and photo for the final version.
- Posting UPSTREAM_ISSUE_DRAFT.md.
- Not done from the review's optional items: report E3T's base view-exclusion rate in the text (it is in Table VI).

## Chronological log

- 2026-09-21T20:40:41Z: locks committed and pushed (02c5f6f) before any held-out data; campaigns launched with `run_cycle3.sh all`.
- 2026-09-21T20:43:57Z: volume corollary U = (m-k)(n-1-m) verified by exact enumeration for all realizable (n,m,k), n<=20 (theory/volume_corollary.py; separate file so the locked chain_model.py is untouched).
- 2026-09-21T20:47:38Z: activity-weighted Corollary 2 calibrated on raw_v2 only (THR=0.10; repeat-ratio gain +0.0215 [0.018,0.025]); predictions AW1-AW3 appended to PREDICTION_LOCK_V3.md and pushed (fd4edf1) before the code read raw_v3.
- 2026-09-21T20:52:04Z: QKD feasibility done (qkd/): at Aptos's measured 27.5 views/s and 128-bit tags, Cambridge-grade links (~2.4 Mbps) sustain unicast votes to n=100 but broadcast only to n=32 (fails at n=64); 45-km links (304 kbps) fail broadcast from n=16. Sources verified from full texts: Dynes 2019 npj QI (2.22-2.58 Mbps, 5-10.6 km, 580 days; Eq. 1 per-link bound), Sasaki 2011 Opt. Express (45 km: 304 and 81.7 kbps). Committed 426b6d0.
- 2026-09-21T20:52:20Z: drafted the relab/hotstuff emulator issue (cycle3/UPSTREAM_ISSUE_DRAFT.md); not yet posted.
- 2026-09-21T21:04:39Z: Aptos held-out fetch complete: 40/40 epochs, 240,000 rounds, integrity checks pass (6000 consecutive rounds each, correct epochs, start heights as locked). Full-epoch archive started (not analysed by the locks).
- 2026-09-21T21:14:27Z: full-epoch archive running at ~290 events/s (4 epochs in parallel, oldest first); ETA ~7.5 h for ~7.8M rounds (~640 MB gz). Left running: not used by any locked analysis, resume-safe, well ahead of pruning.
- 2026-09-21T21:47:37Z: F18 recorded and pushed (beb7964): the E3c residuals (1.6e-4 cell, 5.0e-4 worst run) and the failed participation prediction (min 0.9989) were caused by the truncated final view; without it residuals are <= 3e-5 and min participation 0.99937 (65 of 137 missing votes were in final views). Locked verdicts stay as recorded; paper will report the reanalysis beside them.
- 2026-09-21T22:03:21Z: paper revision in progress (uncommitted): volume corollary subsection; Prop 1 restated as ratio of expectations + first-order gap + repeated-leader exclusion; pre-specification wording; Section V designer bridge; QKD feasibility subsection + table; wide-area post hoc column and explained failure; vote-loss post hoc note; Section VII condensed; intro reframed; limitation for feasibility model. New refs dynes2019cambridge, sasaki2011tokyo pass check_refs (checker gained OpenAlex search fallback and abbreviated-page parsing; self-test 18/18).
- 2026-09-21T22:12:07Z: Cosmos held-out fetch complete: 100/100 chunks, exactly the 200,000 planned heights (27,846,637-28,046,636), 0 inconsistent records, n=180 throughout. QKD_FEASIBILITY.json regenerated with the full data.
- 2026-09-21T22:15:08Z: audit_cycle3_numbers.py added (25/25; mutation-tested: 4/4 caught); committed 0c69c34.
- 2026-09-21T23:17:34Z: E3T finished 72/72. Locked verdicts: T2 (role matters) SUPPORTED at n=16 and n=32; T1, T3, T4, T6 SUPPORTED; T5 (baseline) REFUTED as locked (t_n16_g5_none off Cor 1 by 0.0022: validator 3 misses its vote every 16th view and the following view carries a double-logged proposal; the E3T pipeline omitted the de-duplication step used in E3c/E3d). Post hoc: re-ran the locked analysis on de-duplicated traces (E3T_RESULTS_DEDUP_POSTHOC.json).

- 2026-09-21T23:27Z V3 replication read: every v2 verdict recurs (H9 fails again, as predicted). D1 held (H1q lo 1.0112), D2 held narrowly (H3 lo 4.4e-5).
- 2026-09-21T23:27Z C1 read: C1A SUPPORTED (max R 0.0211 of 0.15 over six round-robin cells); C1B descriptive (R 0.036-0.215).
- 2026-09-21T23:27Z Ran the locked cor2_activity.py on raw_v3 (hashes matched Amendment 1; WORKERS=9 on CPUs 6-15). AW1 SUPPORTED, AW2 REFUTED as locked, AW3 ratio 1.016 [0.988, 1.045].
- 2026-09-21T23:27Z Independent cross-check e3/e3t_crosscheck.py (no shared code with the analysers): E3T D matches the locked values to 2e-17 at n=16 and 32, on raw and de-duplicated traces.
- 2026-09-21T23:27Z Wrote cycle3/CYCLE3_RESULTS.md (generated from the result files). FALSIFIED_CLAIMS: F19 (E3T T5, missing de-duplication), F20 (AW2); corrected F18's transition count (72 votes in 13,837 transitions, not 13,848; the paper already had 13,837). FINAL_REPORT: new section 4d, sections 5-6 rewritten (k<m-in-production claim removed per F17), "pre-specified".
- 2026-09-21T23:27Z Checked that no file in research/, paper/ or the logs contains the API key before committing the logs.
- 2026-09-21T23:36Z Full-epoch Aptos archive complete (all streams finished): 40 epochs, 7,691,847 rounds, 632 MB gz in raw_v3_full/ (not committed; not read by any lock). SHA-256 of every file in RAW_V3_FULL_SHA256.txt.
- 2026-09-22T00:25Z Paper revised with the Cycle-3 results (2a17666): E3T and C1 subsections, second Aptos sample + misspecification + activity weighting, lock table restructured (data at lock time, second-sample column; 34 predictions: 29 held, 4 failed, 1 inconclusive), abstract (<=200 words) and conclusion rewritten, 13 pages. Audits extended (bounds must hold and be tight; table counts must match the text).
- 2026-09-22T00:25Z Review pass: 5 MUST, 13 SHOULD, 7 COULD. Verified each MUST before fixing. Fixed: (1) the printed first-order gap formula was wrong (N0 mu should be pi0 mu; the quoted numbers were right, from the locked code); (2) "A8 is violated in production" overclaimed from a quorum-truncated record, now "bounds visible liveness"; (3) QKD contribution limited to the fastest measured links; (4) the Cosmos replay is labelled simulation under round-robin; (5) "held-out" added to the lock-timing statements. Also fixed SHOULD 6-17 and COULD 19, 21-24 (U renamed "uncarried demand", broadcast counted in messages, fault-arm 480 s, etc.).
- 2026-09-22T00:25Z Found while checking review item 3 (not raised by the reviewer): the QKD feasibility read the ring's guaranteed per-pair share as a ceiling. Added the cut-bound ceiling v_cap = v_max * 2(n-1)/n (feasibility.py, enumeration self-check); "infeasible" now requires v_cap < rate. Broadcast at n=16 on 304 kbps is undetermined, not failed. Recorded as F21. Central conclusion unchanged (Cambridge-grade: next-leader votes guaranteed to n=100; broadcast guaranteed at 32, infeasible at 64).
- 2026-09-22T00:25Z Removed Fig. 3 (serialized-delay residuals) and trimmed restated text to stay at 13 pages. Build clean (no undefined refs, no overfull boxes); audits pass: paper 114/114, all-numbers, Theorem A, Cycle-3 78/78; check_refs 36 PASS, 0 WARN, 0 FAIL. Not done (author's): data-availability statement with a DOI.
