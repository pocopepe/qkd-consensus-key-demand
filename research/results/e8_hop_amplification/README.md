# E8 — multi-hop reservation amplification

**MECHANISM PARTIALLY SUPPORTED.**

    regression control amp=1 vs E7:  max diff 0.0000  PASS

    dS = S(TTL=8) - S(TTL=1), stationary/scarce:
        amp=1  -0.2621      amp=2  -0.1278
        amp=4  -0.0588      amp=8  -0.0241     monotone toward zero
        topo (E1 real)  +0.0030            <-- SIGN FLIP, all four arms

    mechanism is NOT bigger footprint (it falls 0.74 -> 0.59 D).
    it is ARMING FAILURE: 9.14 -> 32.58 per view, live reservations 27 -> 3.
    the sign flip additionally needs LINK SPECIFICITY: successful reservations
    average 1.504 hops against a structural mean of 2.300 -- long paths are
    shut out, which cannot happen in a fungible pool.

Direction of E1 reproduced; magnitude not (+0.003..+0.018 vs E1's 33%).

Files: `E8_REPORT.md`, `figures/` (4 SVGs), `../E8-hopamp-001.json`.
Code: `research/e8_hop_amplification.py` (Model C imports qkdnet/topology.py
unchanged).
