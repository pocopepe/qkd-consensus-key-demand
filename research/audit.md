# Research audit

Adversarial review of this repository against the question: can the strongest
surviving result be developed into a defensible IEEE paper?

**Headline finding of this audit: the central security claim in the current
draft is refuted by an experiment the repository did not previously contain.** A
narrower claim survives and is defensible. Details in §3 and §5.

Evidence for every statement below is named. Where the repository asserts
something without evidence, that is recorded as an assumption, not a result.

---

## 1. Current research question

As implemented, the repository asks three separable questions that the existing
draft conflates:

- **Q1 (systems).** Can a kernel-resident enforcement layer commit predicted QKD
  key allocations fast enough to matter for a consensus deadline?
- **Q2 (theory).** What determines the accuracy ceiling of demand forecasting
  for consensus key supply?
- **Q3 (security).** Does predictive pre-arming leak proposer identity?

Q1 and Q2 are supported. Q3 as currently stated is **not**.

---

## 2. Strongest supported claim

**The accuracy ceiling of any carry-forward forecaster is the support
persistence of the workload, and support persistence is fixed by the consensus
protocol's steady-state message complexity.**

- `π = 1` exactly for all-to-all protocols (PBFT, Tendermint, Narwhal, Simplex),
  every `n` tested.
- `π(n) = (n+1)/(2(n−1)) → 1/2` for rotating-leader linear protocols.
- Best-α EWMA coverage `= π` to `0.00e+00` error across 7 protocols, `n = 4…256`.
- Structural gain `= 1 − π` identically.

*Evidence:* `research/protocols.py`, `research/duality_study.py`,
`research/verify_duality.py` D1–D3. Symbolically derived and independently
checked against exact periodic steady states.

This is mathematically derived, reproducible, and — see §5 — not obviously
anticipated. It is the strongest thing here.

---

## 3. Claims that must be removed

### 3.1 The impossibility corollary (REFUTED)

The draft claims: *"predictive key pre-arming and proposer privacy cannot
coexist in a rotating-leader protocol."*

This is wrong, because the leakage was measured against **chance (1/n)** rather
than against **an observer who simply watches consensus traffic**. That is the
insufficient-baseline error.

`research/marginal_leak.py` (experiment `M-marginal-leak-001`), n = 16, 400
views, chained linear protocol:

| horizon | target | traffic-only | pre-arm | marginal |
|---|---|---|---|---|
| H=1 | L(t+1) | **1.0000** | **1.0000** | **+0.0000** |
| H=2 | L(t+2) | 0.0000 | 0.0625 | +0.0625 (= baseline) |
| H=3 | L(t) | 0.9375 | 0.8125 | **−0.1250** |
| H=4 | L(t+1) | 1.0000 | 0.8125 | **−0.1875** |

At H = 1 — the only horizon with any measured performance benefit — pre-arming
discloses **nothing** the observer could not read off the wire. The vote phase of
a chained protocol is addressed to the next leader, so the wire already names it.
At larger horizons the marginal on the near-term leader is **negative**: a wider
pre-arm set blurs the degree ranking relative to traffic.

**Consequence.** The draft's abstract, Corollary "Impossibility", and the framing
of Theorem "Duality" as a security result must be withdrawn.

### 3.2 The "gain − leak = 1/2" identity as a *security* statement

The algebra is correct (`verify_duality.py` D7, verified to `2.22e-16`). The
interpretation is not. `adv(n)` was computed against a chance baseline; with the
correct baseline the security quantity is ~0 for chained protocols. The identity
survives as a statement about two closed forms; it does not survive as a claim
about privacy.

### 3.3 The "duality" framing is close to tautological

Both halves follow from one structural fact: the demand support is a star centred
on the leader. That a leader-shaped support (a) is predictable from the leader
and (b) identifies the leader is close to a restatement. A reviewer will say so.
The non-trivial content is quantitative (the closed forms), not conceptual.

---

## 4. Claims that are supported

