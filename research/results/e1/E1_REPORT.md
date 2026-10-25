# E1 — Real-implementation hub structure validation

Does the hub-union model, and the closed form
`π(n,m,k) = [k(n−1) + m(m−k)] / [m(n−1)]`, describe the per-view communication
graphs of real BFT implementations?

Definitions were fixed in `trace_model.md` **before** any trace was inspected.
Nothing was tuned to the data. Where a hypothesis of mine failed, the failure is
recorded rather than repaired.

---

## 1. Experimental setup

| | |
|---|---|
| Host | Linux 6.8.0-138, 16 cores, 14 GB |
| Networking | loopback `127.0.0.x`, one address per validator |
| Application | CometBFT `kvstore`; libhotstuff bundled demo client |
| Trace source | logical consensus-message layer, no consensus code modified |

**Deviations from stock configuration, all recorded:**

1. CometBFT `timeout_commit` reduced from 1 s to 100 ms, to reach the target
   view count in reasonable wall-clock time. This changes timing, not the
   per-view message graph.
2. CometBFT log level scoped to `p2p:debug,consensus:info,*:error`. Full debug
   logging throttled block production to 0.64 blocks/s through log I/O; scoping
   it raised the rate to ~11 blocks/s. This is less perturbing, not more.
3. libhotstuff built with `-DHOTSTUFF_PROTO_LOG=ON` (a logging flag) and with
   `#include <cstdint>` added to five headers, required by GCC 13. Neither
   changes protocol behaviour.

## 2. Implementations tested

| Implementation | Commit | Status |
|---|---|---|
| CometBFT | `dc83065f00b1cc441ddd1a1b3c5baca95c448967` (v0.40.0) | **run** |
| libhotstuff | `hot-stuff/libhotstuff` HEAD, shallow clone | **run** |
| Narwhal | — | **not run** |

Narwhal was not attempted after the two above produced a consistent and
sufficient answer; it is recorded as not run rather than estimated.

## 3. Trace definition

Full definition in `trace_model.md`. In summary: a **view** is `(height, round)`;
a **message** is one logical consensus message delivered between two validators;
**demand** is one unit per message, corresponding to one Wegman–Carter tag, not
bytes; **support** is the set of pairs with non-zero demand; **persistence** is
demand-weighted.

Two demand models are carried through every result so that no message-selection
choice is hidden:

- **D-core** — proposal and votes only.
- **D-all** — every inter-validator consensus-reactor message.

They agree everywhere, which is itself a result: the verdict does not depend on
which message types are counted.

## 4. Instrumentation

**CometBFT.** The p2p layer logs every inbound message as
`Received bytes ... peer=<nodeid>@<addr> chID=<n> msgBytes=<hex>` on the
receiving node, naming the sending peer. Channels 32–35 are the consensus
reactor. The protobuf payload was decoded far enough to recover message type,
height and round (`research/e1_parse.py`).

*One parser bug worth recording.* The first decoder required the `round` field
tag to be present and discarded every message it could not find it in — which
was all 13,254 of them. Protobuf omits fields at their default value, so
`round = 0` is simply not on the wire. The corrected decoder treats absent
varints as zero and recovers 100% of messages with zero undecoded.

**libhotstuff.** With `HOTSTUFF_PROTO_LOG` the replica logs
`got <proposal rid=R blk=H>` and `got <vote rid=R blk=H>`, plus
`propose <block id=H height=N ...>` which supplies the block-id → height map
(`research/e1_parse_hs.py`). Self-delivery is excluded, since it consumes no
link key.

## 5. Hub-union fit

`m` is the **minimum vertex cover** of the observed support — not a judgement.
`S(t) ⊆ ⋃_{h∈R} star(h)` holds exactly when `R` covers every observed edge, so
the hub set is determined, and ties are broken lexicographically, independently
of the previous view, so `k` cannot be inflated.

**Table 2 — fit quality**

