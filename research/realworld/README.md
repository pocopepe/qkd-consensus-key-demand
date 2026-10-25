# Real-world validation

Campaigns that re-test the persistence result outside loopback. Each has a
prediction lock (`PREDICTION_LOCK_*.md`) written before its data existed, holding
the hypotheses, the numeric bands, and SHA-256 hashes of the code. Start with
`FINAL_REPORT.md`.

| Campaign | Lock | Raw data | Results |
|---|---|---|---|
| Aptos mainnet, 30 epochs × 2000 rounds | `PREDICTION_LOCK_V2.md` | `raw_v2/` | `V2_RESULTS.json`, `V2_POSTHOC.json` (exploratory) |
| Provisioning loop on real leader sequences | `PREDICTION_LOCK_H7.md` | `raw_v2/` | `H7_RESULTS.json` |
| Emulated WAN + silent proposers, first run | `e3/PREDICTION_LOCK_E3.md` | `e3/raw/` | `e3/E3_RESULTS.json`, `e3/E3_RESULTS_DEDUP.json` |
| Same, corrected emulator (paired geographies) | `e3/PREDICTION_LOCK_E3C.md` | `e3/raw_c/` | `e3/E3C_RESULTS.json`, `e3/E3C_VERDICTS.json` |
| Role-dependent vote loss, held-out geographies | `e3/PREDICTION_LOCK_E3D.md` | `e3/raw_d/` | `e3/E3D_RESULTS.json` |
| Cosmos Hub, production participation | `cosmos/PREDICTION_LOCK_COSMOS.md` | `cosmos/raw/` | `cosmos/COSMOS_RESULTS.json` |
| Aptos v1, 5 epochs — **interpretation withdrawn** | `PREDICTION_LOCK_H1.md`, `PREDICTION_LOCK_H2_H3.md` | `raw/` | `H2_H3_APTOS_HELDOUT_RESULT.json` |

## Re-running

All commands from the repository root. None writes under `research/results/`.

```
# Aptos: independent recomputation against the stored results (11 s)
python3 research/realworld/v2_independent_verify.py research/realworld/raw_v2 research/realworld/V2_RESULTS.json
# Aptos: full locked analysis (about 20 min; includes the predictor zoo)
python3 research/realworld/v2_analyze.py research/realworld/raw_v2 /tmp/v2.json

# Wide-area campaigns: rebuild the de-duplicated traces, then the locked analyser
python3 research/realworld/e3/e3c_dedup.py research/realworld/e3/raw   research/realworld/e3/raw_dedup
python3 research/realworld/e3/e3c_dedup.py research/realworld/e3/raw_c research/realworld/e3/raw_c_dedup
python3 research/realworld/e3/e3_analyze.py research/realworld/e3/raw_c_dedup /tmp/e3c.json
python3 research/realworld/e3/e3c_verdicts.py

# Role-dependent vote loss (E3d)
python3 research/realworld/e3/e3c_dedup.py research/realworld/e3/raw_d research/realworld/e3/raw_d_dedup
python3 research/realworld/e3/e3d_analyze.py research/realworld/e3/raw_d_dedup /tmp/e3d.json
# Proposition 1 as corrected (four roles; not pre-registered) and its brute-force check
python3 research/realworld/e3/e3d_posthoc_roles.py research/realworld/e3/raw_d_dedup /tmp/e3d_roles.json
python3 research/realworld/e3/role_loss_check.py        # asserts; about 1 min

# Cosmos Hub
python3 research/realworld/cosmos/cosmos_analyze.py research/realworld/cosmos/raw /tmp/cosmos.json

# Standing key stock on the Aptos leader schedule (about an hour on ten cores; written against four epochs, run on the other 66)
python3 research/realworld/stock/stock_levels.py heldout research/realworld/stock/STOCK_RESULTS.json

# E2 table recomputed from the frozen raw traces, read-only (40 s)
python3 research/realworld/reproduce_e2_from_raw.py
```

## Guards on the manuscript

```
python3 research/realworld/audit_paper_numbers.py   # wide-area + production numbers, one by one
python3 research/realworld/audit_all_numbers.py     # older sections, per experiment family
python3 research/realworld/audit_stock_numbers.py   # standing key stock numbers
python3 paper/tools/audit_theorem_a.py              # closed-form table and figure
python3 research/realworld/make_figure_data.py      # regenerates the figure coordinates
python3 research/realworld/v2_posthoc_spread.py     # post-hoc: predicted vs observed epoch-to-epoch spread
```

## Rebuilding the corrected emulator binary

`ext/` is not tracked. In `ext/relab-hotstuff` (commit `3179c6e6`, with
`research/results/e2_smoke/instrumentation.diff` applied):

```
git apply ../../research/realworld/e3/emulation_fix.diff
go build -o hotstuff_e3c ./cmd/hotstuff
git apply -R ../../research/realworld/e3/emulation_fix.diff
```

Binary hashes are recorded in the E3 and E3c locks.