| Claim | Evidence type | Where |
|---|---|---|
| Verifier instruction count is invariant in map capacity (244 insns, 16,384× range; full enforcer 2851) | **Measured**, Linux 6.8 | `test/t1_insns.sh` |
| Map update bandwidth is the binding constraint; 2.98 µs/entry serial, 1.16 µs batched | **Measured** | `test/t2_update_cost.sh` |
| XDP fast path 14.2 µs p50, 548 ns in-kernel service | **Measured** | `test/t3_latency.sh`, `scripts/daemon_live.sh` |
| Real ETSI GS QKD 014 fetch 1.04–9.06 ms depending on connection reuse | **Measured** (loopback) | `kme/bench_kme.py` |
| Round latency is a quorum order statistic; additive objective mis-specifies it | Derived + simulation | `qkdnet/consensus.py`, `scripts/gap_bench.py` |
| Density-greedy ≈ optimal here; `G ≥ (1−w_max/C)·OPT` | **Proved** + 0/4000 violations | `verify_theory.py` T4 |
| Support persistence closed forms | **Proved** + verified to 0 error | `verify_duality.py` D1–D3 |
| Pre-arming increases starvation up to 33%; short lease fixes it, hoarding penalty does not | Simulation, 21,900 rounds | `scripts/exp_b_hoarding.py` |
| Structural forecaster beats DT-VQKP (0.588 vs 0.004 hit rate) | Simulation + faithful reimplementation | `research/bench_baselines.py` |

---

## 5. Claims requiring more evidence

### 5.1 The surviving security claim (promising, under-evidenced)

The refutation in §3.1 is specific to protocols whose traffic already names the
next leader. Under **secret leader election** with **subnet gossip** it does not
apply: attestations are gossiped to subnets rather than addressed to the next
proposer, so traffic reveals L(t) after the fact and nothing about L(t+1).

`research/ssle_leak.py` (`S-ssle-leak-001`), n = 16, 400 views:

| attestation coverage | traffic → L(t+1) | self-arm → L(t+1) | marginal |
|---|---|---|---|
| 0.25 (subnet) | 0.0650 | **0.9450** | **+0.8800** |
| 0.75 | 0.0675 | 0.8425 | +0.7750 |
| 0.90 | 0.0500 | 0.2400 | +0.1900 |
| 1.00 (all-to-all) | 0.0475 | 0.0475 | +0.0000 |

Scaling at coverage 0.25: marginal +0.750 (n=7) → **+0.9875 (n=128)**.

This is a real, large, baseline-corrected effect. It is also a **much narrower
claim**: it holds for protocols that hide the proposer and gossip attestations
below ~0.75 coverage. That describes Ethereum; it does not describe HotStuff.

**What it still needs** — see §11.

### 5.2 Everything about the attack is model-level, not end-to-end

The leader-inference attack has **never been run against the real XDP testbed**.
What exists is (a) a measured timing gap and (b) a structural argument computed
in the abstract protocol model. The composition is plausible but unproven. No
figure in this repository shows an adversary recovering a leader from packets
captured on a wire.

---

## 6. Novelty assessment and related-work threats

### 6.1 Threat: the timing channel mechanism is not new

Data-plane table hit/miss producing an observable timing difference that reveals
table state is **established prior art in SDN**, repeatedly, since 2015:

| Work | Venue/Year | Contribution | Threat |
|---|---|---|---|
| Bifulco *et al.*, "Fingerprinting Software-defined Networks" | ICNP 2015 (arXiv 1512.06585) | Timing of probe packets fingerprints SDN presence and configuration | **High** — same mechanism |
| Sonchack *et al.*, "Timing-based Reconnaissance / Flow Reconnaissance via Timing Attacks on SDN Switches" | ICDCS 2016 | Infers flow-rule presence from probe latency | **High** — same mechanism |
| Liu *et al.*, "Know Your Enemy: Stealth Configuration-Information Gathering in SDN" | arXiv 1608.04766 | Flow-table side channel yields network configuration | **High** |
| Cao *et al.*, LOFT / flow-table saturation | 2020–2023 | Infers table state, then exploits it | Medium |

**Assessment.** The *channel* is not novel. Any claim of a "new side channel"
will be rejected. What is potentially novel is the **semantic target** — the
leaked secret is a consensus proposer identity protected by a dedicated
cryptographic mechanism — and the fact that the channel is opened by an
optimisation intended to improve availability, not by a reactive cache.

### 6.2 Threat: a cheaper attack already achieves the adversary's goal

Heimbach *et al.*, **"Deanonymizing Ethereum Validators: The P2P Network Has a
Privacy Issue," USENIX Security 2025**, locate >15% of Ethereum validators by
observing attestation propagation, and explicitly motivate it with targeted DoS.

