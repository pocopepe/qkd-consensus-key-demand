# E4-TTL — reservation lifetime sweep

**OUTCOME C.** The prediction ceiling holds; TTL is a budget/cost dial.

    fresh hits (actual predictions):  max(hit - pi) = +0.0044 at EVERY TTL
    total hits (incl. stale):         max(hit - pi) = +0.7301 at TTL=8
    mechanism:                        live reservations reach 3.77x the budget K
    waste:                            E4's slope-1 law is TTL=1 only
                                      slope 0.977 -> 0.091 as TTL 1 -> 8

E4's "hit rate <= pi" is qualified: it was a TTL=1 statement. Theorems A and B
are unaffected.

Caveat that matters most: per-pair key pools are inherited from E4, so there is
no cross-pair contention here. E1 found the opposite sign under shared link
pools (long leases raised starvation up to 33%). "Longer TTL is better" does NOT
transfer to shared pools.

Files: `E4_TTL_REPORT.md`, `figures/` (4 SVGs), `../E4TTL-001.json`.
Code: `research/e4_ttl.py` (imports the E4 workload unchanged).
