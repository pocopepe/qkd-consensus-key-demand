# Research direction

Decision document. Follows the CONDITIONAL GO audit in `research/audit.md`. Four
new experiments were run to challenge the surviving contribution; two of them
partly falsified it. Nothing here is a paper draft.

---

## 1. Executive verdict

The persistence result is **real, now properly generalized, and the
generalization is the actual contribution** — but two of the claims built on it
in `theory.md` are wrong, and its practical scope is far narrower than the
repository implies.

What changed in this round:

- **The general formula was found.** `π(n,m,k) = [k(n−1) + m(m−k)] / [m(n−1)]`,
  with `π → k/m`. Every protocol-specific formula is a corollary. Verified to
  machine precision (`G-general-pi-001`). This removes the "HotStuff has this
  formula and PBFT has that one" objection.
- **The ceiling does not bind all history-based predictors.** On a round-robin
  schedule a trivial periodic table learner reaches coverage **1.0000** against
  `π = 0.5517` (`P-predictor-zoo-001`). The claim that beating `π` requires
  protocol knowledge is **false for deterministic schedules**.
- **Practical scope is narrow.** Pipelining depth 5 raises `π` to 0.90 (gain
  0.43 → 0.10). One-time-pad payloads at batch 256 raise `π` to 0.9966 (gain
  0.0034). The result applies to tag-only authentication with shallow pipelines
  (`V-realism-001`).
- **Prior-art threat on the grand framing.** Temporal-network predictability
  limits are an existing literature.

> **CONDITIONAL GO on a reframed, narrower contribution.** Do not pursue the
> grand "consensus structure limits proactive allocation" framing. Do not pursue
> the security framing yet.

---

## 2. Current strongest contribution

Not "QKD key demand has a forecasting ceiling". That is one instance of:

> **The predictability limit of a consensus workload's resource demand is
> computable in closed form from the protocol's communication specification,
> before any trace exists, as the surviving-hub fraction `k/m`; and whether that
> limit can be reached without protocol knowledge is decided by the conditional
> entropy of the leader schedule given demand history.**

Two halves, both needed. The first is the formula. The second is what the
`P-predictor-zoo-001` experiment forced.

---

## 3. Formal system model

**Validators.** `V = {1,…,n}`, static. `E = {{u,v} : u ≠ v}`, `|E| = n(n−1)/2`.

**Views.** Discrete `t = 0,1,2,…`. Leader schedule `L : ℕ → V`.

**Demand.** `d_t : E → ℝ₊`, the pairwise key consumed in view `t`. Support
`S(t) = {p ∈ E : d_t(p) > 0}`.

**Hub-union protocols.** A protocol is *hub-union* if there is a hub set
`R(t) ⊆ V`, `|R(t)| = m`, with

    S(t) = ⋃_{h ∈ R(t)} star(h),    star(h) = {{h,u} : u ≠ h},

and `d_t` assigns one unit per hub-incident message, so a pair incident to two
hubs carries two units. Let `k = |R(t) ∩ R(t+1)|`, assumed constant.

*In scope:* PBFT, Tendermint, chained HotStuff, HotStuff-2, Simplex, Narwhal,
pipelined and aggregation-tree variants.
*Out of scope:* committee sortition, whose support is a clique on the committee,
not a union of stars. Measured `π = 0.0442` vs hub-union prediction `0.45`
(`G-general-pi-001` G4). Stated as a restriction, not patched.

**Support persistence.**

    π := lim_{T→∞} (1/T) Σ_t [ Σ_{p ∈ S(t−1)} d_t(p) ] / [ Σ_{p} d_t(p) ]

Demand-weighted, not support-weighted. This distinction is not cosmetic —
see §6.2.

**Forecaster classes.**

- *Recency-weighted counting (RWC).* `score_t(p) = Σ_{s<t} w_{t−s}·1[p ∈ S(s)]`
  with `w` non-negative and non-increasing, **independent of `p` and of `t`**.
  Contains EWMA (`w` geometric), last-observation (`w = δ₁`), frequency
  (`w` uniform).
- *History-based.* Any function of `{d_s}_{s<t}`. Contains RWC, plus Markov
  tables and periodicity detectors.
