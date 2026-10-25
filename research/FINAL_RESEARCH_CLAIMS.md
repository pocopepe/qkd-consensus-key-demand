# Final research claims

Submission-readiness reconstruction of what the completed program actually
establishes. Written adversarially; claims that the evidence does not carry are
marked as such rather than softened.

---

## 1. One-sentence contribution

> The predictability of a consensus protocol's per-view key demand is fixed by
> the protocol's communication specification and is computable in closed form
> before deployment as `π(n,m,k) = [k(n−1)+m(m−k)]/[m(n−1)]`; no
> recency-weighted predictor can exceed it; and the formula predicts a real
> chained-HotStuff implementation across an eightfold range of validator counts
> to within 4.2×10⁻⁴.

That sentence is what survives hostile review. Everything about QKD key supply,
TTL, and shared pools is application evidence, not the contribution.

---

## 2. Core research question

**As answered:**

> Can the predictability limit of a distributed protocol's per-view resource
> demand be derived from its communication specification, and does that limit
> bound what any history-based predictor can achieve?

**Evolution.** The program began as *"predictive eBPF key pre-arming for
QKD-secured blockchain consensus"* — a systems proposal. Three things moved it:
EWMA-driven predictive pre-relaying turned out to be published prior art
(Stan et al., JOCN 2025); the eBPF instruction budget turned out not to be a
real constraint (measured, 244 instructions invariant over a 16,384× map range);
and the forecasting advantage turned out to come from protocol structure rather
than from the estimator. What remained was a question about predictability
limits, which is what the program then answered. The QKD enforcement layer
became the application domain, not the claim.

---

## 3. Contributions

### C1 — Mathematical: the structural persistence formula

**Claim.** For a *hub-union* protocol — one whose per-view support is a union of
`m` stars, of which `k` persist to the next view — the demand-weighted support
persistence is exactly

    π(n,m,k) = [k(n−1) + m(m−k)] / [m(n−1)],   and   π → k/m as n → ∞.

**Evidence.** Derived by counting (`research/general_pi.py`), verified against
brute-force simulation to `< 1e-16` for all `n ∈ {16,32,64} × m ∈ {2,3,5,8} ×
k ∈ {0..m}`. Corollaries reproduce the protocol-specific cases: all-to-all
(`m=k=n`) → 1; chained linear (`m=2,k=1`) → `(n+1)/(2(n−1))`; pipelined depth d
(`m=d+1,k=d`) → `d/(d+1)`.

**Assumptions, all required.** Static validator set; support is exactly a union
of stars; `m` and `k` constant across views; one demand unit per hub-incident
message (a pair incident to two hubs carries two); `n > m`; persistence measured
**demand-weighted**, not support-weighted.

**Limitations.** Explicitly out of scope for clique-support protocols
(committee sortition): the formula predicts 0.45 where measurement gives 0.0442.
Recorded as a scope restriction, not patched.

### C2 — Predictor coverage bound (Theorem B)

**Claim.** Define a *recency-weighted counting* (RWC) predictor by
`score_t(p) = Σ_{s<t} w_{t−s}·1[p ∈ S(s)]` with `w ≥ 0` independent of `p` and
`t`. If `w` satisfies **lag-1 dominance**, `w₁ > Σ_{s≥2} wₛ`, then with
`K = |S(t)|`:

    |S(t−1)| = K  ⟹  cov = π  exactly
    |S(t−1)| > K  ⟹  cov ≤ π
    |S(t−1)| < K  ⟹  cov ≥ π

**Evidence.** Proved by a ranking argument; 13,500 exhaustive small cases and
40,000 randomised instances with zero violations (`research/e5_theorem_b.py`,
7/7 checks).

**Corollaries.** For EWMA `Σ_{s≥2} wₛ = 1−α`, so dominance is exactly `α > ½`.
Uniform frequency weighting over a window `T > 2` fails dominance, which is why
measured `freq` coverage is 0.194 against `π = 0.552`.

**Scope, and it is a real limit.** The bound constrains RWC predictors only.
A periodicity-detecting table learner reaches coverage **1.0000** against
`π = 0.5517` on a round-robin schedule (`research/predictor_zoo.py`). The bound
is therefore about a predictor *class*, not about prediction in general, and it
is operationally meaningful only when the leader schedule has positive
conditional entropy given demand history — VRF, shuffled-epoch and
stake-weighted schedules, where no tested learner beat `π`.

