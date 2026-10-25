# E2 smoke test

**PASS.** relab/hotstuff `3179c6e6`, chainedhotstuff + clique + round-robin, n=4,
7,385 views, one run.

    predicted:  m=2  k=1  rho=0  pi=0.833333
    measured:   m=2  k=1  rho=0  pi=0.833333   (|delta| = 0.000000)

First observation of the non-degenerate regime `k < m` in a real implementation.

Files: `E2_SMOKE_REPORT.md`, `instrumentation.diff`, `analysis.json`,
`raw/smoke_run1.json`, `figures/fig_e2_view_graphs.svg`.

Reproduce:

    (cd ext/relab-hotstuff && git apply ../../research/results/e2_smoke/instrumentation.diff)
    /tmp/e2_smoke.sh
    python3 research/e2_parse.py /tmp/e2_smoke.log 4 research/results/e2_smoke/raw/smoke_run1.json
    python3 research/e2_analyze.py
    python3 research/e2_fig.py

Note: `research/e1_analyze.py:min_vertex_cover` was fixed during this test to
derive its vertex set from the trace instead of assuming `range(n)`; 1-indexed
replica IDs broke the old version. E1 results are unchanged by the fix.