- *Structural.* Additionally reads `L(t), …, L(t+H)`.

**Coverage.** For budget `K`, `cov_t = Σ_{p ∈ top-K(score_t)} d_t(p) / Σ_p d_t(p)`.
Throughout, `K = |S(t)|`, so the budget is never the binding factor.

**Structural gain.** `Δ := cov(structural) − max_{RWC} cov`.

---

## 4. Formal theorem candidate

> **Theorem A (Hub persistence).** For a hub-union protocol with `m` hubs per
> view and `k` surviving hubs,
>
>     π(n,m,k) = [k(n−1) + m(m−k)] / [m(n−1)],     and     lim_{n→∞} π = k/m.
>
> *Proof.* A view carries `m(n−1)` hub-incident messages. For `h ∈ R(t)∩R(t−1)`
> all `n−1` incident edges lie in `S(t−1)`. For `h ∈ R(t)\R(t−1)`, edge `{h,j}`
> lies in `S(t−1)` iff `j ∈ R(t−1)`, giving `m` such edges. Sum and divide. ∎
>
> Verified against brute-force simulation to `< 1e-16` for all
> `n ∈ {16,32,64} × m ∈ {2,3,5,8} × k ∈ {0..m}`.

> **Corollary A.1.** All-to-all (`m = k = n`): `π = 1`.
> **Corollary A.2.** Chained linear (`m=2, k=1`): `π = (n+1)/(2(n−1)) → 1/2`.
> **Corollary A.3.** Single hub, no carry-over (`m=1,k=0`): `π = 1/(n−1)`.
> **Corollary A.4.** Pipelined depth `d` (`m=d+1, k=d`): `π → d/(d+1)`.

> **Theorem B (RWC ceiling) — settled by E5, and the original conjecture was
> wrong.** The recorded conjecture was *"for every RWC predictor, cov ≤ π, with
> equality for EWMA with α ≥ 1/2"*. Both halves needed correcting.
>
> The operative condition is not a property of EWMA but of the weight vector:
>
>     LAG-1 DOMINANCE:   w_1 > sum_{s>=2} w_s
>
> Under it, every member of `S(t-1)` outranks every non-member (a member scores
> at least `w_1`; a non-member at most `sum_{s>=2} w_s`). Hence, with `K = |S(t)|`:
>
>     |S(t-1)| = K  =>  top-K = S(t-1)          =>  cov = pi  EXACTLY
>     |S(t-1)| > K  =>  top-K subset of S(t-1)  =>  cov <= pi
>     |S(t-1)| < K  =>  top-K superset of S(t-1) =>  cov >= pi
>
> So in the constant-support case it is an **equality**, not an inequality; and
> when the support **grows** the inequality runs the other way, refuting the
> conjecture as stated. Explicit counterexample: `S(t-2)={a,b,c}`, `S(t-1)={a}`,
> `S(t)={a,b,c}` gives `π = 1/3` and `cov = 1`.
>
> For EWMA, `sum_{s>=2} w_s = 1 - alpha`, so dominance is exactly `alpha > 1/2`
> — which is why the empirical threshold sat there. Uniform frequency weighting
> fails dominance for any window longer than two, which is why `freq` scored far
> *below* π rather than at it.
>
> *Status: proved, plus 13,500 exhaustive and 40,000 randomised instances with
> zero violations (`research/e5_theorem_b.py`, 7/7).* Every protocol in this
> repository has constant support size, which is why the equality was observed
> everywhere and the failure mode never appeared.

> **Observation C (Entropy condition).** Conjecture B does **not** extend to
> history-based predictors. On a deterministic schedule a periodicity detector
> reaches `cov = 1.0` while `π = 0.55`. Structural knowledge is necessary only
> when the schedule has positive conditional entropy given demand history.

Theorem A is the paper's theorem. Conjecture B is the bridge to practice.
Observation C is the scope limit and must be stated, not buried.

---

## 5. Scope and assumptions

Required for Theorem A:

1. Static validator set.
2. Hub-union support (excludes sortition).
3. Constant `m` and `k`.
4. One demand unit per hub-incident message — i.e. **tag-only authentication**.
5. No message aggregation changing the support graph *(relaxed in §9)*.
6. Demand-weighted persistence.

