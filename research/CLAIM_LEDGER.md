# Claim ledger

Every important claim in the project, with its type, evidence, strength, and the
wording that is safe to put in a paper. A claim is not established because it
recurs in the notes.

**Types:** THEOREM · EMPIRICAL · IMPLEMENTATION · OBSERVATION · HYPOTHESIS ·
OPEN QUESTION

**Strength:** STRONG (proved or measured with controls) · MODERATE (measured,
narrow scope) · WEAK (single condition, or confounded) · NOT ESTABLISHED

| ID | Claim | Type | Evidence | Experiment / theorem | Strength | Limitation | Safe paper wording |
|---|---|---|---|---|---|---|---|
| T1 | `π(n,m,k) = [k(n−1)+m(m−k)]/[m(n−1)]` for hub-union protocols | THEOREM | Counting proof; brute force `<1e-16`, all (n,m,k) tested | `general_pi.py` G1 | STRONG | Hub-union only; constant m,k; demand-weighted | "For protocols whose per-view support is a union of stars, persistence is given in closed form by …" |
| T2 | `π → k/m` as `n → ∞` | THEOREM | Limit of T1; max dev 0.00195 at n=4096 | `general_pi.py` G3 | STRONG | Asymptotic; not observed empirically | "Asymptotically the persistence equals the surviving-hub fraction." |
| T3 | Chained linear: `π = (n+1)/(2(n−1))` | THEOREM | Corollary of T1, m=2,k=1 | `general_pi.py` G2 | STRONG | — | State as corollary |
| T4 | All-to-all: `π = 1` exactly | THEOREM | Corollary of T1, m=k=n | `general_pi.py` G2 | STRONG | — | State as corollary |
| T5 | EWMA steady state `â(φ)=αBq^(φ−1)/(1−q^n)` | THEOREM | Derived; matches simulation `<1e-9` | `verify_theory.py` T1 | STRONG | Periodic impulse train only | Supporting lemma |
| T6 | EWMA anti-correlated with impulse-train demand for all α, n≥2 | THEOREM | Closed form (2), sign analysis | `verify_theory.py` T1 | STRONG | **Does not extend to real star demand** (see F1) | Use only for the impulse case, explicitly |
| T7 | RWC coverage: three-case theorem under lag-1 dominance | THEOREM | Ranking proof; 13.5k exhaustive + 40k random, 0 violations | `e5_theorem_b.py` | STRONG | RWC class only; strict inequality; see T8 | "For recency-weighted counting predictors satisfying w₁>Σw_s …" |
| T8 | Lag-1 dominance ⟺ `α > ½` for EWMA | THEOREM | `Σ_{s≥2}wₛ = 1−α` | `e5_theorem_b.py` B1 | STRONG | — | State as corollary |
| T9 | Density-greedy ≥ `(1−w_max/C)·OPT` | THEOREM | Standard argument; 0/4000 violations | `verify_theory.py` T4 | STRONG | Not needed for the paper's spine | Cite only if the allocator is discussed |
| E1 | Real BFT support is exactly hub-union (`ρ = 0.0000`) | EMPIRICAL | CometBFT 1,458 views; libhotstuff 79,592 views | E1 | STRONG | Two implementations; loopback | "In both implementations measured, the per-view support was exactly a union of stars." |
| E2 | `π` predicted across n = 4…32, max error 4.22e−4 | EMPIRICAL | 50 runs, 0 failures, predictions locked with hashes pre-run | E2 full | **STRONG** | Research framework, not production; n ≤ 32 | "…predicted the measured persistence of a chained-HotStuff implementation to within 4.2×10⁻⁴ across an eightfold range of n." |
| E3 | `m = 2.0000`, `k = 1.0000`, `ρ = 0.00000` under per-view rotation | EMPIRICAL | Zero variance across 5 runs × 5 n | E2 full | STRONG | One comm module (`clique`) | State with the measured variance |
| E4 | Fixed-leader control gives `π = 1.000000` exactly | EMPIRICAL | 25 runs, error 0.000000 | E2 full | STRONG | — | "The same binary, one flag apart, spans both regimes." |
| E5 | Production-lineage systems sit at `k = m` | EMPIRICAL | CometBFT gossips (m=n−1); libhotstuff fixed leader (m=1); induced faults still 98.9% one proposer | E1 | STRONG | Two systems only | **Must be stated.** "Neither production-lineage implementation measured exhibits per-view rotation." |
| E6 | `π` is a ceiling no key rate lifts | EMPIRICAL | 256× rate sweep changed hit rate by 0.0000 (5/6 points) | E4 Q1 | STRONG | Per-pair pools; simulated | "Additional key generation did not raise the fast-path hit rate." |
| E7 | `1−π` predicts wasted key, slope 0.975, corr +0.983 | EMPIRICAL | 6 operating points, 10 seeds | E4 Q3 | MODERATE | **TTL = 1 only** (slope → 0.091 at TTL=8) | Always qualify with "at unit reservation lifetime". |
| E8 | Fresh-hit ≤ π survives TTL ∈ {1,2,4,8} | EMPIRICAL | max excess +0.0044, no growth in TTL | E4-TTL | STRONG | Per-pair pools | "…holds at every reservation lifetime tested." |
| E9 | Total hit rate exceeds π for TTL>1 (up to +0.7301) | EMPIRICAL | occupancy reaches 3.77× budget K | E4-TTL | STRONG | — | **Must be stated.** Never claim total hit ≤ π. |
| E10 | Fresh-hit ≤ π survives shared-pool contention | EMPIRICAL | max +0.0043 over 48 cells, both admission policies | E6 | STRONG | Single pool; simulated | "…and under a finite shared pool." |
| E11 | Under scarcity `π` is not the binding constraint | EMPIRICAL | π=1.0 predictor still starves 26.6% | E6 | STRONG | One capacity model | "Capacity, not predictability, binds under scarcity." |
| E12 | Burstiness does not reverse the TTL effect | EMPIRICAL | ΔS negative in every arm; TTL* differs 2/14, both ties at zero | E7 | MODERATE | One burst generator | Report as a negative result |
| E13 | Amplification monotonically attenuates the TTL benefit | EMPIRICAL | ΔS −0.2621→−0.0241 over amp 1→8, scarce | E8 | MODERATE | Abstract factor, not a topology | "…in an abstract amplification model." |
| E14 | Real topology flips the sign of the TTL effect | EMPIRICAL | ΔS = +0.0030…+0.0177, all four arms | E8 Model C | MODERATE | Magnitude ≪ E1's; near-saturated regime | "…changes sign, though by a far smaller margin than E1 reported." |
| E15 | Mechanism is arming failure + link specificity, not footprint | EMPIRICAL | footprint falls 0.74→0.59; armFail 9.14→32.58; successful hops 1.504 vs structural 2.300 | E8 | MODERATE | Simulated | State as measured mechanism in this model |
| I1 | XDP instruction count invariant in map capacity (244) | IMPLEMENTATION | 6 loads, 16,384× range, Linux 6.8 | E1 T1 | STRONG | One program | "The verifier's instruction count is a property of the program, not of the map." |
| I2 | Full enforcer verifies at 2,851 instructions | IMPLEMENTATION | bpf_prog_info | E1 | STRONG | — | Factual |
| I3 | Map commit costs 2.98 µs/entry serial, 1.16 µs batched | IMPLEMENTATION | timed syscalls | E1 T2 | STRONG | One host | Factual |
| I4 | XDP fast path 14.2 µs p50; 548 ns in-kernel | IMPLEMENTATION | 3,000 requests, veth, skb mode | E1 T3 | STRONG | Loopback veth, skb not native | "…on a loopback veth in skb mode." |
| I5 | ETSI GS QKD 014 fetch 1.04–9.06 ms by connection reuse | IMPLEMENTATION | our KME, mutual TLS, 400 req/config | `kme_bench` | MODERATE | Our implementation, loopback, excludes RTT | "…against a compliant KME implementation on loopback; a conservative lower bound." |
| O1 | Schedule-ablation drops coverage below the baseline (0.400 vs 0.593) | OBSERVATION | exp1 | E-early | MODERATE | Simulated | Use as the control that isolates the structural gain |
| O2 | A periodicity learner beats π on deterministic schedules (1.0000) | OBSERVATION | predictor zoo | `predictor_zoo.py` | STRONG | — | **Must be stated** as the scope limit on T7 |
| O3 | Pre-arming can increase starvation vs reactive (up to 33%) | OBSERVATION | E1 sim, shared link pools, bursty | E1 | WEAK | Not reproduced quantitatively anywhere since | Report as an observation in the original model only |
| H1 | Predictive pre-arming leaks the leader schedule | HYPOTHESIS | Refuted at H=1 (marginal +0.0000 vs traffic baseline) | `marginal_leak.py` | NOT ESTABLISHED | — | **Do not claim.** See FALSIFIED_CLAIMS. |
| H2 | SSLE-conditional leakage (+0.88 marginal) | HYPOTHESIS | Model-level only; R1–R4 not done | `ssle_leak.py` | NOT ESTABLISHED | No packet-level demo, no vantage model | **Omit from the paper.** |
| Q1 | Does the result transfer to production systems in the k<m regime? | OPEN QUESTION | E1 says no system measured is in it | — | — | — | Disclose as a limitation |
| Q2 | Quantitative reconciliation with E1's 33% | OPEN QUESTION | E8 reproduces direction only | — | — | — | Disclose |
| Q3 | Does π bound learned predictors under low-entropy schedules? | OPEN QUESTION | O2 says no | — | — | — | Disclose as scope |
