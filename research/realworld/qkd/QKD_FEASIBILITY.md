# QKD feasibility of authenticating chained-BFT consensus

This is a calculation, not a pre-specified test. The code is `feasibility.py`; the numbers are in
`QKD_FEASIBILITY.json`, regenerated at the end of Cycle 3 with all fetched data.

## Model

- **Demand.** Every message consumes one Wegman–Carter tag's worth of one-time-pad key (64 or 128 bits).
  - With votes sent to the next leader, a view has D = 2(n−1) messages, of which U = n − 3 cannot be carried
    forward (π = (n+1)/(2(n−1))).
  - With votes broadcast, a view has (n+1)(n−1) messages, all carried (k = m).
- **Supply.** Validators sit on a metropolitan trusted-relay ring, one per node (N = n). Each logical pair is
  guaranteed at least B ≥ 4R/[N(N−1)] (Dynes et al., npj Quantum Inf. 5:101, 2019, Eq. 1). Rotation spreads demand
  evenly over pairs, so the ring is **guaranteed** to sustain v_max = 2R / (D × tag bits) views per second.
- **Ceiling.** A cut through the ring's midpoint leaves two links to carry (n/2)² pairs, so an even share is at most
  8R/n² and no routing sustains more than v_cap = v_max × 2(n−1)/n (n even). A design is infeasible only above v_cap;
  between v_max and v_cap it is undetermined. (Correction, 2026-09-22: the first version of this note read v_max as
  a ceiling, and so called some undetermined cases failures; see FALSIFIED_CLAIMS.md F21.)
- **Measured link rates:**
  - Cambridge metro network: 2.22–2.58 Mbps average over 580 days on 5.0–10.6 km links (Dynes et al. 2019).
  - Tokyo QKD network, 45 km, 14.5 dB: 304 kbps (a 24 h average) and 81.7 kbps (Sasaki et al., Opt. Express
    19:10387, 2011).
- **Measured view rates:**
  - Aptos: 26.8 rounds/s (25.0–29.6 across the 40 held-out epochs).
  - Cosmos Hub: 0.169 blocks/s (a block every 5.9 s).

## Result, at Aptos's view rate with 128-bit tags

| Link rate | Votes to next leader | Votes broadcast |
|---|---|---|
| 2.22 Mbps (Cambridge, 5 km) | guaranteed up to n = 100 | guaranteed to n = 32; **infeasible at n = 64** (v_cap 16.7) |
| 304 kbps (Tokyo, 45 km) | guaranteed to n = 64; undetermined at n = 100 | undetermined at n = 16; **infeasible from n = 32** |
| 81.7 kbps (Tokyo, 45 km) | guaranteed to n = 16; undetermined at n = 32; **infeasible from n = 64** | **infeasible from n = 16** |

Vote routing is therefore a decision that QKD supply changes. The broadcast design needs (n+1)/2 times more key
per view. Choosing unicast leaves U/D = (n−3)/(2(n−1)), about 48%, of each view's demand uncarried, out of reach of a
carry-forward provisioner, and that fraction must be served reactively or by schedule-aware provisioning.
