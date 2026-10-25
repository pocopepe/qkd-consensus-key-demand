# E2 — Candidate selection: finding a real system with `k < m`

Not an experiment. A selection decision, made by reading code and running
trials, about which real implementation can test Theorem A outside the
degenerate boundary E1 landed on.

---

## 1. Research question

E1 validated the hub-union abstraction and Theorem A only where `k = m`, so
`π = 1` and the `m(m−k)` term vanishes. The question here is:

> Which real, executable, reproducible consensus implementation naturally
> produces `k < m` for a substantial fraction of consecutive views?

The trap E1 exposed, and the reason this is not a one-line answer: **rotating
leaders is not the requirement.** CometBFT rotates its proposer every height and
still gave `k = m = n−1`, because votes are gossiped, so the support is the
complete graph and rotation is invisible in it.

The actual requirement is two conditions together:

1. per-view leader rotation, and
2. **vote routing that is not gossip** — votes addressed to a specific replica,
   so the support is a union of stars rather than a mesh.

## 2. Candidates investigated

| Candidate | Source inspected | Built | Run |
|---|---|---|---|
| relab/hotstuff | `protocol/comm/clique.go`, `protocol/leaderrotation/*` | yes | yes |
| libhotstuff | `include/hotstuff/liveness.h` | yes (E1) | yes (E1) |
| CometBFT | p2p channel behaviour | yes (E1) | yes (E1) |
| Aptos (aptos-core) | `consensus/src/round_manager.rs`, `consensus/src/network.rs` | no | no |
| Ethereum consensus clients | protocol specification | no | no |
| hotstuff-rs | — | no | no |

`parallelchain-io/hotstuff-rs` could not be located at the expected URL (404).
Recorded as not investigated rather than assessed.

## 3–4. Protocol- and implementation-level analysis

### relab/hotstuff — the structure is the model

`protocol/comm/clique.go` describes itself as *"one-to-all dissemination and
all-to-one aggregation"*, and the code does exactly that:

```go
func (hs *Clique) Disseminate(proposal *hotstuff.ProposeMsg, pc hotstuff.PartialCert) error {
    hs.sender.Propose(proposal)          // broadcast  -> star(L(t))
    return hs.Aggregate(proposal, pc)
}

func (hs *Clique) Aggregate(proposal *hotstuff.ProposeMsg, pc hotstuff.PartialCert) error {
    nextView := proposal.Block.View() + 1
    leaderID := hs.leaderRotation.GetLeader(nextView)
    ...
    return hs.sender.Vote(leaderID, pc)  // unicast   -> star(L(t+1))
}
```

`core.Sender.Vote(id hotstuff.ID, cert)` takes a single destination id — this is
a unicast, not a broadcast. And rotation is genuinely per view:

```go
func (rr RoundRobin) GetLeader(view hotstuff.View) hotstuff.ID {
    return ChooseRoundRobin(view, rr.config.ReplicaCount())
}
```

So `S(t) = star(L(t)) ∪ star(L(t+1))` with `L` rotating every view, giving
`m = 2`, `k = 1` — the chained-linear corollary, not an approximation of it.

Available modules give a *designed sweep* over the parameter the theorem is
about, within one codebase:

| module family | values | effect on (m, k) |
|---|---|---|
| `--communication` | `clique`, `kauri` | clique → star union; kauri → tree aggregation, larger `m` |
| `--leader-rotation` | `round-robin`, `fixed`, `carousel`, `reputation`, `tree-leader` | `fixed` → `k = m = 1`; the rest rotate |
| `--consensus` | `chainedhotstuff`, `fasthotstuff`, `simplehotstuff`, `byzantine` | chain length / phase structure |

`--leader-rotation fixed` should reproduce E1's libhotstuff result exactly
(`m = 1, k = 1, π = 1`), which makes it a **built-in control**: the same binary,
the same parser, one flag apart, spanning the degenerate and non-degenerate
regimes.

**Discrepancy between specification and implementation: none found.** This is
the first candidate where the implementation matches the textbook chained
HotStuff communication pattern.

### libhotstuff — ruled out in E1

`PMRoundRobinProposer` is a view-change mechanism, not per-view rotation:
`rotate()` fires on impeachment and `stop_rotate()` settles on a stable
proposer. Measured `k/m = 1` even under induced leader kills (98.9% of blocks
proposed by replica 0).

### CometBFT — ruled out in E1

Proposer rotates per height, but votes are gossiped on channels 32–35 to all
peers, so the support is the complete graph: `m = n−1`, `k = m`, `ρ = 0`,
`π = 1`. Rotation exists and is invisible in the support.

### Aptos — plausible, expensive

