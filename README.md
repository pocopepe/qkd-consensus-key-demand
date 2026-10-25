# Predicting QKD Key Demand of BFT Consensus

Code, data and prediction records for *Predicting QKD Key Demand of Byzantine Fault-Tolerant Consensus From the Protocol
Specification* (A. Viju Sanjai and R. Dhanalakshmi, Vellore Institute of Technology, Chennai).

Archived with the raw trace data on Zenodo: https://doi.org/10.5281/zenodo.23646236

The paper changes neither the consensus protocol nor the QKD layer. It models the key demand that an unmodified
leader-based BFT protocol places on QKD key management, and shows that this demand can be read from the protocol
specification before deployment.

## Research question

A BFT consensus cluster authenticates many messages per view, and each authenticated message between a pair of
validators consumes shared secret key. When that key comes from quantum key distribution it is scarce, so systems
pre-position it on the pairs expected to need it. How much of that per-pair demand can be read from the protocol
specification before deployment, and what does it constrain?

## Main result

For protocols whose per-view communication support is a union of `m` stars, `k` of which persist into the next view,
the demand-weighted persistence of that support is

```
pi(n,m,k) = [k(n-1) + m(m-k)] / [m(n-1)]  =  k/m + (m-k)/(n-1)
```

under full participation. The demand that cannot be carried from the previous view is `(m-k)(n-1-m)` per view. For
chained HotStuff with per-view rotation, `pi(n) = (n+1)/(2(n-1))`.

## Evidence

Every prediction was fixed, with SHA-256 hashes of the analysis code, before its held-out data existed. There are 34
predictions: 29 held, 4 failed and 1 was inconclusive. All are reported in the paper's table of pre-specified predictions and in
`research/realworld/`.

- **Loopback**, instrumented chained HotStuff (`n = 4 … 32`): the largest residual is `4.2e-4`.
- **Emulated wide-area latency** (`n = 8 … 64`) and silent-proposer faults: cell residuals are at most `1.6e-4`. Fault
  arms are predicted with no fitted parameter.
- **Role-dependent vote loss.** A vote lost by the previous leader, or by the leader two views ahead, costs twice what
  any other lost vote costs.
  - Targeted suppression confirms the predicted role effect (`0.00644` measured against `0.00635` predicted at
    `n = 16`), which a role-blind correction misses by two orders of magnitude.
  - Replayed Cosmos Hub absences follow it in simulation.
- **Aptos mainnet leader schedule** (300,000 rounds on two disjoint samples): chained rotation driven by the real
  schedule stays within the locked tolerance of the stake-weighted form, but that form is measurably misspecified.
  - Aptos itself broadcasts votes, so it operates at `k = m`.
  - Its vote record is quorum-truncated and cannot measure participation.
- **Cosmos Hub** (9,000 blocks, `n = 180`): participation is `0.9933` by validator count and `0.9979` by voting power.
- **Standing key stock.** A key manager that follows recent demand serves the fraction `pi` on time. A pool on every
  pair, refilled as it is used, does better, and the model gives its depth: on 66 held-out epochs of the Aptos leader
  schedule, 4 tags per pair serve 99% of messages on time when key takes five views to relay and 12 when it takes
  fifty. Under round-robin rotation four tags per pair serve every message.
- **QKD feasibility.** At measured field key rates and Aptos's view rate, sending votes to the next leader is sustainable
  on Cambridge-grade links up to `n = 100`, while broadcasting votes is not at `n = 64`.

Refuted hypotheses and corrected readings are listed in `research/FALSIFIED_CLAIMS.md`.

## What this archive contains

| Path | Contents |
|---|---|
| `research/realworld/` | Wide-area, vote-loss, Aptos, Cosmos Hub, key-stock, production-chain and QKD-feasibility campaigns: prediction records (`PREDICTION_LOCK_*.md`), analysis code, raw data, results, and the scripts that audit every number quoted in the paper |
| `research/results/`, `research/freeze/` | The earlier loopback campaigns and their frozen results |
| `research/formula_check/` | Independent checks of every theorem and formula-derived number: exact enumeration, exact fractions and simulation |
| `research/capacity/` | The lower bound for pairwise authentication evaluated against seven production chains |
| `bpf/`, `src/`, `kme/`, `qkdnet/`, `simulator/`, `scripts/`, `test/`, `demo/` | Supporting code: data plane, an ETSI GS QKD 014 key management entity, simulators and harnesses |
| `archive/` | Early experiments that some operational numbers still draw on |

Two further files accompany this archive in the same record:

- `aptos-full-epochs-raw_v3_full.tar`: the full-epoch Aptos leader-schedule records (42 files).
- `cometbft-e1-raw-traces.tar.gz`: raw CometBFT traces of the first loopback campaign (31 files).

`SHA256SUMS.txt` and `cometbft-e1-raw-traces.SHA256.txt` give their checksums.

## What it leaves out

- **The manuscript.** The article source and PDF are not part of this archive while the article is under review. The
  number audits (`research/realworld/audit_*_numbers.py`) compare the result files with the manuscript text, so they
  run only once the manuscript is placed at `paper/paper.tex`. Every other script runs from this archive alone.
- **The journal's template files**, which are not ours to redistribute.
- **`ext/`**, the upstream implementations under test. They are pinned by commit hash in
  `research/REPRODUCIBILITY_FREEZE.md` and are fetched from their own repositories.

## Checking the results

```
python3 research/formula_check/thm1_lemma.py        # Theorem 1 over 66,178 realisations (needs sympy)
python3 research/formula_check/role_loss.py         # role-dependent vote loss, exact and simulated
python3 research/realworld/stock/stock_levels.py views   # key-stock results on the held-out epochs
python3 research/realworld/chains/budget.py         # key budget of seven production chains
python3 research/capacity/floor.py                  # the authentication floor against those chains
./demo/run.sh
```

`research/formula_check/README.md` lists all nine formula checks.

## Reproducibility

The earlier record is frozen at two annotated tags, `research-freeze-v1` and `predictor-zoo-corrected-v1`.
`research/REPRODUCIBILITY_FREEZE.md` records the implementation commits, the instrumentation diffs and the script
hashes. Each later campaign's record (`PREDICTION_LOCK_*.md`) lists the SHA-256 hashes of its analysis code and the
data that existed when it was written.

Scripts whose hashes appear in a prediction record are published exactly as they were run. Some of them contain
absolute paths of the machine they ran on; set the `ROOT` variable or the path at the top of the script to the
location of this archive before running them.

Refuted hypotheses and corrected readings are listed in `research/FALSIFIED_CLAIMS.md`.