**Assessment.** This is the most serious threat to *practical significance*. If
an adversary can already map validators from the P2P layer, the marginal value of
a QKD-data-plane channel must be argued explicitly: it must supply something
Heimbach's attack does not (e.g. per-view advance identification rather than
long-run identity mapping), or the contribution is redundant.

### 6.3 Not found (searched, conceptually as well as by phrase)

No prior work located on: QKD key pre-allocation causing information leakage;
key-relay behaviour revealing consensus state; consensus communication structure
determining resource-demand predictability; or a persistence-based accuracy
ceiling. The persistence/complexity result (§2) appears genuinely unanticipated.

### 6.4 Prior art that constrains the *systems* claim

Stan *et al.* (JOCN 17(3), 2025) and US 11,652,620 B2 already do EWMA-driven
predictive pre-relaying for QKD. Predictive key supply per se is not novel.
Reimplemented and beaten (`bench_baselines.py`), which is the correct handling.

---

## 7. Threat model assessment

The current model is **not stated precisely anywhere in the repository**, and
when made precise it is weaker than the results assume.

### 7.1 What the experiments silently assume

`qkdnet/sidechannel.py` and `research/adversary.py` let the attacker observe the
timing of **every one of the n(n−1)/2 validator pairs**. No realistic adversary
can do this:

- A **validator** observes only its own n−1 pairs.
- An **on-path observer** sees only pairs crossing its vantage point.
- An **external attacker** cannot induce traffic between two other validators at
  all, so it cannot probe those pairs actively.

### 7.2 Measured effect of restricting the vantage

`M-marginal-leak-001` M2, n = 16:

| validators watched | H=2 → L(t+2) | H=3 → L(t+3) |
|---|---|---|
| 16/16 | 0.0625 | 0.0625 |
| 8/16 | 0.3125 | 0.1875 |
| 1/16 | 0.0625 | 0.0625 |

A single-validator vantage yields chance. The attack needs a substantial
fraction of the cluster in view.

### 7.3 Required separation

The repository mixes passive and active adversaries. They must be split:

- **Passive on-path.** Observes request/response timing for pairs crossing its
  link. Cannot choose what to observe. This is the realistic deployment
  adversary and the one the paper should be built on.
- **Active prober.** Injects traffic to elicit timing. Requires the ability to
  send as a validator, i.e. compromise or spoofing. Much stronger assumption;
  the current `repeats_per_pair` experiments implicitly assume it.

### 7.4 Timing precision

Measured separation is 14.2 µs against 1.04 ms (pooled mTLS). Attack accuracy
holds at 1.000 up to 500 µs jitter and degrades past ~1 ms
(`research/adversary.py` A1). That is a genuine robustness result and survives
audit, **conditional on the vantage assumption above**.

---

## 8. Theoretical audit

| Result | Status |
|---|---|
| Lemma 1 (EWMA steady state) | Derived; matches simulation to 1e-9. **Sound.** |
| Theorem 1 (anti-correlation) | Derived. **Sound but narrow** — holds for isolated impulse trains, not for real star demand. The draft is already explicit about this. |
| Theorem 2 (persistence ceiling) | Proof sketch only; equality for α ≥ ½ is verified numerically to 1e-9 across protocols but the sketch is not a full proof. **Needs a complete proof.** |
| Theorem 7 (π closed forms) | Fully derived, verified to 0 error, n = 4…256. **Sound.** |
| Corollary 9 (gain = 1 − π) | Immediate. **Sound.** |
| Theorem 10 (leak = (n−1)/n) | Correct *within the model* where the observer sees all pairs. **Assumption not stated.** Fails under restricted vantage (§7.2). |
| Theorem 11 / 11a (duality) | Algebra correct; **security interpretation refuted** (§3.1). |
| Theorem 5 (greedy ratio) | Standard argument, correctly reproduced, 0/4000 violations. **Sound.** |

**Assumptions never stated in the draft and required by the results:** static
validator set; round-robin or uniformly random leader schedule; every validator
pair is a distinct observable; one authenticated message per pair per phase; no
batching, pipelining or gossip layer; no message aggregation.

Real HotStuff implementations pipeline and batch, which would change the support
and therefore π. **This is unvalidated and is the largest threat to Theorem 7's
external validity.**

