# Evaluation

Kernel measurements are from Linux 6.8.0-138 with the XDP program loaded; the
consensus and QKD layers are simulated. Every table names which it is.

## 1. Kernel data plane (measured)

### 1.1 Instruction count does not scale with the pre-arm set

`src/xdp_enforcer.o`, loaded at six map capacities spanning 16,384x:

| M_max | 64 | 256 | 1024 | 16384 | 262144 | 1048576 |
|---|---|---|---|---|---|---|
| verified_insns (minimal path) | 244 | 244 | 244 | 244 | 244 | 244 |

The full enforcer -- sliding-window leases, per-validator token buckets,
amortised garbage collection -- verifies at **2,851 instructions**, 5,984 bytes
xlated, 3,305 bytes JIT-ed. That is 0.29% of the verifier's 1,000,000 ceiling,
and it too is independent of map capacity. The instruction budget is not a
resource the allocator competes for.

### 1.2 What a commit costs

Timed through `bpf_map_update_elem` and `BPF_MAP_UPDATE_BATCH`:

| entries | serial ns/op | batch ns/op |
|---|---|---|
| 16 | 3,642 | 3,064 |
| 64 | 3,591 | 1,389 |
| 256 | 3,119 | 1,170 |
| 4096 | 2,982 | 1,159 |

Batching pays above roughly 32 entries and saturates near a 3x saving. At a
250 ms view spending 1% of itself on map updates, `U_max` is about **800 entries
serial or 2,000 batched** -- and only *changed* entries are charged, so a stable
pre-arm set costs nothing to keep.

### 1.3 End-to-end service time

veth pair across a network namespace, XDP in skb mode, KME stub at the 3 ms
literature figure for an ETSI GS QKD 014 round trip:

| population | n | p50 | p99 | min |
|---|---|---|---|---|
| pre-armed (answered by XDP) | 3000 | **14.2 us** | 20.9 us | 13.8 us |
| not pre-armed (KME path) | 3000 | 3074.6 us | 3298.0 us | 3070.2 us |

Requests are separated by the flag the kernel sets, not by a latency threshold.
In-kernel service time from the program's own counters is
`fast_ns/hits = 1,700,741/3,100 =` **548 ns**; the remaining ~13.6 us is veth
transit and the client's own syscalls.

The honest form of the claim: the 3 ms is a parameter, the 14.2 us is a
measurement. Whatever a real KME costs, the fast path removes it.

### 1.4 Leases expire without starving anyone

40 pairs armed with a 300 ms sliding lease and a 400 ms hard ceiling, then left
silent:

| | live entries | gc_reclaimed | starvation credits |
|---|---|---|---|
| t = 0 s | 40 | 0 | 0 |
| t = 1 s, no traffic | 40 | 0 | 0 |
| after 400 packets | **0** | **40** | **80** |

All forty reclaimed, and 80 credits (two owners per pair) handed back to the
daemon so the pairs it mis-forecast are re-prioritised rather than skipped again.

**A real property, documented rather than hidden:** the sweep is amortised over
packets, so a fully idle interface never reclaims. The daemon's own TTL is the
backstop for that case.

Under live traffic the sliding window does its job: 3,100 hits produced 3,100
renewals and zero mid-round evictions.

## 2. Forecasting (simulated)

Coverage of next view's demand by the top-48 predicted pairs:

| forecaster | round-robin | +2 Byzantine | VRF, lookahead 4 |
|---|---|---|---|
| EWMA, alpha tuned per scenario | 0.593 | 0.521 | 0.694 |
| Holt (level + trend) | 0.626 | 0.554 | 0.686 |
| **structural** | **0.993** | **0.920** | **0.993** |
| structural, schedule ablated | 0.400 | 0.397 | 0.400 |

Theorem 2 in `theory.md` explains the EWMA column: its ceiling is the support
persistence of the workload, which for chained HotStuff is one half, because the
vote star of view t-1 is the proposal star of view t. Measured persistence at
n=16 is 0.567 against a measured EWMA coverage of 0.520.

## 3. Horizon buys nothing after the first view

21,900 rounds over the event-driven substrate, against a reactive baseline at
p50 = 6.000 ms:

| H | p50 saved | armed entries | hit rate |
|---|---|---|---|
| 1 | 5.986 ms | 31 | 0.513 |
| 2 | 5.986 ms | 39 | 0.521 |
| 3 | 5.986 ms | 44 | 0.518 |
| 4 | 5.986 ms | 49 | 0.533 |
| 6 | 5.986 ms | 51 | 0.526 |

Latency saved is flat to three decimals while held entries grow by 65%. A
one-view horizon already covers both stars of the imminent view, so everything
past it is pure cost -- in map footprint, in held key, and (per theory.md 3.3)
in schedule secrecy, since the leak horizon tracks the forecast horizon exactly.

**Design rule: hold H = 1.**

## 4. Pre-arming makes starvation worse, and the fix is not the obvious one

The expected result was that pre-positioning key reduces starvation. It does the
opposite:

| flash-crowd probability | 0.00 | 0.02 | 0.05 | 0.10 | 0.20 | 0.35 |
|---|---|---|---|---|---|---|
| reactive | 0.0000 | 0.0060 | 0.0264 | 0.1128 | 0.2409 | 0.3717 |
| predictive (2-view lease) | 0.0000 | 0.0082 | 0.0352 | 0.1258 | 0.2554 | 0.3800 |
| + hoarding penalty gamma=1 | 0.0000 | 0.0082 | 0.0352 | 0.1258 | 0.2554 | 0.3800 |
| **+ penalty, 1-view lease** | 0.0000 | **0.0060** | **0.0264** | **0.1123** | **0.2408** | **0.3715** |