`network.rs` exposes `send_vote(vote_msg, recipients: Vec<Author>)`, i.e.
unicast-capable, and `round_manager.rs` broadcasts proposals
(`broadcast_proposal`) while resolving `get_valid_proposer(round)` for vote
targeting. The structure is therefore plausibly `m = 2, k = 1`. Not confirmed:
the `send_vote` call site and the recipient list were not traced to a
conclusion, and leader selection uses **leader reputation**, not pure
round-robin, so `k` may be less regular.

Cost is the problem: a full `aptos-core` Rust build plus a local testnet is
hours of setup, and block rate is far lower than a research framework.

### Ethereum consensus layer — structurally unsuitable

Proposer rotation per slot is genuine and the schedule is known an epoch ahead,
which sounds ideal. The communication is not:

- Blocks are published to the `beacon_block` **gossipsub** topic, not sent
  point-to-point from the proposer.
- Attestations go to attestation **subnets**, are aggregated by selected
  aggregators, and the aggregates are gossiped again.

The per-slot support is therefore a gossipsub mesh plus subnet meshes, which is
**not a union of stars**. A minimum vertex cover of a mesh is large, and the
mesh is stable across slots, so the expected outcome is large `m`, `k ≈ m`, and
— worse — a large residual `ρ`, meaning the hub-union model does not describe
the graph at all. Add 12-second slots (1000 views ≈ 3.3 hours) and a Kurtosis
multi-client testnet, and the cost is high for a result the structure predicts
will be uninformative.

**If the answer were Ethereum, the part to instrument would be the beacon
node's libp2p gossipsub layer per topic.** It is not the answer.

## 5. Candidate scoring

Scored 1–5; higher is better.

| Criterion | relab/hotstuff | Aptos | Ethereum CL | libhotstuff | CometBFT |
|---|---:|---:|---:|---:|---:|
| Natural `k < m` regime | **5** | 4 | 2 | 1 | 1 |
| Hub-union compatibility | **5** | 4 | 1 | 5 | 5 |
| Easy local reproduction | **5** | 2 | 2 | 4 | 4 |
| Instrumentation access | **5** | 3 | 3 | 4 | 4 |
| Controllable validator count | **5** | 4 | 4 | 3 | 5 |
| Deterministic leader schedule | **5** | 3 | 4 | 2 | 4 |
| Ability to collect 1000+ views | **5** | 3 | 1 | 5 | 4 |
| Minimal environmental complexity | **5** | 2 | 1 | 4 | 4 |
| Similarity to theoretical model | **5** | 4 | 2 | 3 | 2 |
| Scientific value | 4 | **5** | **5** | 3 | 4 |
| **Total** | **49** | 34 | 25 | 34 | 37 |

relab/hotstuff loses a point only on scientific value, and for a real reason
(§8).

## 6. Expected `m`, `k`, `ρ`

Derived from the code, to be confirmed by measurement — stated in advance so
the prediction is falsifiable:

| configuration | expected m | expected k | expected ρ | expected π |
|---|---:|---:|---:|---|
| clique + round-robin, n=4 | 2 | 1 | 0 | 0.8333 |
| clique + round-robin, n=7 | 2 | 1 | 0 | 0.6667 |
| clique + round-robin, n=16 | 2 | 1 | 0 | 0.5667 |
| clique + round-robin, n=32 | 2 | 1 | 0 | 0.5323 |
| clique + **fixed** (control) | 1 | 1 | 0 | 1.0000 |
| kauri + round-robin | > 2 | ? | > 0 | ? |

The `n` sweep is what makes this a real test: `π = (n+1)/(2(n−1))` is a
*non-constant* prediction, unlike every value E1 was able to measure.

## 7. Expected experimental difficulty

Low. Measured in trial runs already performed:

- Builds with the Go toolchain already installed (`go build ./...` clean).
- `go run ./cmd/hotstuff run --replicas 4 --duration 10s` reached **view 4,343**,
  roughly 430 views/second. A 1000-view trace takes seconds, not hours.
- `--log-pkgs "votingmachine:debug"` already emits
  `CollectVote(from N)` on the receiving replica, tagged with the replica's
  logger name (`hs3`) — **17,372 vote-delivery records in one 10 s run**, with
  sender and receiver both recoverable without touching the source.

Two gaps remain: mapping block hash → view, and logging proposal *receipt*.
Both are addressed in §11.

## 8. Threats to validity

- **The main one.** relab/hotstuff is a research framework, not a deployed
  production system. Measuring it validates the model against a faithful
  implementation of the specification, which is weaker than validating against
  something running real value. A reviewer is entitled to say so. The honest
  framing is: E1 showed two *production-lineage* systems sit at `k = m`;
  E2 would show that an implementation which follows the chained-HotStuff
  specification sits at `k < m` exactly where the theorem says. Both halves are
  needed and neither substitutes for the other.
