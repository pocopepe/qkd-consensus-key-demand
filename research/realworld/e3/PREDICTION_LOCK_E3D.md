# Prediction lock — E3d (held-out test of the role-dependent participation correction)

Written 2026-09-20T04:11:02Z, before any E3d run.

## What is being tested

E3 (serialised emulator) lost votes, mostly from the previous leader, and the
role-blind correction pi_p over-predicted. A post-hoc accounting fitted all 20
E3 wide-area runs to 0.0011. It is a first-order statement, and E3 is where it
was found, so E3 is development data and cannot test it.

**Claim.** Chained rotation, complete proposal stars, generic leader triple
a=L(t-1), b=L(t), c=L(t+1). Let mu_a be the expected number of missing votes per
view from the previous leader and mu_o from any other validator. A vote missing
in view t-1 leaves one proposal pair of view t uncarried (either role). A vote
missing from a in view t additionally removes the carried vote pair {a,c}.
Total demand falls by one unit per missing vote. To first order:

    pi_role = (n + 1 - 2 mu_a - mu_o) / (2(n-1) - mu_a - mu_o)

It returns pi(n,2,1) at mu_a = mu_o = 0. mu_a and mu_o are measured from the
same run, so this is a two-measured-parameter accounting model, not a
parameter-free prediction; what is tested is whether the role split is what
matters, against the role-blind pi_p(n,p) given the same total loss.

## Design

Original (serialised-delay) emulator binary, used deliberately as a reproducible
source of vote loss. n in {8,16,32} x 8 NEW geographies (seeds
`e3d-geo-<n>-<g>`; none of E3's `e3-geo-*` seeds is reused), 120 s, round-robin.
Frozen parser and structural analyser, adjacency-correct timeout-free
transitions, double-logged proposals collapsed (`e3c_dedup.py`), all as in E3c.

## Locked predictions

| ID | Prediction | Supported if |
|---|---|---|
| R1 | the role accounting reproduces the measurement | \|pi_role - pi_measured\| <= 0.002 in **every** run |
| R2 | role matters, not just total loss | among runs losing >= 0.03 votes per view, pi_role is closer than both pi(n,2,1) and pi_p in >= 90%; NOT_TESTABLE if < 5 such runs |
| R3 | the serialised emulator's loss is concentrated on the previous leader | pooled share of missing votes from L(t-1) >= 0.60 (E3: 0.84); NOT_TESTABLE if < 50 missing votes |

Development values (E3 wide-area runs, not evidence): R1 max 0.0010; R2 9 lossy
runs, pi_role closest in 8 of 9 (max residuals 0.0010 / 0.0134 / 0.0243 for
pi_role / pi_p / pi(n,2,1)).

## Hashes at lock time

    e3d_driver.py        bf49d07f7c6bf54574dddc23ac6f7571e56c2835fd7037762ed00c26ffbedd29
    e3d_analyze.py       145ee450a217173d9ea1177c547c9d48eff656b1764c1768a78b7d7d6be0b282
    e3_driver.py         de3294a13ad20c18e0d9c925dadb6637716d88d1f3921b7ae852b441744e35a5
    e3c_dedup.py         e3d8930812114bac27adc0ff419d986ff8bb9473850b8d1656848bdcdfae1a4f
    hotstuff binary      c7269ecd0c1e02f71d5a69b1c96d1ec21dbbf1e5c8faa29fa8494139c45c2a51

## Amendment 1 — my error in R2, corrected before any E3d run was opened (2026-09-20T04:11:54Z)

The lock above was written before I had run the final analysis script on the
development data. Doing so showed pi_role closest in 8 of 9 lossy E3 runs, not
"all 9" as first written (corrected in place above), so the 90% win band would
have failed on the development data itself. The miss is a run with little loss,
where all three formulas agree to a few 1e-4 and "closest" is noise. R2 is
therefore re-stated so that it measures the size of the improvement, not only a
count of near-ties:

**R2 (amended):** among runs losing >= 0.03 votes per view, pi_role is closest in
>= 80% of them **and** its mean absolute residual is at most half that of pi_p
and at most half that of pi(n,2,1). NOT_TESTABLE below 5 such runs.
Development values: 8/9 wins; mean residual 0.00039 vs 0.0031 (pi_p) and 0.0054.

The campaign had been launched about three minutes earlier; `raw_d/` held 0 file(s), none of
which had been opened or analysed. R1 and R3 are unchanged.

    e3d_analyze.py (amended)   99dff61103285e295c6fc231f52d390b73ec69efb4facf4bf7f0989e0d3e70d1

## Outcome (2026-09-20T18:38Z) — recorded after the locked pipeline ran

24/24 runs, no failures; all hashes above verified before analysis; 1,104 of
621,292 records de-duplicated (pre-registered step).
- **R1 SUPPORTED**: max |pi_role − measured| = 0.00093 over 24 runs (band 0.002);
  mean 0.00020. 15,498 transitions.
- **R2 SUPPORTED** (amended criterion): 15 lossy runs; pi_role closest in 14 (93%);
  mean |residual| 0.00030 vs 0.0026 (pi_p) and 0.0049 (pi(n,2,1)); max 0.0009 vs
  0.0108 vs 0.0198. Under the ORIGINAL 90% win band the result would also have
  held (14/15 = 93%); the amendment did not change the verdict.
- **R3 SUPPORTED**: 729 of 971 missing votes (75%) from the previous leader; 238
  from non-leaders; 4 from an adjacent leader (the case the proposition excludes).
