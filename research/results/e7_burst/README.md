# E7 — burstiness x TTL x shared capacity

**INTERACTION NOT CONFIRMED.**

    TTL* differs between stationary and bursty in 2/14 comparisons, both among
    ties at zero starvation under ample capacity.

    starvation, TTL 1 -> 8 (scarce):
        stationary          -0.2621
        bursty              -0.2438
        bursty mean-matched -0.2871
    Same sign everywhere. E1 measured the OPPOSITE sign.

    ceiling: max(fresh - pi) = +0.0013 (bursty), +0.0044 (stationary)

Burstiness does not explain the E1/E6 discrepancy. The candidate that remains,
read from E1's source but NOT tested here: qkdnet/topology.py reserves `bits` on
EVERY hop of a relay path, so a long lease blocks h links at once. E6/E7 use one
fungible pool, where that amplification cannot occur.

A mean-load control arm separates level from variance: most of bursty's penalty
is the 1.43x higher mean load, not burstiness. Variance alone slightly HELPS
fresh hit.

Files: `E7_REPORT.md`, `figures/` (5 SVGs), `../E7-burst-001.json`.
Code: `research/e7_burst.py`.
