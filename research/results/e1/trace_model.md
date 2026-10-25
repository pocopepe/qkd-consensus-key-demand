# E1 trace model

Definitions fixed **before** any trace was inspected. Written first so that the
hub-union fit cannot be tuned after seeing the data.

The theoretical model is pairwise: `d_t : E → ℝ₊` over unordered validator pairs,
with demand-weighted support persistence. Anything measured has to be reduced to
that, and every reduction choice is recorded here with its justification and its
alternative.

---

## 1. View

A **view** is one `(height, round)` pair — the unit within which a single leader
proposes and a quorum votes.

Rationale: the theoretical model assumes one hub rotation per view. In CometBFT a
height may contain several rounds after a timeout, and the proposer changes
between rounds. Using height alone would merge distinct proposers into one view
and inflate the hub count. Views are ordered lexicographically by
`(height, round)` and consecutive views are adjacent in that order.

Views in which no consensus message was observed are **not** dropped silently;
they are recorded as empty and excluded from persistence with the count reported.

## 2. Message

A **message** is one logical consensus-reactor message delivered from one
validator to another. Not a TCP segment, not an RPC, not a byte.

Classified as:

| class | CometBFT type | counted in D-core | counted in D-all |
|---|---|---|---|
| proposal | `Proposal` | yes | yes |
| block part | `BlockPart` | no | yes |
| prevote | `Vote` (prevote) | yes | yes |
| precommit | `Vote` (precommit) | yes | yes |
| gossip metadata | `NewRoundStep`, `HasVote`, `VoteSetMaj23`, `VoteSetBits`, `NewValidBlock` | no | yes |

**Two demand models are reported, not one.** Selecting only the convenient
message types is exactly the failure mode this experiment is meant to avoid, so
both are carried through every result:

- **D-core** — the logical consensus messages a textbook description of the
  protocol contains: proposal and votes.
- **D-all** — every inter-validator consensus-reactor message, which is what a
  QKD deployment would actually have to authenticate, since gossip metadata
  travels between the same validators and carries consensus state.

If D-core and D-all disagree, that disagreement is a result.

## 3. Validator pair

An unordered pair `{u,v}`, `u ≠ v`, both of which are **validators** (members of
the active validator set). Traffic to or from non-validator full nodes, seed
nodes, or RPC clients is excluded, because it consumes no pairwise consensus key
in the model.

Direction is discarded: `{u,v}` and `{v,u}` are the same pair, since a QKD link
is symmetric.

## 4. Demand

One unit of demand per authenticated message on the pair carrying it:

    d_t({u,v}) = number of logical consensus messages between u and v in view t

**One unit = one Wegman–Carter tag.** Not bytes. This encodes the tag-only
authentication assumption identified in `research_direction.md` §5 as assumption
9. Under one-time-pad payload encryption the weighting would be by message length
and, as measured there, `π → 1`; that regime is explicitly out of scope for E1
and is noted as a limitation rather than measured here.

A logical message split across several transport frames counts once. A block
delivered as `p` `BlockPart` messages counts as `p` messages in D-all and `0` in
D-core, because each part is separately transmitted and would separately need a
tag.

## 5. Support

    S(t) = { p ∈ E : d_t(p) > 0 }

The unweighted edge set. `|S(t)|` is the support size.

## 6. Hub, and the fit procedure

The theoretical model says `S(t) = ⋃_{h∈R(t)} star(h)`. Observe that
`S(t) ⊆ ⋃_{h∈R} star(h)` holds **iff every edge of `S(t)` has an endpoint in
`R`** — that is, iff `R` is a **vertex cover** of the support graph.

So the hub set is not a judgement call:

    m(t) := |minimum vertex cover of G_t = (V, S(t))|
    R(t) := a minimum vertex cover of G_t

Computed exactly by branch and bound (validator counts here are ≤ 16, so exact
is affordable). Where several minimum covers exist, the tie is broken
**deterministically and independently of the previous view** — lexicographically
smallest — so that `k` cannot be inflated by choosing a cover that happens to
overlap.

This gives two distinct fit qualities, both reported:

- **Containment** is exact by construction: every observed edge is covered.
- **Over-prediction residual**

      ρ(t) = ( |⋃_{h∈R(t)} star(h)| − |S(t)| ) / |⋃_{h∈R(t)} star(h)|

  is the share of edges the hub-union model *predicts* that were not observed.
  `ρ = 0` means the support is exactly a union of stars. Large `ρ` means the
  model is a poor description even though the cover exists — a star with most of
  its edges missing is not a hub.

**A configuration is declared hub-union only if `ρ` is small.** The threshold is
declared in advance: `ρ ≤ 0.15` mean across views.

## 7. Surviving hub

    k(t) := | R(t) ∩ R(t-1) |

Using the deterministic covers of §6. Reported as the mean over views, together
with its distribution, since the theory assumes `k` constant and real traces may
not oblige.

## 8. Measured persistence

    π_t = ( Σ_{p ∈ S(t-1)} d_t(p) ) / ( Σ_p d_t(p) )
    π̂   = (1/T) Σ_t π_t

Demand-weighted, matching the definition in `research_direction.md` §3, over
views `t` with non-empty support and non-empty predecessor.

## 9. Theoretical prediction

    π_theory = [ k(n-1) + m(m-k) ] / [ m(n-1) ]

evaluated at the **measured** `n`, and the measured mean `m` and `k` from §6–7.
No parameter is fitted. `n` is the active validator-set size.

Error reported as `ε = |π̂ − π_theory|`, with the interpretation bands from the
task: `<0.05` strong, `0.05–0.15` investigate, `>0.15` external-validity problem.

## 10. What would falsify the model

Declared in advance:

1. `ρ > 0.15` — the support is not a union of stars, so the model does not
   describe the graph regardless of what `π` does.
2. `ε > 0.15` while `ρ ≤ 0.15` — the graph fits but the formula does not predict
   its persistence.
3. `m` or `k` unstable across views (coefficient of variation > 0.5) — the
   constant-`m,k` assumption fails.
4. D-core and D-all giving materially different verdicts — the result depends on
   an arbitrary message-selection choice.

## 11. Known deviations from the theoretical model, recorded up front

- CometBFT **gossips** votes to all peers rather than unicasting them to the next
  proposer. If so, the support should be close to complete, `m` close to a
  minimum cover of a near-complete graph (`≈ n-1`), and `π ≈ 1`. That would be
  *consistent* with the model's all-to-all corollary, not a refutation of it, and
  it is the outcome the model predicts for Tendermint-class protocols.
- CometBFT does not pipeline in the HotStuff sense. Phase 6's pipeline sweep is
  therefore only meaningful on a chained-HotStuff implementation; if none can be
  run, the sweep is reported as not executed rather than simulated.