Required additionally for the practical claim (structural forecasting is worth
building):

7. Schedule with positive conditional entropy given history (Observation C).
8. `k/m` bounded away from 1 — shallow pipelines, low gossip degree.
9. Key consumed per message, not per byte.

**Assumptions 7–9 are the ones that decide whether the work matters, and none of
them is stated anywhere in the current repository.**

---

## 6. Counterexamples

### 6.1 Deterministic schedules break the ceiling (`P-predictor-zoo-001`)

| schedule | π | ewma | last | freq | markov1 | periodic |
|---|---|---|---|---|---|---|
| round-robin, n=16 | 0.5517 | 0.5517 | 0.5517 | 0.1940 | 0.9741 | **1.0000** |
| round-robin, n=32 | 0.5246 | 0.5246 | 0.5246 | 0.0891 | 0.9857 | **1.0000** |
| shuffled-epoch, n=16 | 0.5546 | 0.5559 | 0.5544 | 0.1858 | 0.3949 | 0.2562 |
| VRF, n=16 | 0.6068 | 0.6158 | 0.6086 | 0.2544 | 0.4495 | 0.2367 |
| stake-weighted, n=16 | 0.6427 | 0.6606 | 0.6435 | 0.4963 | 0.5394 | 0.3037 |

Theorem A is untouched (`π` is a property of the workload). **Conjecture B's
practical reading is falsified for deterministic schedules.** On the three
stochastic schedules no history-based predictor reaches `π`, so the reading
survives exactly where the schedule is not learnable.

*Better theorem suggested:* the operative quantity is `H(L(t+1) | d_{<t})`, not
"protocol structure". The structural forecaster's contribution is *information*,
not *modelling*.

### 6.2 The batching control failed, and the failure is informative

Batching was expected to leave `π` unchanged. It does not:

| key model | proposal:vote weight | π | gain |
|---|---|---|---|
| tag-only (Wegman–Carter) | 1:1 | 0.5667 | 0.4333 |
| OTP payload, batch 16 | 16:1 | 0.9490 | 0.0510 |
| OTP payload, batch 256 | 256:1 | 0.9966 | **0.0034** |

`π` is demand-weighted, so concentrating demand on the proposal star — which is
exactly the star that carried over — drives `π → 1`. Under OTP-encrypted
payloads the entire contribution evaporates.

This is survivable because tag-only authentication is the sensible QKD design
(OTP consumes key equal to message length, which QKD rates cannot sustain), but
it must become an explicit assumption.

### 6.3 Pipelining and gossip erode the gain (`V-realism-001`, n=16)

| configuration | π | gain |
|---|---|---|
| ideal chained | 0.5667 | 0.4333 |
| pipelined depth 2 | 0.7333 | 0.2667 |
| pipelined depth 3 | 0.8167 | 0.1833 |
| pipelined depth 5 | 0.9000 | **0.1000** |
| aggregation tree, fanout 4 | 0.4894 | 0.5106 |
| vote gossip, degree 2 | 0.3270 | 0.6730 |
| vote gossip, degree 8 | 0.8052 | 0.1948 |

Pipelining is exactly Corollary A.4 (`π → d/(d+1)`), so this is the theorem
predicting its own erosion — a point in its favour scientifically and against it
practically. Aggregation trees *lower* `π` (interior nodes rotate), which helps.

---

## 7. Generalization opportunities

**Taken:** hub-union → `k/m`. This is the main advance of this round.

**Available but not taken:**

- *Clique-union protocols* (sortition). Needs a second formula; preliminary
  `P(edge repeats) ≈ (c/n)²`. Would complete the taxonomy.
- *Weighted hubs.* Real protocols have hubs of unequal weight (proposal vs
  vote). A weighted `π` would subsume §6.2 rather than treating it as a caveat.
- *Entropy formulation.* Replace "structural knowledge" with
  `H(L(t+1) | d_{<t})` and state the gain as a function of it. This is the
  cleanest version and is what Observation C is pointing at.

