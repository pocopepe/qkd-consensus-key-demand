# Gaps

Classified by whether the central claim survives without fixing them. The
central claim under audit is:

> Consensus demand predictability is fixed by the protocol's communication
> specification, computable in closed form as `π(n,m,k)`, bounded for
> recency-weighted predictors, and confirmed against a real implementation
> across `n`.

---

## FATAL

**None.**

Every candidate was checked and none reaches fatal:

- *"Theorem A is only tested on one implementation family."* — E2 tests a
  non-constant prediction across an eightfold `n` range with locked
  predictions, plus a control arm that spans both regimes. That is sufficient
  for the theorem as stated (hub-union protocols), which is what is claimed.
- *"π was measured with code that could be wrong."* — Recomputed here
  independently from raw trace data without the shared analysis path:
  0.566558 vs 0.566667 predicted. Not fatal.
- *"The security result is unsupported."* — True, and it is **excluded** from
  the paper. Excluded claims cannot be fatal.

---

## MAJOR — the paper is publishable only if these are fixed in writing or scope

| # | Gap | Fix |
|---|---|---|
| M1 | **No production system operates in the regime the theorem is interesting in.** E1 measured CometBFT at `k = m` (gossip) and libhotstuff at `m = 1` (stable leader, 98.9% one proposer even under induced faults). The `k < m` validation is on relab/hotstuff, a **research framework**. | **Writing.** Must be stated in the abstract-adjacent text, not buried in limitations. The honest framing: the theorem describes the chained-HotStuff *specification* faithfully implemented; whether a deployment sits in that regime is a separate, measurable question — and for the two production-lineage systems measured, the answer was no. |
| M2 | **C5 (shared-resource / topology) is substantially prior art.** Path-crossing starvation from key reservation is documented in Dervisevic et al.'s QKD key-management survey; advance path reservation with contention handling is Q-RoKR (ICC 2024). | **Scope + citation.** Demote C5 from contribution to supporting evaluation; cite both; claim only the *quantitative coupling to π and TTL* and the fresh/stale decomposition. |
| M3 | **The framing collides with temporal-network predictability limits** (Nat. Sci. Rev. 2020 and the temporal link-prediction line). | **Writing + citation.** Engage early and explicitly. The defensible distinction is *derived from a specification, computable with zero data, before deployment* versus *measured from a trace*. |
| M4 | **Predictive QKD key supply is published prior art** (Stan et al. JOCN 2025; evolutionQ patents; IEEE 2025 pre-provisioning). | **Citation + baseline.** Already handled by reimplementing DT-VQKP as the baseline; must be cited prominently and the paper must never claim predictive key supply as novel. |
| M5 | **Theorem B's scope limit is easy to overstate.** A periodicity learner reaches coverage 1.0000 against π = 0.5517 on deterministic schedules. | **Writing.** State the entropy condition as part of the theorem's presentation, not as a limitation paragraph. The bound is about a predictor *class*. |
| M6 | **Everything in C4/C5 is simulation.** | **Writing.** A single explicit table of which results are measured vs simulated. Draft exists in `EXPERIMENT_AUDIT.md`. |
| M7 | **E8 does not reproduce E1's magnitude** (+0.003 vs 33%). | **Writing.** Already handled correctly in the E8 report; must not drift to "explains" in the paper. "Reproduces the direction, not the magnitude." |
| M8 | **The repository is not under version control.** No commit history ties a result to the code that produced it. | **Code/process.** `git init`, commit, tag. One hour of work; do it before submission. |

---

## MINOR — presentation and reproducibility

| # | Gap | Fix |
|---|---|---|
| m1 | CIs computed and stored but not surfaced in every printed table | Writing |
| m2 | E4–E8 state hypotheses in advance but do not hash analysis code as E2 does | Process; note the asymmetry |
| m3 | E1's CometBFT n = 7/10/16 sweep never completed (driver killed) | Acceptable — at `k = m` the `(n−1)` factor cancels; already disclosed in the E1 report |
| m4 | Within a run, one RNG drives workload, admission and service order | Writing; arms share seeds so comparisons are unaffected |
| m5 | E6's "moderate" contention regime never bound (identical to low) | Writing; already disclosed |
| m6 | libhotstuff `mean_hops` metric averages over successful reservations only, including zero-success runs | Writing; already noted as a lower bound |
| m7 | Full text of the IEEE 2025 pre-provisioning paper not obtained (fetch failed) | Obtain before submission |

---

## ACCEPTABLE LIMITATIONS — disclose, no work required

- Loopback networking throughout; no WAN delay, loss, or reordering.
- XDP measured in skb mode on veth, not native on a NIC.
- The KME is our own compliant implementation; the 1.04–9.06 ms range is a
  conservative lower bound because it excludes network RTT.
- `n ≤ 32`; the asymptote `π → ½` is approached, not observed.
- One topology (`ring_with_chords`, seed 3) for the multi-hop arm.
- Tag-only authentication assumed; under one-time-pad payloads `π → 1` and the
  contribution evaporates (measured: slope 0.0034 at batch 256).
- Byzantine behaviour limited to leaders that fail to propose.
- Clique-support protocols (committee sortition) are out of Theorem A's scope.

---

## What is explicitly excluded from the paper

- The entire security/side-channel line (F9, H1, H2). The general claim is
  refuted against the correct baseline; the SSLE-conditional variant rests on
  four experiments that were never run; and the channel mechanism is SDN prior
  art.
- Any claim of real QKD hardware validation.
- Any claim that total fast-path hit rate is bounded by `π`.