A reservation holds key on every hop of a relay path for the whole lease. During
a flash crowd that key is exactly what the burst needs and cannot have, so
confident-but-slightly-wrong forecasting converts directly into starvation --
a 33% relative increase at burst probability 0.05.

**The hoarding penalty does nothing.** Charging gamma per bit-hop held changes
*which* pairs are chosen, and under a quorum objective the block value dominates
the per-pair term, so the selection barely moves. Identical numbers to three
decimals.

**Shortening the lease fixes it completely.** One view instead of two returns
starvation to the reactive baseline (0.2408 against 0.2409) while keeping the
fast path -- at burst probability 0.05 the short-lease arm holds p50 at 0.014 ms
where the long-lease arm has already fallen back to 6.000 ms.

The cost of holding key is a **duration** problem, not a selection problem. This
is why the enforcer's lease is a short window that the data plane renews on
actual use: arm briefly, extend only what is really being drawn on.

## 5. Allocation policies

### 5.1 Hit rate is a misleading metric

Round latency is the quorum order statistic, so a pre-armed pair that does not
complete a block changes nothing. Measured at 450 views per point:

| M_max | greedy hit / p50 / armed | quorum hit / p50 / armed | hybrid hit / p50 / armed |
|---|---|---|---|
| 192 | 0.269 / 6.00 ms / 60 | **0.515 / 0.01 ms / 32** | 0.307 / 6.00 ms / 51 |
| 128 | 0.174 / 6.00 ms / 40 | **0.452 / 0.01 ms / 24** | 0.322 / 4.50 ms / 27 |
| 96 | 0.166 / 6.00 ms / 28 | **0.450 / 0.01 ms / 24** | 0.325 / 4.50 ms / 19 |
| 64 | 0.162 / 6.00 ms / 18 | 0.225 / 6.00 ms / 13 | 0.042 / 6.00 ms / 3 |
| 48 | 0.183 / 6.00 ms / 11 | 0.219 / 6.00 ms / 12 | 0.009 / 6.00 ms / 1 |
| 32 | 0.117 / 6.00 ms / 7 | 0.000 / 6.00 ms / 0 | 0.000 / 6.00 ms / 0 |

Density-greedy at M=192 holds **60 entries and delivers nothing**: p50 stays at
the reactive 6.00 ms while a third of individual requests hit. The quorum rule
holds *half* as many entries and reaches 0.01 ms. Reporting hit rate alone would
have made greedy look like it was working.

**The cliff between M=96 and M=64 is the quorum threshold.** Below roughly
2 x (2f + slack) x mean_hops entries, no policy can complete a block and
pre-arming is strictly harmful -- it holds key and buys no latency. Scored on
the corrected objective, greedy goes **negative** there (-0.13, -0.09, -0.07 of
bound), while the hybrid correctly declines to arm at all and scores zero.

### 5.2 The hybrid bridges the offline gap but loses the live system

Against the scenario-correlated objective with an entry-hold cost, and a valid
upper bound from a scenario knapsack:

| M_max / U_max | greedy | lagrangian | quorum | hybrid |
|---|---|---|---|---|
| 192 / 96 | 0.071 | 0.071 | **0.386** | 0.297 |
| 192 / 48 | 0.477 | 0.477 | 0.611 | **0.624** |
| 192 / 24 | 0.738 | 0.738 | 0.710 | **0.808** |
| 96 / 16 | −0.130 | −0.130 | −0.105 | 0.000 |
| 48 / 12 | −0.087 | −0.087 | −0.105 | 0.000 |

The hybrid closes 24–28% of the residual gap over density-greedy wherever a
block is coverable at all. But in the live loop it does not win:

| planning budget | hit | p50 | wall per view |
|---|---|---|---|
| 2 ms | 0.264 | 6.000 ms | 9.5 ms |
| 4 ms | 0.325 | 4.500 ms | 18.1 ms |
| 25 ms | 0.322 | 4.500 ms | 34.8 ms |
| 50 ms | 0.322 | 4.500 ms | 59.5 ms |
| **quorum rule** | **0.456** | **0.014 ms** | **8.3 ms** |
| greedy rule | 0.166 | 6.000 ms | 6.3 ms |

More search does not help: the hybrid saturates at 4.5 ms of round latency by a
4 ms budget and never improves, while the fixed quorum rule reaches 0.014 ms for
less compute. **A general-purpose metaheuristic did not beat a rule derived from
the protocol's own structure**, and buying it twenty-five times the search budget
did not change that.

The reason is worth stating: the quorum rule encodes three things the random
search has to rediscover every view -- cover blocks whole, take the
topologically cheapest quorum, keep a liveness margin past the threshold. Those
are consequences of the protocol, not of the instance, so paying to search for
them each round is paying for something already known.

### 5.3 What each correction was worth

Three hypotheses were wrong, and each correction changed the design:

| hypothesis | what the data said | consequence |
|---|---|---|
| EWMA is anti-correlated with real star demand | positive correlation for large alpha; correlation is the wrong statistic | Theorem 2: the ceiling is support persistence, = 1/2 |
| Faster smoothing overshoots more on bursts | burst error falls monotonically in alpha | Theorem 3: burst-optimal alpha is rotation-worst alpha |
| A hoarding penalty fixes the starvation regression | identical to three decimals | the cost of holding is a duration problem; shorten the lease |
| Blocks can be scored independently | the hybrid over-armed hedging an uncoverable event | scenario correlation + entry cost in the objective |

## 5. Open

- No competitive-ratio bound for the switching-cost formulation.
- One consensus protocol. PBFT's O(n^3) view change and DAG protocols have
  different demand structure and would test whether the structural forecaster
  generalises.
- The side-channel adversary is passive. An adaptive one that reacts to the
  observed pre-arm set is not modelled.
