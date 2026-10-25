# E6 — shared finite QKD pool

**QUALIFIED.** The structural result survives; operational implications do not.

    fresh-hit <= pi:   max(fresh - pi) = +0.0043 over 48 cells, ALL regimes,
                       BOTH admission policies. Contention pushes hits DOWN.
    but:               at pi = 1.0 (perfect prediction) high contention still
                       starves 26.6% of requests -- capacity, not pi, binds.
    starvation:        0.898 at pi=0.1333, TTL=1, caused BY pre-arming draining
                       the shared pool. Falls to 0.327 at TTL=8.

Two methodological corrections are documented in the report rather than hidden:
the contention regimes were first defined on refill rate and produced zero
contention (expired reservations return capacity, so refill is the wrong knob);
and deterministic arming order was a hidden priority rule that inflated
unfairness to 0.97 -- fair admission gives 0.15-0.18.

Reconciliation with E1: E1 found long leases harmful under FLASH CROWDS; E6's
workload is stationary, where they help. Different workloads, not a conflict.
Lease duration is workload-dependent.

Files: `E6_REPORT.md`, `figures/` (6 SVGs),
`../E6-sharedpool-random.json`, `../E6-sharedpool-fifo.json`.
Code: `research/e6_shared_pool.py` (ARM_ORDER=random|fifo).