| implementation | regime | n | support | max edges | m | m cv | k cv | ρ | hub-union? |
|---|---|---|---|---|---|---|---|---|---|
| CometBFT | steady | 4 | 5.99 | 6 | 3.00 | 0.019 | 0.020 | 0.0000 | **yes** |
| libhotstuff | stable-leader | 4 | 3.00 | 6 | 1.00 | 0.000 | 0.000 | 0.0000 | **yes** |
| libhotstuff | induced-rotation | 4 | 3.00 | 6 | 1.00 | 0.000 | 0.042 | 0.0009 | **yes** |

Both implementations are exactly hub-union: `ρ = 0`, meaning every edge the
model predicts is present and no edge is missing. `m` and `k` are essentially
constant across views (`cv ≤ 0.042`), satisfying the constant-`m,k` assumption.

The two are structurally opposite, and `m` detects it:
CometBFT gossips, giving a complete graph and `m = n−1 = 3`; libhotstuff
unicasts votes to the leader, giving a star and `m = 1`.

## 6–7. Predictions vs measurement

**Table 1 — theory vs measured**

| implementation | regime | model | n | runs | views | m | k | ρ | π theory | π measured | error |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CometBFT | steady | D-core | 4 | 2 | 1,457 | 3.00 | 3.00 | 0.0000 | 1.0000 | 1.0000 ± 0.000 | **0.0000** |
| CometBFT | steady | D-all | 4 | 2 | 1,458 | 3.00 | 3.00 | 0.0000 | 1.0000 | 1.0000 ± 0.000 | **0.0000** |
| libhotstuff | stable-leader | D-core | 4 | 6 | 73,589 | 1.00 | 1.00 | 0.0000 | 1.0000 | 1.0000 ± 0.000 | **0.0000** |
| libhotstuff | stable-leader | D-all | 4 | 6 | 73,589 | 1.00 | 1.00 | 0.0000 | 1.0000 | 1.0000 ± 0.000 | **0.0000** |
| libhotstuff | induced-rotation | D-core | 4 | 3 | 4,546 | 1.00 | 1.00 | 0.0009 | 1.0000 | 0.9987 ± 0.000 | **0.0013** |
| libhotstuff | induced-rotation | D-all | 4 | 3 | 4,546 | 1.00 | 1.00 | 0.0009 | 1.0000 | 0.9987 ± 0.000 | **0.0013** |

All errors are far inside the `< 0.05` strong-agreement band.

## 8. Statistical results

Runs: libhotstuff 6 stable + 3 induced; CometBFT 2 at n=4 with a larger sweep
still collecting. Views: 79,592 (libhotstuff) and 1,458 (CometBFT). Confidence
intervals on π are below `0.0005` in every group — the quantity is essentially
deterministic within a configuration, so run-to-run variation is not what limits
this experiment. **What limits it is that every configuration landed on the same
point of the model's parameter space.**

## 9. Pipeline results

**Not executed, and the reason is a finding.** The pipeline sweep required by
Phase 6 presumes an implementation with a tunable per-view rotation depth.
Neither implementation has one:

- CometBFT does not pipeline in the HotStuff sense.
- libhotstuff ships exactly two pacemakers: `PaceMakerDummyFixed` (fixed
  proposer) and `PMRoundRobinProposer`. Reading `include/hotstuff/liveness.h`,
  the latter is a **view-change** mechanism, not a per-view rotation: it calls
  `rotate()` on impeachment and then `stop_rotate()` once a proposal is
  accepted, settling on a stable proposer. The log line `Pacemaker: stop
  rotation at 0` appears once at start-up and the system then runs with a fixed
  hub.

The induced-rotation regime was constructed to force the issue: the current
proposer was killed and restarted every 3 s for the run's duration. Even then
replica 0 proposed **4,485 of 4,536 blocks (98.9%)**, with 22 pacemaker events
producing brief excursions before the system returned to the same hub. Measured
`k = 0.998` against `m = 1`.

