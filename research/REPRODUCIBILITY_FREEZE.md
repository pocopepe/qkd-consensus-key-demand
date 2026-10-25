# Reproducibility freeze — `research-freeze-v1`

The state from which every number in the manuscript must be reproducible.
Created **after** the scientific record was frozen: no experiment was run, no
analysis code modified, no result altered, no prediction lock touched, no
theorem or claim document edited in the course of this checkpoint.

---

## 1. Repository state

| Item | Value |
|---|---|
| Repository | `/home/pocopepe/code/predictive` |
| Version control | initialised at freeze time — **no prior history existed** |
| Branch | `master` (git default; no prior branches) |
| Commit message | `Freeze research record before manuscript` |
| Tag | `research-freeze-v1` (annotated) |
| Freeze date | 2026-08-21 |
| Files committed | 271 |
| Bytes committed | 151,624,401 (≈145 MiB) |

**On the commit hash.** A commit hash cannot be embedded in a file that the
commit contains — the hash is computed over that content. The hash is therefore
recorded in the annotated tag `research-freeze-v1` and in the freeze report, not
here. `git rev-list -n1 research-freeze-v1` returns it.

---

## 2. Implementations under test

These are upstream repositories, cloned under `ext/`, each with its own git
history. They are **excluded from this repository** (§6) and pinned by commit
hash instead.

| Role | Repository | Commit | Date |
|---|---|---|---|
| **E1** — production-lineage, gossip | `github.com/cometbft/cometbft` | `dc83065f00b1cc441ddd1a1b3c5baca95c448967` | 2026-08-17 |
| **E1** — production-lineage, stable leader | `github.com/hot-stuff/libhotstuff` | `34aa50796f201aaab91c4db5aae9d3b7aceddb5c` | 2021-09-29 |
| **E2** — chained HotStuff, `k<m` | `github.com/relab/hotstuff` | `3179c6e62929294961acbfd9bf8445769716a121` | 2026-07-15 |

libhotstuff submodules: `salticidae @ bec7c8fee67ee34d888d2fdc118aefbd65f454c9`,
`secp256k1 @ 1e6f1f5ad5e7f1e3ef79313ec02023902bf8175c`.

### Working-tree modifications (all disclosed, all archived)

| Repository | Change | Archived diff |
|---|---|---|
| relab/hotstuff | **+10 insertions, 4 files, logging only, 0 logic changes** (`protocol/comm/clique.go`, `protocol/comm/factory.go`, `protocol/synchronizer/synchronizer.go`, `twins/node.go`) | `research/results/e2_smoke/instrumentation.diff` |
| libhotstuff | `#include <cstdint>` added to `include/hotstuff/type.h` (GCC 13 build fix) | `research/freeze/libhotstuff_cstdint.diff` |
| libhotstuff/salticidae | `#include <cstdint>` added to `include/salticidae/ref.h`, `include/salticidae/util.h` (GCC 13 build fix) | `research/freeze/salticidae_cstdint.diff` |
| CometBFT | **no source modification**; log level scoped to `p2p:debug`, `timeout_commit` lowered to 100 ms | — (runtime config only) |

**Verified at freeze time.** The archived relab/hotstuff instrumentation diff is
**byte-identical** to the live worktree diff, and `git diff --stat` confirms
`4 files changed, 10 insertions(+)` — matching `PREDICTION_LOCK.md` exactly.

**One discrepancy recorded, not corrected.** `EXPERIMENT_AUDIT.md` states
`#include <cstdint>` was added to **five** headers. The worktree contains
**three** (one in libhotstuff, two in salticidae). The change is a GCC 13
compilation fix with no behavioural effect and touches no measured quantity. It
is recorded here rather than edited into the audit document, because the mandate
for this checkpoint forbids modifying research documents.

Untracked build outputs left in the upstream trees (`ext/libhotstuff/log0…log3`,
`logclient`) are run logs, not inputs, and are excluded with `ext/`.

---

## 3. Prediction lock — verified at freeze time

Canonical file: `research/results/e2_full/PREDICTION_LOCK.md`, written and
hashed **before** any E2 matrix run.

**Locked analysis-script hashes, re-verified against the working tree at freeze
time — all three `OK`:**

```
5cbfb8d28f70e97285ee09d9e29ccb0a2d7a8efde57c898334b09caeb055d4e9  research/e1_analyze.py
b771493e02020ba6adf2e74b3e303944c18a06254a08bc29cb99cb36b8a2c2de  research/e2_parse.py
050e93e6685640e5884a8525355fab3743e16167c0044d12ad156968e1e8a04b  research/e2_analyze.py
```

Verification command and result:

```
$ sha256sum -c   # against the hashes recorded in PREDICTION_LOCK.md
research/e1_analyze.py: OK
research/e2_parse.py:   OK
research/e2_analyze.py: OK
```

**This is the load-bearing integrity fact of the freeze.** The analysis code that
produced the E2 numbers is byte-identical to the code hashed before the first
run.

