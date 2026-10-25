# Prediction lock — E3c (E3 repeated with corrected latency emulation)

Written 2026-09-19T00:58:29Z, before any E3c campaign run.

## Why E3c exists: a second flaw found in E3, by self-review

In E3, 555 of 663 missing votes (84%) came from one role: the **previous
leader**. That is too structured to be geography. The framework's latency
matrix rules out the explanation first written into the paper (a nearby next
leader out-racing a distant proposal): for the smoke geography, Auckland's
proposal reaches Amsterdam at 136 ms one-way, and London cannot issue the next
proposal before 152 ms — yet the log shows London's proposal arriving first.
Cause: relab sleeps for the emulated latency *inside* the gorums RPC handler,
which holds a per-sender stream lock until `ctx.Release()`. Two messages from
the same sender therefore queue, and delay accumulates. A far leader's late
vote for view t−2 (addressed to the previous leader) blocks its own proposal
for view t on the same stream, so exactly the previous leader sees that
proposal late, has already advanced, and does not vote.
This is an emulator artefact, not a wide-area phenomenon.

Fix (`emulation_fix.diff`, 4 inserted lines, emulation layer only — no
consensus logic): call `ctx.Release()` before sleeping, giving per-message
delay. Development evidence (one 20 s smoke run, the geography that first
showed the effect; not part of the campaign): views with a missing vote fell
from 14 of 108 to 0 of 125 complete views.

## Design

Identical to E3 — same instrumented tree plus the fix, same parser, same
hashed analyser, and the **same geography seeds**, so every E3c run is paired
with an E3 run. One change: f=5 fault runs last 480 s instead of 120 s (E3
obtained only 33–39 views per run). De-duplication of double-logged proposals
(`e3c_dedup.py`) is pre-registered here as the primary analysis input.

## Locked predictions

| ID | Prediction | Supported if |
|---|---|---|
| C1 | E3's vote loss was an emulator artefact | vote participation ≥ 0.999 on timeout-free transitions in **every** WAN run. If not, genuine latency-driven vote loss exists and is reported as such. |
| C2 | With per-message delay the spec-derived π(n,2,1) holds tightly | every WAN cell mean within 0.002 and every run within 0.005 of π(n,2,1); m=2 in ≥ 99% of transitions and mean ρ ≤ 0.01 in every run |
| C3 | Silent-proposer mixture (zero fitted parameters) | every fault run within ±0.03 of 0.537778 (f=1) / 0.369697 (f=5) — band unchanged from E3 |

`e3_analyze.py`'s own printed P1/P2/P3/F verdicts use E3's looser bands and are
reported, but C1–C3 above are the E3c criteria, evaluated from its per-run output.

## Hashes at lock time

    e3c_driver.py        367d1ef8f19e9b699ce3268f26053325bb661469a1810a2798f22fc35e10fc02
    e3c_dedup.py         e3d8930812114bac27adc0ff419d986ff8bb9473850b8d1656848bdcdfae1a4f
    e3_driver.py         de3294a13ad20c18e0d9c925dadb6637716d88d1f3921b7ae852b441744e35a5
    e3_analyze.py        18408e0479c80ff74fe4cc545663cedcef4f491b8f3d4f3218b5b79949e214cf
    emulation_fix.diff   2212a04d15ef5afc7292e5f8c849b7481278a4fa490708ad30a2f725db385ac5
    hotstuff_e3c binary  c8522a0ecb0f68d07ba32e9f689cbae92a29d0f811089f04dd5837393b6824f3

E3's results are kept and reported as what they are: the model under a stress
that turned out to be partly artefactual.

## Outcome (2026-09-19T02:34Z) — recorded after the locked pipeline ran

30/30 runs, no failures, all hashes above verified before analysis.
- **C1 FAILED as locked, narrowly**: 19 of 20 WAN runs have vote participation
  ≥ 0.999; `wan_n16_g1` has 0.99893. Minimum over runs 0.9989 (E3: 0.9663).
  Residual loss is 137 votes in 13,848 transitions, 4 from the previous leader
  (E3: 555 of 663); 113 are replicas that logged no proposal for that view.
  The artefact explains nearly all of E3's vote loss, not all of it to the band.
- **C2 SUPPORTED**: cell residuals +1.6e-4, +1.1e-4, +1.1e-5, −2.9e-5 at
  n=8,16,32,64; worst run 5.0e-4; m=2 in ≥ 99.89% of transitions; max ρ 0.0011.
- **C3 SUPPORTED**: max residual 0.0034 (f=1: 1,729 views; f=5: 250 views —
  480 s runs still yield only 48–52 views each because the view timer backs off).
Double-logged proposals: 81 of 890,023 records (E3: 733 of 827,404), as expected
once early arrivals are rarer. Raw-trace results kept in `E3C_RESULTS_RAW.json`.

Rebuild note: after the campaign the relab working tree was restored to the
frozen E2 instrumentation diff (`git apply -R emulation_fix.diff`), so E2's
reproducibility check still passes. `hotstuff_e3c` = that tree + the fix.
