# E1 — real-implementation validation

Verdict: **PARTIALLY SUPPORTED**. See `E1_REPORT.md`.

The hub-union model fits both real implementations exactly (ρ = 0.0000) and the
closed form predicts persistence with error ≤ 0.0013. But every configuration
measured sits at k/m = 1, where π = 1 and forecasting gain is zero. Neither
implementation exhibits per-view leader rotation — the regime the research
direction depends on.

## Layout

    trace_model.md   definitions, fixed before any trace was inspected
    E1_REPORT.md     the full report
    raw/             per-run parsed traces (JSON)
    processed/       per-run summaries and all_summaries.json
    tables/          table1_theory_vs_measured.json, table2_fit_quality.json
    figures/         fig1, fig2, fig3 (SVG)

## Reproduce

    python3 research/e1_parse.py <logdir> <netdir> <out.json>     # CometBFT
    python3 research/e1_parse_hs.py <hotstuff dir> <n> <out.json> # libhotstuff
    python3 research/e1_analyze.py <trace.json>                   # single trace
    python3 research/e1_report.py                                 # tables+figures
    python3 research/e1_fig3.py                                   # view graphs

Campaign drivers: `research/e1_driver.py` (CometBFT, resumable),
`/tmp/e1_hscamp.sh` (libhotstuff, stable + induced regimes).

Builds: CometBFT v0.40.0 `dc83065`; libhotstuff HEAD with `-DHOTSTUFF_PROTO_LOG=ON`.