Locked predictions (round-robin arm): `π(4)=0.8333333333`, `π(7)=0.6666666667`,
`π(10)=0.6111111111`, `π(16)=0.5666666667`, `π(32)=0.5322580645`; control arm
`π = 1.0` for every `n`. Falsification criteria as recorded in the lock file.

---

## 4. Experiment result directories

All committed unless noted.

| Experiment | Directory | Contents |
|---|---|---|
| **E1** | `research/results/e1/` | `E1_REPORT.md`, `README.md`, `trace_model.md`, `processed/` (12 files), `tables/` (2), `figures/` — **`raw/` excluded, see §6** |
| **E2 smoke** | `research/results/e2_smoke/` | full, incl. `instrumentation.diff` |
| **E2 full** | `research/results/e2_full/` | `E2_FULL_REPORT.md`, `PREDICTION_LOCK.md`, `raw/` (**committed**, 136 MiB, 50 runs), `processed/all_runs.json`, `tables/` (3), `figures/` |
| **E4** | `research/results/e4/` + `E4-operational-001.json` | full |
| **E4-TTL** | `research/results/e4_ttl/` + `E4TTL-001.json` | full |
| **E5** | `E5-theorem-b-001.json` | full |
| **E6** | `research/results/e6_shared_pool/` + `E6-sharedpool-{001,fifo,random}.json` | full |
| **E7** | `research/results/e7_burst/` + `E7-burst-001.json` | full |
| **E8** | `research/results/e8_hop_amplification/` + `E8-hopamp-001.json` | full |
| Supporting | `G-general-pi-001.json`, `P-predictor-zoo-001.json`, `V-realism-001.json`, `M-marginal-leak-001.json`, `S-ssle-leak-001.json` | full — the last two support **excluded** claims (F9) and are retained deliberately |

83 result JSON files committed in total.

---

## 5. Seeds

The result JSONs for E4, E4-TTL, E6 (all three arms), E7 and E8 carry a `seeds`
key — verified present at freeze time. It records the **seed count**, not the
seed values: E4 stores `20`, E6 and E8 store `10`. Per `EXPERIMENT_AUDIT.md` the
seeds are the contiguous integer ranges `range(20)` / `range(10)` passed to
`np.random.default_rng(seed)`, and the seed *values* are therefore recoverable
from the driver scripts rather than from the result files.

**Recorded as a weakness, not smoothed over:** the result files pin how many
seeds were used, not which. Reproduction depends on the committed driver scripts
preserving the `range(...)` construction.

E5, `general_pi`, and the predictor zoo record no seed key: E5 and `general_pi`
are exhaustive/analytic, and the predictor zoo records `views: 600, warm: 120`
with its schedule families instead.

**Known caveat, carried forward from `EXPERIMENT_AUDIT.md`:** within a run a
single RNG drives workload, admission order and service order, so those three
streams are correlated within a run. Arms share seeds, so comparisons are
unaffected.

---

## 6. Deliberately excluded from git

| Path | Size | Reason | Mitigation |
|---|---|---|---|
| `ext/` | 222 MiB | Three upstream repositories, each with its own `.git` (plus two nested submodules). Committing them would nest histories and misrepresent authorship | Commit hashes + submodule pointers in §2; all instrumentation diffs archived and committed |
| `research/results/e1/raw/` | **1,757,388,314 bytes** (1.64 GiB, 30 files) | Raw CometBFT p2p debug traces. Storing them would make the repository unusable and unpushable | **Every file SHA-256 pinned** in `research/freeze/EXCLUDED_RAW_SHA256.txt` (committed). Files remain on disk, **not deleted**. All E1 derived outputs — `processed/`, `tables/`, `figures/`, `E1_REPORT.md` — are committed |
| `__pycache__/`, `*.pyc` | 104 KiB | Python bytecode, regenerated on import | none needed |

**E2's raw traces are committed** (136 MiB, `research/results/e2_full/raw/`),
because E2 is the paper's core empirical claim and its inputs should be
reproducible without recourse to a hash manifest.

Compiled artefacts `src/xdp_enforcer.o` (36,600 B) and `bpf/prearm.bpf.o`
(17,000 B) **are committed** — these are the exact objects the verifier
instruction counts were measured against.

---

## 7. Toolchain

Recorded as observed at freeze time. Not all of it was recorded at the time the
experiments ran; where that is so, it is stated rather than inferred.

| Component | Version |
|---|---|
| OS | Ubuntu 24.04.4 LTS, `x86_64` |
| Kernel | `6.8.0-138-generic` |
| Python | 3.12.3 |
| NumPy | 1.26.4 |
| Go | `go1.22.2 linux/amd64` |
| GCC | 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1) |
| clang | **not on `PATH` at freeze time**; `/usr/bin/clang-15` present and is the presumptive BPF compiler — *not verified against the build that produced the committed `.o` files* |
| bpftool | v7.4.0 |
| SciPy | **not installed** — no analysis path depends on it |
| `requirements.txt` | `numpy>=1.24` (sole declared dependency) |

