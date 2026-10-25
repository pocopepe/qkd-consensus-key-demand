# Related-work audit

Searched: IEEE Xplore, ACM DL, arXiv, USENIX, and QKD/BFT literature, August
2026. Conceptual equivalents were searched for, not only exact phrases. Absence
of an identical paper is **not** treated as novelty.

---

## A. Direct prior art on predictive / proactive QKD key supply

| Work | Year / venue | What it does | What it does not do | Overlap | Reviewer objection |
|---|---|---|---|---|---|
| **Stan, Verchere, Vegas Olmos, Tafur Monroy, Rommel — "Dynamic-threshold-based pre-relaying for enhanced key allocation in quantum-secured networks"** | JOCN 17(3), 2025 | EWMA prediction of next-interval key demand; dynamic upper/lower thresholds on virtual key pools; pre-relays **ahead of requests** | No consensus-specific structure; no predictability bound; no closed form | **High** on the predictive-key-supply idea | "Predictive QKD key pre-positioning is already published." **Must be cited and beaten, which E-baselines does (0.588 vs 0.004 hit rate).** |
| **US 11,652,620 B2** (evolutionQ) | 2023 | Proactive buffering of surplus QKD key at link endpoints; forecast-driven relay routing via multi-commodity flow LP | No prediction ceiling; no consensus model | High on "proactive buffering" | Patent prior art on the mechanism |
| **US 11,652,619 B2** (evolutionQ) | 2023 | Optimising routing of QKD key material | — | Moderate | — |
| **"Exploring Key Pre-provisioning in Quantum Key Distribution Networks"** | IEEE, 2025 (Xplore 11268613) | Key pre-provisioning via Quantum Key Pools; variants that reduce demand blocking without increasing supply delay | Could not retrieve full text (fetch failed). Based on abstract: no consensus structure, no bound | **High on pre-provisioning** | "Pre-provisioning in QKD networks is an established line." **Must be cited; full text must be obtained before submission.** |

**Assessment.** Predictive/proactive QKD key supply is *not novel*. Any framing
that leads with it will be rejected. The correct handling — already done in the
repository — is to reimplement DT-VQKP faithfully and use it as the baseline.

---

## B. Direct prior art on QKD reservation, relay contention, starvation

| Work | Year / venue | What it does | Overlap | Reviewer objection |
|---|---|---|---|---|
| **"The Future of QKD Networks"** | arXiv 2407.00877, 2024 | States that without reservation rules key consumption is FCFS, and that two nodes requesting many keys **"may inadvertently starve all intermediary nodes as well as all other pairs of nodes whose paths between each other pass through the two nodes"**; also states that an h-hop end-to-end key consumes key on each of the h links | **Very high** — this is E8's link-specificity starvation mechanism *and* its amplification arithmetic | **Severe.** "Both the mechanism and the arithmetic your E8 identifies are textbook QKD key management." |
| **Dervisevic et al. — QKD Networks Key Management: A Survey** | arXiv 2408.04580, 2024 | Key management architecture survey. **Correction:** an earlier draft of this audit attributed the starvation passage above to this survey; a direct fetch does not contain it. Cited for key-management architecture only. | Moderate | — |
| **Wu et al. — Q-RoKR, "A Distributed Routing Protocol Based on Key Reservation"** | IEEE ICC 2024 | Reserves key **in advance along selected paths** for exclusive use in real-time relay; priority-aware handling of competition during reservation | **High** — advance path reservation with contention handling | "Advance path reservation and its contention are solved problems." |
| Q-learning resource-aware routing in trusted-relay QKD | 2024–25 | Dynamic relay path selection to balance key resources | Moderate | Alternative to our allocator |

**Assessment.** **This is the most damaging finding in the audit.** E6 and E8's
qualitative results — that reservations on shared relay paths starve
path-crossing pairs, and that this is a contention problem needing admission
rules — are already in the QKD literature, including in a survey. What remains
of C5 is only the *quantitative coupling to π and TTL*, and the fresh/stale
decomposition. **C5 must be demoted from a contribution to supporting
evaluation.**

---

## C. Consensus communication structure and predictability

