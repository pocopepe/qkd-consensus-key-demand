# E2 full matrix

**STRONGLY SUPPORTED.** 50 runs, 0 failures.

    round-robin arm:  m=2, k=1, rho=0, max |pi_measured - pi_theory| = 0.000422
    fixed control:    m=1, k=1, rho=0, pi = 1.000000 exactly, all n

| n | pi theory | pi measured | error |
|---|---|---|---|
| 4 | 0.833333 | 0.833333 | 0.000000 |
| 7 | 0.666667 | 0.666657 | 0.000009 |
| 10 | 0.611111 | 0.611085 | 0.000026 |
| 16 | 0.566667 | 0.566645 | 0.000022 |
| 32 | 0.532258 | 0.531836 | 0.000422 |

Predictions were locked with script hashes in `PREDICTION_LOCK.md` before the
first run.

## Layout

    PREDICTION_LOCK.md   locked predictions + analyzer hashes + regression check
    E2_FULL_REPORT.md    the report (15 sections)
    raw/                 50 parsed traces
    processed/           all_runs.json (per-run statistics)
    tables/              table1_roundrobin, table2_control, table3_timeouts (JSON)
    figures/             fig1 pi vs n, fig2 residual, fig3 m/k vs n, fig4 timeouts
    failures.json        absent - no run failed

## Reproduce

    (cd ext/relab-hotstuff && git apply ../../research/results/e2_smoke/instrumentation.diff)
    go build -o /tmp/hsbin ./cmd/hotstuff
    python3 research/e2_driver.py          # resumable, 50 runs
    python3 research/e2_full_report.py     # tables + figures