**Not recorded at experiment time and therefore unavailable:** exact clang
invocation and version for the BPF objects; CPU model and core count; memory
size; whether any run shared the host with other load. These were not captured
when the experiments ran and are **not reconstructed here.**

---

## 8. Manuscript-source state

No manuscript prose exists at freeze time. What is committed is the construction
apparatus only:

| File | Role |
|---|---|
| `research/MANUSCRIPT_BLUEPRINT.md` | section-by-section construction spec, figure/table plan, title options, final thesis |
| `research/EVIDENCE_MAP.md` | claim → experiment → artefact → statistic → limitation |
| `research/PAPER_CLAIM_LANGUAGE.md` | BAD/GOOD phrasing audit, cleared sentences, pre-submission grep list |
| `research/PAPER_THESIS.md` | novelty lock |
| `research/PAPER_SPINE.md` | earlier structural draft, superseded by the blueprint, retained |
| `research/NOVELTY_MATRIX_FINAL.md`, `research/NOVELTY_WORDING_FINAL.md` | novelty scoring and conservative wording |
| `research/ICUMT_2025_FULLTEXT_AUDIT.md` | final prior-art gate |
| `research/RELATED_WORK_AUDIT.md`, `research/GAPS.md`, `research/CLAIM_LEDGER.md`, `research/EXPERIMENT_AUDIT.md`, `research/FINAL_RESEARCH_CLAIMS.md`, `research/FALSIFIED_CLAIMS.md`, `research/theory.md`, `research/research_direction.md` | frozen research record |

`paper/` contains the earlier preliminary draft produced before the audit
sequence. It is committed as historical record and **is not the manuscript**;
the blueprint supersedes it.

---

## 9. What this tag guarantees

- The analysis code that produced the E2 numbers hashes to the values fixed
  before the first E2 run (§3, verified).
- The implementations under test are pinned by commit, and every modification to
  them is archived as a diff (§2).
- Every result artefact behind every manuscript number is committed, except the
  E1 raw traces, which are SHA-256 pinned file by file (§6).

## 10. What it does not guarantee

- Bit-identical re-execution: host hardware, clang version, and concurrent load
  were not recorded (§7).
- E1 raw traces are pinned but not stored; if the working copies are lost, the
  E1 numbers can be checked against `processed/` but not recomputed from source
  traces.
- Nothing here revalidates any scientific claim. This is a provenance
  checkpoint, not a re-verification.

---

## Commit hashes changed on 2026-09-19 (file contents did not)

The commit messages of this repository were edited on 2026-09-19. No file was
changed: every commit keeps the same tree, author, and dates, which the table
lets anyone check with `git rev-parse <new>^{tree}`. Because a commit hash
covers its message, all hashes changed, and the two freeze tags were re-created
on the corresponding new commits with their original tagger and date.

Documents and result metadata written before that date cite the **old** hashes
— among them `research/results/predictor_zoo_corrected/P-predictor-zoo-corrected-001.json`,
which is frozen and was deliberately left as it is. Use this table to resolve
them. The tag *names* are the stable identifiers.

| Old commit | New commit | Tree (unchanged) | Subject |
|---|---|---|---|
| `330b87b6d69f` | `266889ff4112` | `ff8591a1d31f` | Freeze research record before manuscript |
| `123ec8b957d2` | `84fdd0608c63` | `73d780bc269e` | Add corrected demand-weighted predictor evaluation |
| `ff79aa501589` | `b3c2c9f6e4e3` | `50a0ea523749` | Set up research council coordination |
| `3a7de4059c88` | `ae9d27c86a04` | `b9f77b5d6823` | Archive development history and add the live demonstration |
| `d191ead473ef` | `13991e57f0f6` | `5750f8803187` | Add pre-registered real-world validation campaigns |
| `f954a88280b9` | `6b9b8ecd0b6c` | `65ad8aa1c0cc` | Add Cosmos Hub participation campaign |
| `e82800214db4` | `2eb30795d049` | `ea8413aceacf` | Integrate wide-area and production results into the manuscript |

`research-freeze-v1` → `266889ff4112` · `predictor-zoo-corrected-v1` → `84fdd0608c63`

## Working-tree cleanup (2026-09-22)

The manuscript-planning documents listed in the manifest above (`MANUSCRIPT_BLUEPRINT.md`, `EVIDENCE_MAP.md`,
`PAPER_THESIS.md`, `PAPER_SPINE.md`, `PAPER_CLAIM_LANGUAGE.md`, `NOVELTY_MATRIX_FINAL.md`, `NOVELTY_WORDING_FINAL.md`,
`ICUMT_2025_FULLTEXT_AUDIT.md`, `FINAL_REPO_MANIFEST.md`) and the development-review archive were removed from the
working tree. They remain unchanged at the tags; no result, lock, analysis script or frozen record was touched.
