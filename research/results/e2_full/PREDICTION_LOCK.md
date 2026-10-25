# Prediction lock — E2 full matrix

Written and hashed **before** any matrix run was executed. Nothing below may be
changed after observing results; deviations are reported as errors, not as
revisions.

## Locked theorem

For chained HotStuff with clique communication and round-robin per-view
leadership:

    m = 2,  k = 1,  rho = 0

    pi(n) = [k(n-1) + m(m-k)] / [m(n-1)] = (n+1) / (2(n-1))

## Locked predictions, round-robin arm

| n | predicted pi |
|---:|---:|
| 4 | 0.8333333333 |
| 7 | 0.6666666667 |
| 10 | 0.6111111111 |
| 16 | 0.5666666667 |
| 32 | 0.5322580645 |

## Locked predictions, fixed-leader control arm

    m = 1,  k = 1,  rho = 0,  pi = 1.0   for every n

## Falsification criteria (locked)

The result is problematic if, systematically:

1. `m != 2` in the round-robin arm
2. `k != 1` under stable operation
3. `rho > 0.15`
4. `|pi_measured - pi_theory| > 0.05`
5. the observed curve does not follow the predicted n-dependence
6. the fixed-leader control does not produce `pi ~ 1`

A single anomalous run is to be investigated, not treated as theorem failure.

## Analysis pipeline state at lock time

The minimum-vertex-cover fix from the smoke test (candidate vertices derived
from the trace rather than assumed to be `range(n)`) is present and verified:

    research/e1_analyze.py:48   verts = sorted({v for e in edges for v in e})

SHA-256:

    5cbfb8d28f70e97285ee09d9e29ccb0a2d7a8efde57c898334b09caeb055d4e9  research/e1_analyze.py
    b771493e02020ba6adf2e74b3e303944c18a06254a08bc29cb99cb36b8a2c2de  research/e2_parse.py
    050e93e6685640e5884a8525355fab3743e16167c0044d12ad156968e1e8a04b  research/e2_analyze.py

Regression check against E1 traces, run at lock time — both unchanged from the
E1 report:

| trace | m | k | rho | pi |
|---|---|---|---|---|
| libhotstuff stable_run1 | 1.000 | 1.000 | 0.0000 | 1.0000 |
| CometBFT n4_run1 | 2.991 | 2.990 | 0.0000 | 1.0000 |

## System under test

    relab/hotstuff @ 3179c6e62929294961acbfd9bf8445769716a121
    working tree: +10 insertions (logging-only instrumentation, 4 files)
    go build ./... : clean

## Matrix

    n in {4, 7, 10, 16, 32}
    leader-rotation in {round-robin, fixed}
    5 repetitions each  =  50 runs
    >= 1000 analysed views per run