---

## 9. Experimental audit

| Issue | Severity | Detail |
|---|---|---|
| Insufficient baseline for leakage | **Critical** | Chance instead of traffic-only. Refutes the headline (§3.1). |
| Attack never run end-to-end | **High** | Model-level only; no packet capture demonstration. |
| Unrealistic attacker vantage | **High** | All-pairs observation assumed (§7.1). |
| Demand model unvalidated | **High** | Protocol models are hand-written; not checked against a real HotStuff/Tendermint trace. |
| No confidence intervals anywhere | Medium | Single-seed runs throughout. `duality.json`, `experiment_log.json` have no repeats. |
| Loopback KME | Medium | Excludes network RTT. Conservative for speedup, but not a deployment number. |
| Simulated QKD | Medium | No hardware; key rates from a decoy-BB84 formula. |
| Parameter selection undocumented | Medium | `hoard_gamma`, `entry_cost = 0.004`, `slack = 2`, `min_prob = 0.05` chosen without sensitivity analysis except where noted. |
| Single topology family | Medium | ring+chords and metro-star only. |
| Nagle artifact | *Resolved* | Found and fixed; 42 ms → 1.04 ms. Documented. |

**Alternative explanations not yet excluded** for the SSLE result (§5.1): that
the leak is an artifact of modelling gossip as a uniform random pair sample; that
degree ranking is unusually favoured by the synthetic support; that a real
attester subnet assignment (which is structured, not random) changes the
baseline.

---

## 10. Most important weaknesses, ranked