**Prior-art constraint on generalizing further:** temporal-network predictability
limits already exist as a literature (*Predictability of real temporal networks*,
Nat. Sci. Rev. 2020, and the temporal link-prediction line). Any framing as
"predictability limits for temporal graphs" collides with it directly. The
defensible distinction is that Theorem A is **derived from a protocol
specification rather than measured from a trace** — computable before deployment,
with no data. That distinction must be made explicitly and early.

---

## 8. QKD relevance

Honest answer: **the theorem is necessary but not sufficient to justify the
system.** It tells an operator the ceiling before they build anything, which is
genuinely useful. It does not by itself show the ceiling matters.

What the repository already measures for the operational chain:

| quantity | ideal chained | pipelined ×5 | OTP batch 256 |
|---|---|---|---|
| `π` | 0.567 | 0.900 | 0.997 |
| gain `1−π` | 0.433 | 0.100 | 0.003 |
| best measured hit-rate advantage | 0.588 vs 0.004 | — | — |
| measured p50 | 0.014 ms vs 5.542 ms | — | — |

The engineering decision the theorem changes: **whether to implement a
schedule-aware control plane at all.** At `k/m ≥ 0.8` the answer is no —
last-observation is within 10% of the ceiling and costs nothing. That is a real
decision rule and it is the strongest practical statement available.

Not yet measured, and needed: how `1−π` translates into key-material waste and
required over-provisioning (§12, E4).

---

## 9. Real-system validity

Unresolved and the largest remaining threat. `V-realism-001` uses *models* of
pipelining, aggregation and gossip, not traces. Nobody has checked `m` and `k`
against a real implementation.

Concretely needed: instrument HotStuff-rs / CometBFT / a Narwhal implementation,
extract the per-view message graph, compute `m`, `k`, `π` empirically, and
compare against Theorem A. If real HotStuff runs at pipeline depth 3+, the
measured gain is ~0.18 and the practical case is weak — which must then be
reported.

---

## 10. Security contribution assessment

**Omit from this paper.**

