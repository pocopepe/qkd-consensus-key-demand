# E4 — operational translation

**OPERATIONALLY RELEVANT**, but not via the hypothesised mechanism.

    Q1  pi is a hard ceiling on hit rate.   max change 0.0161 over a 256x key-rate sweep
    Q2  required key RATE vs 1-pi:          NOT SUPPORTED (non-monotone, corr +0.36)
    Q3  wasted KEY vs 1-pi:                 corr +0.983, waste = 0.975*(1-pi) + 0.074
                                            structural waste exactly 0.0000 at every pi

Files: `E4_REPORT.md`, `figures/` (3 SVGs), `../E4-operational-001.json`.
Code: `research/e4_operational.py`.

Note: a bit-sizing error was found and fixed mid-experiment (a flat per-pair
arming amount inflated structural waste by ~0.8-0.93). All reported numbers are
post-fix; the incident is documented in the report.