1. The headline security claim is refuted by its own corrected baseline.
2. The timing-channel mechanism is prior art in SDN.
3. A cheaper published attack (USENIX Sec '25) may already achieve the goal.
4. The attack is model-level; never demonstrated on the built testbed.
5. Attacker vantage is unrealistic and the results are sensitive to it.
6. Protocol demand models are unvalidated against real implementations.
7. No confidence intervals on any headline number.

---

## 11. Required experiments

Ranked by whether they can sink the paper.

| # | Experiment | Answers | Sinks the paper if it fails? |
|---|---|---|---|
| R1 | End-to-end leader recovery from packet captures on the veth testbed, SSLE configuration | RQ2, RQ3 | **Yes** |
| R2 | Realistic vantage sweep: single validator, on-path fraction, colluding subset — under SSLE | RQ3 | **Yes** |
| R3 | Validate the gossip model against real Ethereum attester-subnet parameters (64 subnets, committee sizes) | §9 alt. explanations | **Yes** |
| R4 | Explicit marginal-value argument vs Heimbach *et al.*: what does per-view advance identification give that long-run mapping does not? | §6.2 | **Yes** |
| R5 | Validate π against a demand trace from a real BFT implementation (batching, pipelining on) | Theorem 7 external validity | Weakens badly |
| R6 | Confidence intervals: ≥20 seeds on every headline number | §9 | No, but reviewers will demand it |
| R7 | Complete proof of Theorem 2 (currently a sketch) | §8 | No |
| R8 | Mitigation cost under the corrected threat model | RQ8 | No |

---

## 12. Proposed research questions

- **RQ1** Does predictive pre-arming improve key availability and round latency
  against a reactive baseline and against published predictive schemes? *(largely
  answered)*
- **RQ2** Is there a measurable observable distinguishing pre-armed from
  non-pre-armed requests on a real data plane? *(answered: 14.2 µs vs 1.04 ms)*
- **RQ3** Under a realistic vantage, can an adversary infer the **next** proposer
  from that observable, **beyond what consensus traffic already reveals**?
  *(open — this is the paper)*
- **RQ4** How does that marginal inference scale with n? *(preliminary: +0.75 at
  n=7 to +0.99 at n=128, model-level only)*
- **RQ5** How robust is it to realistic jitter? *(preliminary: holds to 500 µs)*
- **RQ6** Does it survive topology, key rate, lease duration, workload changes?
  *(open)*
- **RQ7** Which protocol families exhibit it? *(preliminary: those hiding the
  proposer with sub-saturating gossip)*
- **RQ8** What is the performance cost of mitigation? *(preliminary: n/2 map
  footprint; needs redoing under the corrected model)*

---

## 13. Proposed hypotheses

- **H-A.** Support persistence is determined by steady-state message complexity.
  *(supported; independent of the security claim)*
- **H-B.** In protocols whose traffic already addresses the next leader,
  pre-arming has **zero** marginal leakage. *(supported — this is the refutation,
  and it is a publishable negative result)*
- **H-C.** In protocols with secret leader election and sub-saturating gossip,
  pre-arming has **large** marginal leakage. *(preliminary support; requires
  R1–R4)*
- **H-D.** Marginal leakage is a decreasing function of attestation coverage,
  vanishing as coverage → 1. *(preliminary: monotone from +0.88 at 0.25 to
  +0.00 at 1.0)*

H-B and H-C together are a sharper and more honest story than the original
claim: **the leak exists precisely where the protocol went to trouble to hide the
proposer, and nowhere else.**

---

## 14. Proposed baselines

1. Reactive allocation (no prediction).
2. EWMA prediction without protocol knowledge.
3. DT-VQKP (Stan *et al.*) — reimplemented, already present.
4. Structural prediction without pre-arming (control plane only).
5. Structural prediction with pre-arming.
6. Structural prediction with uniform-coverage mitigation.
7. **Traffic-only adversary** — mandatory for every leakage number.
8. **Heimbach-style P2P adversary** — as the alternative-attack baseline.

Items 7 and 8 are the ones whose absence caused the refuted claim.

---

## 15. Proposed ablations

Remove, one at a time, and measure effect on *performance*, *predictability*, and
*leakage* separately:

- prediction; protocol knowledge; leader-schedule knowledge; pre-arming;
  lease persistence; quorum awareness; horizon H; gossip coverage; attacker
  vantage fraction.

The existing schedule-ablation (0.993 → 0.400) is the model for how these should
be reported.

---

## 16. Recommended paper contribution

**Do not write the currently drafted paper.** Its abstract asserts a claim this
audit refutes.

Recommended framing, in order of defensibility:

> **Primary.** Support persistence determines the accuracy ceiling of predictive
> key supply for consensus, and is fixed by the protocol's message complexity
> class. Closed forms, verified across seven protocols and n = 4…256.
>
> **Secondary (systems).** A kernel-resident enforcement plane, with the
> corrections that the instruction budget is not a constraint, the objective is a
> quorum order statistic, and holding key causes starvation.
>
> **Tertiary (security), conditional on R1–R4.** Predictive pre-arming has zero
> marginal leakage in protocols whose traffic already names the next leader, and
> large marginal leakage in exactly those protocols that hide it. The negative
> half is as valuable as the positive half and should be stated first.

---

## 17. Recommended paper structure

1. Introduction — lead with the persistence result, not the side channel.
2. Background: QKD key management, BFT communication patterns, SSLE.
3. System model, with the assumptions of §8 stated explicitly.
4. The persistence ceiling: Theorems 1, 2 (full proof), 7, Corollary 9.
5. Enforcement plane: verifier facts, quorum objective, leases.
6. Evaluation: measured kernel and KME numbers, DT-VQKP comparison, starvation.
7. Security analysis: the traffic-only baseline **first**, the negative result,
   then the SSLE-conditional positive result with vantage sweeps.
8. Mitigation and cost.
9. Limitations — simulation, vantage, unvalidated demand models.
10. Related work — SDN timing channels and Heimbach engaged directly, not buried.

---

## 18. Go / No-Go

The persistence/complexity theory is sound, novel as far as a broad search
reveals, and independently verified. The systems work is real and measured. The
security claim as drafted is refuted, but its corrected form is sharper and the
refutation is itself a contribution.

> ## CONDITIONAL GO

Proceed, on these conditions, ranked:

1. **Withdraw the impossibility claim** and the security reading of the duality
   identity. Non-negotiable — the current abstract is not defensible.
2. **R1** end-to-end leader recovery on the real testbed under SSLE.
3. **R2** realistic vantage sweep.
4. **R3** validate the gossip model against Ethereum's actual subnet structure.
5. **R4** explicit marginal-value argument against Heimbach *et al.*
6. **R5** validate π against a real BFT trace with batching enabled.
7. **R6** confidence intervals throughout.
8. **R7** complete the Theorem 2 proof.

If R1–R4 fail, the security contribution should be dropped entirely and the
paper submitted on the persistence result plus the enforcement plane, which
stand on their own.