- Aptos remains the one candidate that is both production-grade and plausibly
  `k < m`. It should be the follow-up if the specification-level result holds.
- The trial run was timeout-dominated (`no command batch`, views advancing by
  TC rather than QC). Timeout views have a different support — a timeout
  certificate is collected all-to-one but there is no proposal star — so the
  workload must be configured to keep the happy path dominant, and the
  timeout fraction must be measured and reported, not assumed away.
- `--fixed-timeout` and batch settings change the happy/timeout mix. They must
  be fixed in advance and reported, not tuned toward a desired `π`.

## 9. Recommended implementation

> **relab/hotstuff**, commit `3179c6e62929294961acbfd9bf8445769716a121`
> (2026-07-14), `chainedhotstuff` + `clique` + `round-robin`.

Chosen because it is the only investigated implementation whose *source* shows
one-to-all dissemination with all-to-one aggregation to `GetLeader(view+1)` and
per-view round-robin rotation — the two conditions in §1 — and because it ships
a one-flag control (`--leader-rotation fixed`) that reproduces E1's degenerate
case in the same binary.

## 10. Exact configuration to test

```
go run ./cmd/hotstuff run \
  --replicas {4,7,10,16,32} \
  --clients 2 --batch-size 10 --max-concurrent 20 \
  --consensus chainedhotstuff \
  --communication clique \
  --leader-rotation {round-robin | fixed} \
  --duration 30s \
  --fixed-timeout 100ms \
  --log-level info \
  --log-pkgs "votingmachine:debug,consensus:debug,comm:debug"
```

5 validator counts x 2 rotations x 5 runs = 50 runs, a few minutes total.
`--leader-rotation fixed` is the control arm and must be run and reported, not
just the rotating arm.

## 11. Required instrumentation

Existing, no patch:
- `CollectVote(from N)` at debug in `protocol/votingmachine/votingmachine.go:55`,
  with the receiving replica identified by the logger name.

Needed, as a **logging-only** patch to `protocol/comm/clique.go` — no behaviour
change, matching the E1 precedent of raising log verbosity only:

1. In `Disseminate`, log `(view, from=self, to=ALL, type=proposal)` before
   `sender.Propose`.
2. In `Aggregate`, log `(view, from=self, to=leaderID, type=vote)` before
   `sender.Vote`.
3. On the receive path, log proposal receipt with `(view, from, to=self)`.
4. Include the **view number** in each, removing the need to reconstruct
   block-hash → view.

The patch must be recorded in the report and its diff kept, as the libhotstuff
`<cstdint>` patch was in E1.

## 12. Expected data format

Identical to E1 so the existing analysis runs unchanged:

```json
{"n_validators": 16,
 "records": [[view, round, sender, receiver, "Proposal"|"Vote"], ...]}
```

`research/e1_analyze.py`, `e1_report.py` and `e1_fig3.py` then apply as-is:
minimum vertex cover for `m`, lexicographic tie-break for `k`, demand-weighted
`π`, and `ρ` as the over-prediction residual.

## 13. Minimum experiment to establish the non-degenerate regime

The smallest result that would settle the question:

1. **`m = 2, k = 1, ρ ≈ 0`** measured on `clique + round-robin`, over ≥1000
   views, ≥5 runs, at ≥3 validator counts.
2. **`π` matching `(n+1)/(2(n−1))`** across those `n`, with error < 0.05 — a
   *non-constant* prediction, which is what E1 could not test.
3. **The control arm reproducing `m = 1, k = 1, π = 1`** under
   `--leader-rotation fixed`, confirming the sweep spans both regimes.
4. **Timeout-view fraction reported**, with `π` computed on happy-path views and
   on all views separately.

Falsification: `ρ > 0.15` (not hub-union), or `|π_measured − π_theory| > 0.15`
at any `n`, or `k = m` in the rotating arm (rotation invisible in the support,
as in CometBFT).

## 14. Verdict

> ## GO

A practical implementation exists, is already built and running on this machine,
produces `k < m` by construction rather than by configuration accident, reaches
430 views/second, exposes the required sender/receiver instrumentation at debug
level, and includes a one-flag control that reproduces E1's degenerate result.

The `n`-sweep gives the first opportunity to test a **non-constant** prediction
of Theorem A, which is precisely what E1 could not do.

One caveat carried forward rather than buried: this is a research framework.
It tests whether the theorem describes the chained-HotStuff *specification*
faithfully implemented. Whether any production system runs in that regime is a
separate question, and E1's answer for the two production-lineage systems
measured was no.