| Work | Year / venue | What it does | What it does not do | Overlap |
|---|---|---|---|---|
| **HotStuff** (Yin et al.) | PODC 2019 | Linear steady-state communication via threshold signatures | No demand-predictability analysis | Background only |
| **PBFT** (Castro & Liskov) | OSDI 1999 | O(n²) all-to-all phases | — | Background |
| **Narwhal/Tusk** (Danezis et al.) | EuroSys 2022 | DAG mempool, leaderless data path | — | Background |
| **TimesNet-BFT** | Entropy 28(3), 2026 | Deep temporal modelling of **latency** history to tune leader election and timeouts | Predicts latency, not resource demand; no structural bound; learned, not closed-form | Low–moderate | "Someone already does temporal prediction in BFT" — answerable: different quantity, learned vs derived |
| **"Predictability of real temporal networks"** | Nat. Sci. Rev. 7(5), 2020 | Entropy-based limits on predictability of temporal graphs; per-link predictability measures | **Measured from traces**, not derived from a generating specification | **Moderate–high on framing** | "Temporal-graph predictability limits already exist." Answerable only by stressing *derived-from-specification, computable with zero data*. |
| Temporal link prediction literature | 2021–2026 | Forecasting future edges in evolving graphs | Empirical/learned; no protocol-derived closed form | Moderate | Same objection |

**Assessment.** No prior work found that derives a **closed-form predictability
limit from a protocol specification**. The temporal-network predictability line
is the framing threat and must be engaged directly and early, not buried.

---

## D. Programmable data plane / eBPF and side channels

| Work | Year | Overlap |
|---|---|---|
| eBPF/XDP (Høiland-Jørgensen et al., CoNEXT 2018) | 2018 | Background for the enforcement layer |
| SDN flow-rule timing side channels (Bifulco ICNP'15; Sonchack ICDCS'16; "Know Your Enemy" 2016; LOFT 2020–23) | 2015–2023 | **High** for any timing-channel claim — the mechanism is established prior art |
| Heimbach et al., "Deanonymizing Ethereum Validators" | USENIX Sec 2025 | Cheaper existing route to the same adversary goal |

**Assessment.** Confirms the decision to **omit the security contribution
entirely** (F9). Any leakage claim would have to survive both the SDN
timing-channel prior art and a cheaper published attack.

---

## E. What was searched and not found

- A closed-form persistence/predictability formula derived from a consensus
  protocol's communication specification.
- A coverage bound for a defined predictor class on consensus resource demand.
- Validation of such a formula against real BFT implementations.
- The fresh/stale reservation decomposition applied to key pre-arming.

These are the four items on which a novelty claim can rest.

---

## F. QKD-networking citation gaps (added by the ICUMT 2025 gate)

The ICUMT 2025 prior-art gate ([`ICUMT_2025_FULLTEXT_AUDIT.md`](ICUMT_2025_FULLTEXT_AUDIT.md))
recovered that paper's complete 12-item reference list. Cross-checking it against
this repository found only two already cited by us (Stan *et al.* DT-VQKP;
Álvarez Roa *et al.*). The following are relevant adjacent prior art we do not
currently cite. **None threaten C1–C3** — all are QKD routing/resource work — but
a QKD-side reviewer would expect at least the first two.

| Work | Venue | Year | Why it belongs |
|---|---|---|---|
| The Evolution of QKD Networks: On the Road to the Qinternet | IEEE COMST | 2022 | The standard QKD-network survey; expected background citation |
| Comparison and optimization of routing methods for meshed QKD networks using trusted nodes (10.1364/jocn.509269) | JOCN | 2024 | Trusted-relay routing baseline |
| ADA-QKDN: routing based on application demand adaptation | Quantum Inf. Process. | 2021 | Application-*demand-adaptive* QKD routing — closest in spirit to demand-aware provisioning |
| QKD network: optimal secret-key-aware routing for trust relaying | China Comms | 2018 | Early key-aware relay routing |
| Towards Optimized Demand Routing in QKD Networks | OFC | 2023 | Demand routing |
| Simulation Study on Impact of Variable SKR and Outdated Information in QKD Networks | RNDM | 2024 | Junqueira/Girão-Silva/Gomes group; *outdated information* is adjacent to our stale-hit analysis |
| Exploring Quantum Key Distribution Routing Algorithms | DRCN | 2025 | Same group; immediate predecessor to ICUMT 2025 |

Both group papers are also `embargoedAccess` in Estudo Geral, so they are cited
from metadata only.