### C3 — Real-system validation

**Claim.** The hub-union abstraction and Theorem A describe real BFT
implementations exactly, and the formula's *non-constant* `n`-dependence is
confirmed.

**Evidence.**
- **E1**: CometBFT v0.40.0 (`dc83065`) and libhotstuff, instrumented at the
  logical consensus-message layer. `ρ = 0.0000` (support is exactly a union of
  stars) over 79,592 + 1,458 views; prediction error ≤ 0.0013. **But both sit at
  `k = m`, where `π = 1` and the `m(m−k)` term vanishes.**
- **E2**: relab/hotstuff `3179c6e6`, chained HotStuff + clique + round-robin, 50
  runs, 0 failures, predictions locked with script hashes before the first run.
  `m = 2.0000` (zero variance), `k = 1.0000`, `ρ = 0.00000`, and

  | n | 4 | 7 | 10 | 16 | 32 |
  |---|---|---|---|---|---|
  | π theory | 0.833333 | 0.666667 | 0.611111 | 0.566667 | 0.532258 |
  | π measured | 0.833333 | 0.666657 | 0.611085 | 0.566645 | 0.531836 |

  **max error 0.000422.** Fixed-leader control gives `π = 1.000000` exactly at
  every `n`, so one binary and one pipeline span both regimes.

**Limitations.** relab/hotstuff is a **research framework**, not a production
system. E1 established that the two production-lineage systems measured do
**not** operate in the non-degenerate regime. Loopback networking; one
communication module; `n ≤ 32`; the asymptote `π → ½` is approached, not
observed.

### C4 — Operational consequence

**Claim.** `π` is a hard ceiling on prediction-attributable fast-path hit rate
that additional key generation does not lift.

**Evidence (E4).** Sweeping key-generation rate over a **256× range** changed
hit rate by **0.0000** in five of six operating points. `1−π` predicts wasted
key at `corr = +0.983`, slope 0.975 — **at TTL = 1 only** (E4-TTL: slope falls
to 0.091 at TTL = 8).

**Explicitly not established.** The hypothesis that *required key-generation
rate* scales with `1−π` is **not supported**: the ratio is non-monotone
(1.017, 1.696, 1.282, 1.007), `corr = +0.36` on four points.

**The distinction that must never be blurred.** `π` bounds **fresh** hits —
those served by a reservation created in the current view, i.e. actual
predictions. **Total** fast-path hit rate is not bounded by `π`: with TTL = 8 it
exceeds `π` by up to **+0.7301**, because live reservations reach **3.77×** the
per-view budget. That is budget inflation, not improved prediction.

### C5 — Shared resources, TTL, and topology

**Claim (E6).** Under a finite shared pool, the fresh-hit ceiling survives
(`max(fresh − π) = +0.0043` over 48 cells, all regimes, both admission
policies), but `π` **stops being the binding constraint** under scarcity: at
`π = 1.0` a never-wrong predictor still starves **26.6%** of requests.

**Claim (E7).** Burstiness does **not** explain the E1/E6 TTL discrepancy.
`TTL*` differs in 2 of 14 comparisons, both among ties at zero starvation, and
`ΔS` is negative in every arm.

**Claim (E8).** Multi-hop reservation amplification does change the TTL
trade-off, monotonically: `ΔS = −0.2621 → −0.1278 → −0.0588 → −0.0241` as the
factor grows 1 → 8, and under E1's actual relay mechanism it **flips sign**
(+0.0030 … +0.0177). The regression control at amp = 1 reproduces E7 to
**0.0000**.

**Mechanism, corrected.** Amplification does **not** raise occupied resource —
achieved footprint *falls* (0.74 → 0.59 D). It raises **arming failure**
(9.14 → 32.58 per view) and cuts live reservations 9×. The sign flip
additionally requires **link specificity**: successful reservations average
**1.504 hops** against a structural mean of **2.300**, so long paths are shut
out — impossible in a fungible pool.

**Limitations, severe.** Magnitude is not reproduced (+0.003 against E1's 33%).
And per §Related-Work audit, **path-crossing starvation from key reservation is
already documented in the QKD literature**, which substantially reduces C5's
novelty; what is new is only its quantitative coupling to `π` and TTL.