The previous audit refuted the general claim (marginal leakage `+0.0000` at
H=1). The surviving SSLE-conditional result (`S-ssle-leak-001`, marginal
`+0.88`) is promising but rests on R1–R4, none of which are done: no
packet-level demonstration, no realistic vantage model, no validation of the
gossip model against Ethereum's subnet structure, no marginal-value argument
against Heimbach *et al.* (USENIX Sec '25).

It is a separate paper if it works. Attaching it here doubles the attack surface
and invites the SDN-timing-channel prior art into a paper that otherwise does not
need to survive it.

---

## 11. Contribution ranking

| | Contribution | Novelty | Depth | Evidence | Practical | Attack surface | Work left |
|---|---|---|---|---|---|---|---|
| **C2** | Protocol structure → predictability limit, closed form `k/m` | High | Medium-high | Strong (exact) | Medium | Temporal-graph prior art | Small |
| **C1** | Persistence ceiling for RWC predictors | Medium | Medium | **Proved** (E5) + 53.5k instances | Medium | Scope condition must be stated | None |
| **C4** | XDP enforcement plane + corrected resource model | Medium | Low-medium | Strong (measured) | High | "engineering not research" | None |
| **C5** | Predictive allocation ↔ starvation trade-off | Medium-high | Low | Strong (21.9k rounds) | High | Simulation-only | CIs |
| **C3** | QKD implications | Low | Low | **Strong (E4)** | High | — | None |
| **C6** | Security under SSLE | High if true | Medium | **Insufficient** | Unknown | Very large | R1–R4 |
| **C7** | Mitigation | Low | Low | Refuted baseline | Low | — | Redo |

**Primary:** C2, with C1 as its operational bridge.
**Secondary:** C4.
**Supporting:** C5, C3.
**Omitted:** C6, C7.

Venue implication: this is now a **networking/systems** paper — INFOCOM, ICNP,
CoNEXT, IEEE/ACM ToN — not a security paper.

---

## 12. Decisive experiments

Six. Each distinguishes competing explanations or can falsify the contribution.

### E1 — Real-implementation hub structure *(highest priority)*
- **Hypothesis:** real HotStuff/Tendermint per-view message graphs are hub-union
  with `m`,`k` matching Theorem A.
- **IV:** implementation (HotStuff-rs, CometBFT, Narwhal), pipeline depth.
- **DV:** measured `m`, `k`, `π`; predicted vs measured `π`.
- **Baseline:** the idealised model already in the repo.
- **Expected:** `π` within ±0.05 of Theorem A at matched `m`,`k`.
- **Falsifies if:** real graphs are not hub-union, or error > 0.15.
- **Reps:** 3 implementations × 5 runs × 1000 views.
- **Stats:** mean ± 95% CI; per-implementation.
- **Output:** Table — predicted vs measured `π`. **The paper's credibility table.**

### E2 — Predictor-class boundary
- **Hypothesis:** `cov ≤ π` for RWC predictors; history-based predictors exceed
  `π` iff `H(L(t+1)|d_{<t})` is low.
- **IV:** predictor class × schedule entropy (round-robin → shuffled → VRF →
  stake-weighted).
- **DV:** coverage, and measured conditional entropy.
- **Baseline:** last-observation (attains `π`).
- **Expected:** monotone collapse of the learner advantage as entropy rises.
- **Falsifies if:** a history-based predictor beats `π` at high entropy.
- **Reps:** 20 seeds × 4 schedules × 6 predictors.
- **Stats:** CI on coverage; regression of advantage on entropy.
- **Output:** Figure — learner advantage vs schedule entropy.

### E3 — `k/m` sweep against the closed form
- **Hypothesis:** Theorem A holds across the whole `(m,k)` lattice.
- **IV:** `n ∈ {16,64,256}`, `m ∈ {1..8}`, `k ∈ {0..m}`.
- **DV:** simulated `π` vs formula.
- **Expected:** error < 1e-12 *(already obtained; needs repetition with seeds)*.
- **Falsifies if:** systematic deviation for any `(m,k)`.
- **Reps:** 20 seeds each.
- **Output:** Figure — `π` vs `k/m` collapsing onto one line across `n`.

### E4 — Operational translation
- **Hypothesis:** `1−π` predicts key over-provisioning needed for a target
  hit rate.
- **IV:** `π` (via `m`,`k`), target hit rate.
- **DV:** required key-generation rate; wasted reserved key; p50/p99 latency.
- **Baseline:** reactive; last-observation.
- **Expected:** required over-provisioning scales with `1−π`.
- **Falsifies if:** no relationship — which would make the theorem
  operationally irrelevant and should be reported as such.
- **Reps:** 20 seeds × 6 `(m,k)` points.
- **Output:** Figure — over-provisioning vs `1−π`. **The relevance figure.**

### E5 — Proof or counterexample for Conjecture B — **DONE**
- **Result: the conjecture is refuted as stated and replaced by Theorem B
  above.** Lag-1 dominance is the operative condition; under constant support
  the relation is an equality, and under growing support the inequality
  reverses. Counterexample documented.
- Evidence: `research/e5_theorem_b.py` (7/7), `results/E5-theorem-b-001.json`.

### E6 — Confidence intervals on existing headline numbers
- Every number currently in `README.md`, `theory.md`, `evaluation.md` is
  single-seed. Re-run ≥20 seeds; report mean ± 95% CI.
- **Output:** revised tables throughout. Cheap, and reviewers will demand it.

---

## 13. Proposed research question

> **Can the predictability limit of a distributed protocol's resource demand be
> computed from its communication specification, and does that limit determine
> whether proactive allocation is worth implementing?**

Secondary:

- **SQ1** What structural property of the per-view message graph determines the
  limit?
- **SQ2** Which predictor classes are bound by it, and what additional
  information is needed to exceed it?
- **SQ3** How much does the limit move under real implementation behaviour —
  pipelining, aggregation, gossip, batching?
- **SQ4** What does the limit imply for QKD key provisioning?

---

## 14. Proposed hypothesis

> **H.** For hub-union consensus protocols, demand-weighted support persistence
> is `π(n,m,k) = [k(n−1)+m(m−k)]/[m(n−1)] → k/m`; recency-weighted counting
> predictors cannot exceed `π`; and exceeding it requires leader-schedule
> information that is recoverable from demand history only when the schedule's
> conditional entropy is low.

Falsifiable at three points: the formula (E1, E3), the ceiling (E2, E5), the
entropy condition (E2).

---

## 15. Proposed paper contributions

1. **Theorem A** and its corollaries — a predictability limit computed from a
   protocol specification, not measured from a trace.
2. **The predictor-class boundary** — `π` binds recency-weighted counting;
   history-based learners exceed it exactly when the schedule is learnable.
3. **An engineering decision rule** — implement schedule-aware prediction only
   when `k/m` is bounded away from 1 and the schedule has entropy; with measured
   erosion under pipelining, gossip and OTP payloads.
4. **A measured enforcement plane** — with the corrected resource model
   (instruction count invariant; update bandwidth binds; quorum order statistic).
5. **The starvation trade-off** — pre-arming raises starvation up to 33%; the
   fix is lease duration, not selection.

---

## 16. Proposed paper outline

1. Introduction — a limit you can compute before you build.
2. Background: BFT communication patterns; QKD key management; predictive
   allocation prior art (Stan *et al.*); temporal-network predictability, and
   why this differs.
3. Model and definitions (§3 here), assumptions stated up front.
4. Theorem A, corollaries, the `k/m` collapse.
5. Predictor classes: Conjecture B, Observation C, the entropy condition.
6. Erosion under real mechanisms: pipelining, aggregation, gossip, OTP.
7. Enforcement plane and corrected resource model.
8. Evaluation: E1 credibility table, E3 collapse figure, E4 relevance figure,
   DT-VQKP comparison, starvation.
9. Decision rule and limitations.
10. Related work.

---

## 17. Reviewer objections, and the answer

| # | Objection | Answer |
|---|---|---|
| 1 | "Predictability limits for temporal graphs already exist." | Ours is derived from a specification, computable with zero data, before deployment. Theirs is measured from a trace. Cite directly, position early. |
| 2 | "`π → k/m` is obvious once stated." | Only after the hub-union abstraction is chosen. The `m(m−k)` correction term is not obvious, and the demand-weighting subtlety (§6.2) inverts the batching intuition. |
| 3 | "The ceiling is trivially beaten by a table lookup." | Conceded and measured (E2). It is a stated scope condition, not a hidden flaw — and the entropy condition is a contribution. |
| 4 | "It's all simulation." | E1 answers with real implementation traces. This is the objection to fear. |
| 5 | "Real HotStuff pipelines, so the gain is 0.10." | Reported, not hidden. The decision rule turns it into a contribution: our own theorem says when not to build the system. |
| 6 | "Why QKD? Any scarce resource has this." | True, and stated. QKD is the instantiation where the resource is physically rate-limited, which makes the limit binding rather than academic. |
| 7 | "Single seed throughout." | E6. |
| 8 | "Conjecture B is unproved." | E5: prove it or publish the counterexample. |

---

## 18. Final recommendation

> ## CONDITIONAL GO — reframed

Proceed on **C2 primary, C4 secondary**, at a networking venue. Drop the security
contribution from this paper and the grand "consensus limits proactive
allocation" framing.

Required before drafting, in order:

1. ~~**E1** — real implementation traces~~ **done: partially supported (E1),
   then strongly supported in the non-degenerate regime (E2 full matrix).**
2. ~~**E5** — prove Conjecture B~~ **done: refuted and replaced by Theorem B.**
3. ~~**E4** — operational translation~~ **done: operationally relevant.** pi is
   a hard ceiling no key budget lifts (max change 0.0161 over a 256x rate
   sweep); 1-pi predicts wasted key at corr +0.983, slope 0.975. The stated
   hypothesis about required *rate* was not supported and is recorded as such.
4. **E2** — predictor-class boundary with entropy regression.
5. **E3, E6** — repetitions and confidence intervals.

Retire from `theory.md`: the impossibility corollary, the security reading of
the duality identity, and the claim that structural knowledge is necessary
(true only under Observation C's entropy condition).

If E1 shows real implementations run at `k/m ≥ 0.8`, the honest paper is a
negative result — *predictive key supply is not worth building for pipelined
BFT, and here is the closed form that tells you so in advance*. That is still
publishable, and it is still useful.
