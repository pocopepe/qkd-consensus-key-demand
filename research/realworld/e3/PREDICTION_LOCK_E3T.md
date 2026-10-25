# Prediction lock — E3T: targeted single-role vote loss (falsification of Proposition 1's role claim)

Written 2026-09-21T20:12Z, **before any held-out run**. Held-out geographies use seeds
`e3t-geo-<n>-<g>`; none has been run. Amendments are dated and appended below, never edited in.

## Question

Proposition 1 says *which* validator loses a vote matters: a vote lost by L(t-1) ("a") or by
L(t+2) ("g") removes two carried units; one lost by L(t) ("b") or by any other validator removes one.
A role-blind correction (the paper's pi_phi) says only the total loss matters. At **equal total loss**,
the two make different predictions. This experiment can refute the proposition.

## Design (fixed)

- System: relab/hotstuff 3179c6e6, chained HotStuff, round-robin rotation, full mesh, per-message-delay
  emulation (the emulator fix), plus a sender-side vote-suppression injector. The injector suppresses a vote
  before it is sent (and before the E2 SEND_VOTE record), so the pair is genuinely not crossed; consensus and
  safety rules are untouched. Each suppression is logged separately (E3T SUPPRESS_VOTE).
- Build: `build_e3t.sh` is reproducible (-trimpath, -buildvcs=false); two independent builds gave identical binaries.
- Arms, all at LAMBDA = 0.2 expected suppressed votes per view (except none):
  none (baseline) · a only · g only · b only · other only (probability LAMBDA/(n-4) per other sender) ·
  blind (every sender, probability LAMBDA/(n-1): the role-blind null control).
- n in {16, 32}; 6 geographies per n (seeded city samples from the 217-city matrix); every geography runs
  every arm, so arms are compared within a geography. 120 s per run; runs are serial. 72 runs.
- Measurement: frozen parser and frozen structural analyser; adjacency-correct timeout-free transitions
  (as in E3c/E3d), **excluding each run's final view**, which the duration limit truncates.

- Validity guard (e3t_driver.py): a run is invalid if the host was suspended during it (CLOCK_BOOTTIME advanced
  more than 5 s beyond CLOCK_MONOTONIC) or its wall time exceeded 2x its duration + 60 s. Invalid runs move to
  raw_t/invalid/ with the reason; invalid or failed runs are re-run once, and a second failure is reported as missing.

## Predictions and bands (constants in e3t_analyze.py)

| ID | Prediction | Band | If it fails |
|---|---|---|---|
| T1 | Proposition 1, at each run's measured per-role loss rates, reproduces the measured pi | \|resid\| <= 0.002 in every lossy run | proposition's accounting is wrong |
| **T2** | **Role matters.** Per n, D = mean(pi_b, pi_other) - mean(pi_a, pi_g), averaged over geographies, is positive and matches Proposition 1's predicted D | 95% bootstrap CI of D (over geographies) excludes 0, **and** \|D - D_pred\| <= 0.5 D_pred | **the claim that which validator loses a vote matters is retracted from the paper** |
| T3 | The two double-cost roles behave alike, and so do the two single-cost roles | \|mean(pi_a - pi_g)\| and \|mean(pi_b - pi_other)\| each <= 0.5 D_pred | the role grouping is reported as wrong |
| T4 | Null control: under role-blind loss, Proposition 1 and the role-blind form both fit | both within 0.002 of measured in every blind run | measurement pipeline is suspect |
| T5 | Baseline: no suppression gives Corollary 1 | within 0.002 in every none run | apparatus is suspect |
| T6 | Selection guard: suppression does not change whether the next view is counted | per lossy arm, share of suppressed views whose next view is excluded within 0.10 of the share of all views excluded | T1–T3 reported with this caveat |

Predicted magnitude: D_pred ~ LAMBDA / (2(n-1) - LAMBDA) = 0.0067 at n = 16 and 0.0032 at n = 32. The role-blind
form predicts D ~ 0. On development data the per-run residual scale was <= 3.4e-4 at 40 s, so a paired design with
6 geographies resolves D at n = 32 with a margin of several standard errors.

## Data that existed when this lock was written

One **development** geography only (`e3t-dev-geo-16-0`, n = 16, 40 s per arm, directory raw_t_dev/), used to
validate the injector and the analyser. It showed: every suppression carries the intended role, none leaks
into the parsed records, roles agree with the observed proposer sequence; D = 0.0066 against D_pred = 0.0065
and a role-blind 0.0002; max \|T1 residual\| 3.4e-4. It also revealed that the final view of a run is
truncated (one run had a final view with demand 1 and pi = 1), which is why the analyser excludes it. No
held-out geography has been run.

## Resources

All work pinned to logical CPUs 6-15 (`taskset -c 6-15`, nice 10); CPUs 0-5 stay free.

## Revision history

- 2026-09-21T20:26Z: revised **before any held-out run** — added the validity guard above (driver hash updated). The guard was
  tested on a scratch run with a simulated 30 s suspend, which it set aside.

## Hashes at lock time

    hotstuff_e3t (binary)        1f30c02422e8dfe3aa6572456a81615c5b6711a0ab53485876b9d97b7f42ec9a
    build_e3t.sh                 8b6de82853d5630310609181912fd83336569000d847f49b69c47838bb2b62e2
    e3t_injector.diff            04660cf56922281a16073a4838e6f4ca8f3337aa55d4f8a38abf478b980e8b16
    emulation_fix.diff           2212a04d15ef5afc7292e5f8c849b7481278a4fa490708ad30a2f725db385ac5
    e3t_driver.py                12cd62153ce7b3c963dc8c4cd8ce3ea6d4bed8cbc80ff02fbb296bd88e57e23a
    e3t_analyze.py               cabeb343ee01a4ee8324580875ae9c55a332a0f34959efd1aca020dba7561d19
    e3_driver.py (imported)      de3294a13ad20c18e0d9c925dadb6637716d88d1f3921b7ae852b441744e35a5
    research/e2_parse.py         b771493e02020ba6adf2e74b3e303944c18a06254a08bc29cb99cb36b8a2c2de
    research/e1_analyze.py       5cbfb8d28f70e97285ee09d9e29ccb0a2d7a8efde57c898334b09caeb055d4e9
    pi_p_model.py                00acf59c5f2cca280d23e0e7e346aa3fd0da775f2aae670045b51febdc79c88a