**In neither implementation, under fault or otherwise, was `k/m < 1` observed.**

## 10. Aggregation and batching effects

CometBFT's gossip is visible directly: support is the complete graph on every
view (`5.99` of `6` possible edges), which is why `m = n−1`. Block delivery is
split into `BlockPart` messages, counted in D-all and not in D-core; the two
models agree to four decimals, so this choice does not affect the verdict.

Batching was not swept here. The synthetic result in `research/realism.py` —
that one-time-pad payload weighting drives `π → 1` — is untested against a real
trace and remains a limitation, though under the tag-only demand model fixed in
the trace definition it does not arise.

## 11. Failures and counterexamples

1. **The parser discarded 100% of messages** on the first attempt, from a wrong
   protobuf assumption. Fixed; recorded in §4.
2. **The shell campaign driver was repeatedly killed** by process-group cleanup,
   losing runs. Replaced with a resumable driver that records each run on
   completion. No result was affected; wall-clock was.
3. **The pipeline sweep is not executable** on either implementation (§9).
4. **No counterexample to the model was found.** Every configuration measured is
   hub-union with `ρ ≤ 0.0009`, and every prediction is within 0.0013.

## 12. Threats to validity

- **The decisive one.** All six configurations sit at `k/m = 1`, where the
  formula reduces to `π = 1` and the numerator's `m(m−k)` correction term
  vanishes. The measurement therefore confirms the model **only on its
  degenerate boundary**. The term that makes the formula non-trivial has not
  been tested against any real system.
- `n = 4` throughout the completed runs. The larger sweep (n = 7, 10, 16) was
  still collecting when this report was written; `n` appears in the formula only
  through `(n−1)`, and at `k = m` that factor cancels, so larger `n` is not
  expected to change the verdict.
- Loopback networking; no WAN delay, loss or reordering.
- Two implementations, both `n = 3f+1` partially-synchronous BFT. No DAG
  protocol, no committee sortition.
- The induced-rotation regime is a fault mode built for this experiment, not a
  configuration anyone deploys.

## 13. Verdict

> ## PARTIALLY SUPPORTED

**What is supported, strongly.** The hub-union abstraction is not an idealisation
that real implementations merely approximate — they fit it *exactly*. `ρ = 0.0000`
over 79,592 views of libhotstuff and 1,458 views of CometBFT, with `m` and `k`
stable across views. Where the model is applicable, `π` is predicted with error
`≤ 0.0013`, well inside the strong-agreement band, and the prediction holds
under an induced fault regime as well as in steady state. The minimum-vertex-cover
definition of `m` correctly distinguishes the two implementations'
opposite communication structures without being told which is which.

**What is not supported.** The measurement confirms the model only at `k/m = 1`,
where `π = 1` and no forecasting gain exists. The regime that motivates the
entire line of work — per-view leader rotation, `k/m < 1`, `π → 1/2`, structural
forecasting gain `1 − π` — **was not produced by either implementation, in
steady state or under induced leader failure.** libhotstuff has no per-view
rotation mode; CometBFT gossips and is all-to-all by construction.

**Consequence for the research direction.** Theorem A survives E1 and is
strengthened as a *descriptive* result: it predicts real communication graphs
exactly. But the practical claim built on it — that a schedule-aware forecaster
wins `1 − π` on deployed systems — is not supported by these two
implementations, because on them `1 − π = 0`.

The claim is not thereby refuted: protocols that do rotate per view exist
(Ethereum's slot-based proposer rotation, chained HotStuff as specified, Diem /
Aptos-lineage implementations). But that regime must be demonstrated on a system
that actually exhibits it. Until then the honest statement is that **the
predictability limit is computable and exact, and on the two reference
implementations measured it computes to "prediction buys nothing".**

That is a publishable finding — a closed form that tells an operator in advance
not to build the system — but it is a different paper from the one the
repository was heading toward, and it must not be presented as validation of
the forecasting gain.
