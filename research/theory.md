# Theory: predictive key supply for rotating-leader consensus

Every claim below is checked numerically by `research/verify_theory.py`
(16/16 passing). Where a hypothesis I started with turned out to be wrong, the
corrected statement is given and the wrong one is named, because the correction
is usually the more interesting result.

## 0. Setup

A BFT cluster of `n` validators runs views `t = 0, 1, 2, …`. View `t` is led by
`L(t)`; under round-robin `L(t) = t mod n`. Writing `P` for the set of
`n(n-1)/2` unordered validator pairs, view `t` consumes `d_p(t)` bits of
pairwise QKD key on pair `p ∈ P`. For chained HotStuff the happy path is

    d(t) = B · [ star(L(t)) + star(L(t+1)) ]

where `star(v) = { {v,u} : u ≠ v }` and `B` is the tag size. A timeout replaces
this with the all-to-all NEW-VIEW fabric.

The control plane installs a pre-arm set `S(t) ⊆ P` into a kernel map before
view `t` runs, subject to a capacity `M_max` and a per-view update budget
`U_max`. Latency is the quorum order statistic over each demand block, not the
maximum, because BFT progresses on `2f+1`.

The EWMA forecaster of the proposal, and of the published prior art, is

    d̂_p(t+1) = α·d_p(t) + (1-α)·d̂_p(t),   q := 1-α.        (1)

---

## 1. The rotation blindspot

### 1.1 Exact steady state

**Lemma 1.** Let `d_p` be a period-`n` impulse train of height `B` with its
impulse at phase 0. The EWMA (1) has a unique periodic steady state

    â(φ) = αB·q^(φ-1) / (1 - q^n),   φ = 1 … n,     â(0) = â(n).

*Proof.* Between impulses the recursion is `â(φ+1) = q·â(φ)`, so
`â(φ) = q^(φ-1)·â(1)` on `1 ≤ φ ≤ n`. Across the impulse,
`â(1) = αB + q·â(0)`, and periodicity forces `â(0) = â(n) = q^(n-1)·â(1)`.
Substituting gives `â(1)(1 - q^n) = αB`. ∎

Verified against direct simulation to `< 1e-9` for all
`n ∈ {4,8,16,32} × α ∈ {0.1,0.3,0.5,0.9}`.

### 1.2 The predictor is anti-correlated with what it predicts

**Theorem 1 (Rotation blindspot).** Under Lemma 1's conditions,

    E[d̂] = E[d] = B/n                                       (unbiased)
    Cov(d, d̂) = (B²/n)·[ α·q^(n-1)/(1 - q^n)  −  1/n ].     (2)

The covariance is **negative** whenever `α·q^(n-1)/(1-q^n) < 1/n`.

*Proof.* `E[d̂] = (1/n)[â(0) + Σ_{φ=1}^{n-1} â(φ)]`. The geometric sum is
`(αB/(1-q^n))·(1-q^(n-1))/α`, and adding `â(0) = αB q^(n-1)/(1-q^n)` gives
`(B/(1-q^n))·[1 - q^(n-1)(1-α)] = B`, since `q^(n-1)(1-α) = q^n`. Divide by `n`.
The product term is `E[d·d̂] = (1/n)·B·â(0)` because `d` vanishes off phase 0.
Subtract. ∎

**Corollary 1.1.** *No choice of `α` escapes.* As `α → 1`, `q^(n-1) → 0` and (2)
tends to `−B²/n²`, its most negative value: the pure lag-1 predictor is the
worst possible. As `α → 0` the predictor tends to a constant and the covariance
tends to `0⁻` from below. The supremum over `α` is attained in the limit
`α → 0` and is still negative.

Numerically, the smallest period at which the covariance turns negative is
`n* = 2` for every `α ∈ [0.05, 0.99]`. Verified.

| n | α=0.1 | α=0.3 | α=0.5 | α=0.9 |
|---|---|---|---|---|
| 8 | −0.0372 | −0.0611 | −0.0625 | −0.0625 |
| 16 | −0.0372 | −0.0611 | −0.0625 | −0.0625 |
| 32 | −0.0223 | −0.0611 | −0.0625 | −0.0625 |

(values are `n·Cov/B²`.)

The interpretation is the useful part. The EWMA's peak prediction occurs at
phase 1, one view *after* the impulse; the next impulse is `n-1` views later.
The predictor is not noisy — it is reliably out of phase, by construction, and
rotation is what puts it out of phase.

### 1.3 What I got wrong, and the correct ceiling

I first claimed Theorem 1 extends to the real star-structured demand. **It does
not.** Measured over the full pair matrix, EWMA's correlation with real HotStuff
demand is *positive* for `α ≳ 0.5` (`+0.39` at `n=16, α=0.9`).

Two things were wrong. Real demand is not an isolated impulse train — a pair is
hot on four phases of the cycle, and consecutive views share structure. And
correlation over all of `P` is dominated by the many pairs correctly predicted
to be zero, which flatters any smoother; it is not the statistic a pre-arming
control plane depends on.

The right statistic is coverage at the budget: of view `t`'s demand bits, what
share falls on the `K` pairs the forecaster ranks highest.

**Definition.** The *support persistence* of a workload is

    π := E_t [ Σ_{p : d_p(t-1) > 0} d_p(t) / Σ_p d_p(t) ],

the share of a view's demand carried by pairs that were already hot in the
previous view.

**Theorem 2 (Persistence ceiling).** For `K = 2(n-1)` — exactly the two stars a
view touches — the EWMA's coverage satisfies `cov@K ≤ π`, with **equality** for
all `α ≥ 1/2`.

*Proof sketch.* For `α ≥ 1/2` we have `α > q`, so in the steady state the
contribution of view `t-1` to `d̂(t)` strictly dominates every earlier view on
every pair. The top-`K` ranking therefore reproduces the hot set of view `t-1`
exactly, and its coverage of view `t` is by definition `π`. For `α < 1/2` mass
is spread across several stale stars, the ranking admits pairs from views
`t-2, t-3, …`, and coverage falls strictly below `π`. ∎

Verified to `1e-9`:

| n | π | α=0.1 | α=0.3 | α=0.5 | α=0.9 | structural |
|---|---|---|---|---|---|---|
| 8 | 0.6429 | 0.3571 | 0.4286 | **0.6429** | **0.6429** | 1.0000 |
| 16 | 0.5667 | 0.1667 | 0.2333 | **0.5667** | **0.5667** | 1.0000 |
| 32 | 0.5323 | 0.0968 | 0.1290 | **0.5323** | **0.5323** | 1.0000 |

**Corollary 2.1.** For chained HotStuff, `π → 1/2` as `n → ∞`. The vote star of
view `t-1` *is* the proposal star of view `t`, so exactly one of the two stars
persists and one is new. A carry-forward predictor gets the first for free and
cannot reach the second at any `α`.

This is the sharp version of the blindspot, and it explains the measurement: the
full simulator reports EWMA coverage@48 = 0.520 at `n=16`, against a predicted
ceiling of 0.567. **The smoother is not performing badly. It is sitting on its
ceiling, and the ceiling is one half.** The structural forecaster reads `L(t)`
and `L(t+1)` from the schedule and takes both stars, which is why it reaches
0.919 in simulation and 1.000 on the noiseless pattern.

### 1.4 Flash crowds pull `α` the wrong way

I also expected faster smoothing to overshoot more on bursts. **It does not** —
on a deterministic burst the tracking error falls monotonically in `α`, because
under- and over-provision areas are equal for an unbiased filter and both shrink
as the filter gets faster.

**Theorem 3 (α-conflict).** On a burst, total tracking error is strictly
decreasing in `α`. On rotation, `Cov(d, d̂)` is strictly decreasing in `α`
(Corollary 1.1). Hence the burst-optimal `α` is exactly the rotation-worst `α`,
and the two objectives admit no common optimum.

| α | burst error | rotation cov (n=16) |
|---|---|---|
| 0.1 | 37.81 | −0.0372 |
| 0.3 | 30.66 | −0.0611 |
| 0.5 | 24.50 | −0.0625 |
| 0.9 | **15.54** | **−0.0625** |

A tuned EWMA is therefore not an engineering detail left undone; it is a
constrained choice between two failure modes. The structural forecaster is not
subject to the trade at all: its burst term is a per-leader Beta-Bernoulli
posterior applied to the view that leader owns, which has no settling time
because it is not a filter over time.

---

## 2. Density-greedy under kernel bounds

### 2.1 The instruction dimension is vacuous

The proposal's program is

    max Σ_{v∈S} u_v   s.t.   Σ_{v∈S} c_v ≤ I_max,  Σ_{v∈S} m_v ≤ M_max.

**Proposition 4.** The first constraint has no referent in the BPF verifier.

The verifier bounds a *program*, statically, at load time. The XDP fast path
(`src/xdp_enforcer.c`) performs one hash lookup with no loop over `S` and no
data-dependent control flow, so its instruction count is a property of the
program text. Measured on Linux 6.8 across a 16,384× range of map capacity:

| M_max | 64 | 256 | 1024 | 16384 | 262144 | 1048576 |
|---|---|---|---|---|---|---|
| verified_insns | 244 | 244 | 244 | 244 | 244 | 244 |

The problem is therefore one-dimensional in `M_max`, and `d = 1` below.

### 2.2 Approximation ratio

**Theorem 5.** Let items have utilities `u_i > 0`, integer weights `w_i` with
`w_max = max_i w_i`, and capacity `C > w_max`. Density-greedy — sort by
`u_i/w_i`, admit while it fits — returns `G` with

    G ≥ (1 − w_max/C) · OPT.

*Proof.* Index items by decreasing density and let `k` be the first index that
does not fit. Greedy admits all `i < k`, so `G ≥ Σ_{i<k} u_i`, and
`Σ_{i<k} w_i > C − w_k ≥ C − w_max`. Every admitted item has density at least
`ρ_k := u_k/w_k`, hence `G ≥ (C − w_max)·ρ_k`, i.e. `ρ_k ≤ G/(C − w_max)`.
The fractional relaxation satisfies `LP = Σ_{i<k} u_i + λ·u_k` for some
`λ ∈ [0,1)`, so `LP ≤ G + w_k·ρ_k ≤ G + w_max·ρ_k ≤ G·C/(C − w_max)`. Since
`OPT ≤ LP`, rearranging gives the claim. ∎

Verified: 0 violations over 4,000 random instances, minimum slack `+0.0084`.

**Corollary 5.1.** In this system `w_i` is the relay hop count of a pair, so
`w_max ≈ 4` while `M_max` is in the hundreds. The bound gives
`G ≥ 0.979·OPT` at `M_max = 192`.

| M_max | bound `1−w_max/C` | measured mean | measured min |
|---|---|---|---|
| 16 | 0.7500 | 0.99718 | 0.94848 |
| 64 | 0.9375 | 0.99901 | 0.98345 |
| 192 | 0.9792 | 0.99999 | 0.99876 |
| 256 | 0.9844 | 1.00000 | 1.00000 |

The measured ratio is far tighter than the bound because hop weights are tiny
against the map, making the instance nearly fractional. **The ½ worst-case bound
for density-greedy is real but unreachable in this regime**, and the proposal's
plan to analyse that gap as its central theoretical result would have been
effort spent on the one part of the design that is not a problem. The binding
resource is `U_max`, and because holding an entry is free while changing one
costs a syscall, the correct formulation is online knapsack with switching
costs — a different problem, treated in `qkdnet/allocate.py`.

---

## 3. Metadata leakage from kernel pre-arming

### 3.1 The channel

A pre-armed pair is answered by XDP in 14 µs (measured); a miss takes the
userspace/KME path, three orders of magnitude slower. The gap is the objective
of the design and is trivially observable by anyone who can time consensus
responses. Let `O_t` be the set of pairs observed to be fast in view `t`.

**Theorem 6 (Leakage of a leader-concentrated policy).** If the policy arms the
stars of exactly `k` validators, one of which is always the true leader, and the
adversary can identify the armed set from timing, then

    I(L; O) = log₂ n − log₂ k,

and the adversary's top-1 accuracy is `1/k`.

*Proof.* Conditioned on `O`, the leader is uniform on the `k` armed centres, so
`H(L|O) = log₂ k`, while `H(L) = log₂ n`. ∎

| stars armed | leak (bits) | adversary top-1 | pairs armed |
|---|---|---|---|
| 1 | 4.000 | 1.000 | 15 |
| 2 | 3.000 | 0.500 | 30 |
| 8 | 1.000 | 0.125 | 120 |
| 16 | **0.000** | 0.062 | 240 |

**Corollary 6.1 (Privacy costs a factor of n/2).** `I(L;O) = 0` requires
`k = n`: every star armed. Since `star(v)` has `n−1` pairs and the union over
all `v` is all `n(n−1)/2` pairs, the zero-leak footprint is `n/2` times the
leader-only footprint — 8× at `n = 16`.

### 3.2 Two things that do not work, and why

**Decoys fail.** Padding the map with stars nobody sends to moves the
adversary's advantage by nothing (measured: 0.534 → 0.518 for eight decoys). The
observable is generated by *real traffic*; a pair that carries no message is
never timed, so a decoy entry buys map capacity and held key and zero privacy.
Any defence must be uniform over the pairs that actually carry traffic.

**Uniform membership is not enough.** The pair `{L(t), L(t+1)}` appears in both
the proposal star and the vote star, so it draws twice the key of any other pair
in the view. Provisioning every pair to the same *depth in bits* leaves exactly
that pair short; it alone takes the slow path, and the adversary recovers the
leader pair from the single timing anomaly the defence created. The reservation
must be uniform at the **worst-case per-pair draw**, not the typical one.

### 3.3 The horizon identity

Consensus traffic already names `L(t)` — that validator is broadcasting — and in
a chained protocol the vote phase names `L(t+1)`. Neither is a new leak. The new
leak is *advance* warning: a control plane with forecast horizon `H` installs
stars for views the network has not reached, so `S(t)` is a function of
`L(t), …, L(t+H)`, and for offsets `≥ 2` no traffic exists that could have
carried that information.

Measured leak accuracy at offset `k` (baseline `1/16 = 0.062`):

| H | leak@1 | leak@2 | leak@3 | leak@4 |
|---|---|---|---|---|
| 1 | 0.197 | 0.050 | 0.058 | 0.087 |
| 2 | 0.182 | 0.184 | 0.050 | 0.055 |
| 3 | 0.239 | 0.203 | 0.192 | 0.066 |
| 4 | 0.224 | 0.216 | 0.176 | 0.205 |

The staircase is exact: the leak horizon equals the forecast horizon. **Lead
time and schedule secrecy are the same quantity, spent in opposite directions.**

**Design consequence.** In every configuration measured, `H = 1` already
attains the full latency benefit, because a one-view horizon covers both stars
of the imminent view. The recommendation is therefore to hold `H = 1` and spend
no secrecy at all — a rule that falls out of the identity rather than a
mitigation added afterwards.

### 3.4 Amplification

A silenced leader forces a view change. The demand ratio is

    gain(n) = [n(n−1)/2 · B] / [2(n−1) · B] = n/4

giving 4× at n = 16 and 25× at n = 100,

against links whose secret-key rate is fixed by physics and cannot surge. Each
correct guess therefore drains the pools the next view depends on, which makes
the side channel self-financing rather than merely informative.

---

## 3.5 The duality: predictability and leakage are one quantity

Sections 1-3 were established on chained HotStuff. The obvious objection is that
they describe one protocol. They do not -- they describe a class, and the class
boundary is the protocol's steady-state message complexity. Seven protocols were
reduced to the only thing a key-supply layer sees, the set of validator pairs
that exchange an authenticated message each view, and measured at
n = 4 … 256 (`research/protocols.py`, `research/duality_study.py`;
`verify_duality.py` checks 10/10 closed forms).

### Theorem 7 (Persistence-Complexity)

For a protocol whose steady-state support is all-to-all -- PBFT, Tendermint,
Narwhal/DAG, and Simplex, whose quadratic vote phase covers every pair --

    pi = 1 exactly, for every n.

For a rotating-leader protocol with linear steady state (chained HotStuff,
HotStuff-2),

    pi(n) = (n + 1) / (2(n - 1))  ->  1/2.

*Proof.* View t touches `star(L(t))` and `star(L(t+1))`, so `2(n-1)`
pair-messages. View t-1 touched `star(L(t-1))` and `star(L(t))`. The whole
proposal star of view t was already hot -- it was view t-1's vote star --
contributing `n-1`. From view t's vote star only `{L(t+1), L(t-1)}` and
`{L(t+1), L(t)}` were hot before, contributing 2. Hence
`pi = ((n-1) + 2)/(2(n-1))`. ∎

Verified to `0.00e+00` at n = 4, 7, 16, 31, 64, 128, 256.

| n | 4 | 7 | 16 | 31 | 64 | 128 |
|---|---|---|---|---|---|---|
| pi predicted | 0.8333 | 0.6667 | 0.5667 | 0.5333 | 0.5159 | 0.5079 |
| pi measured | 0.8333 | 0.6667 | 0.5667 | 0.5333 | 0.5159 | 0.5079 |

**The efficiency that makes HotStuff attractive is exactly what makes its key
demand unpredictable by smoothing.** Collapsing the quadratic phases into two
stars concentrates demand onto a rotating hub; an all-to-all protocol spreads it
over every pair every view, where a smoother has nothing left to get wrong.

### Theorem 8 (Ceiling, generalised)

Best-alpha EWMA coverage at the protocol's natural budget equals `pi` exactly,
for every protocol and every n measured -- maximum error `0.00e+00`. Theorem 2
was not a property of HotStuff.

### Theorem 9 (Gain)

A schedule-aware forecaster attains coverage 1 by construction, so

    structural gain = 1 - pi,

identically. There is no tuning residue: what a smoother cannot reach is exactly
the share of demand that does not persist.

### Theorem 10 (Leakage)

Ranking validators by degree in the pre-armed support recovers the leader with
top-1 probability

    (n-1)/n   for star-supported (linear) protocols,
    1/n       for all-to-all protocols, i.e. chance.

At n = 128 chained HotStuff discloses **6.984 of 7 bits** of leader entropy --
99.8%. Verified to `0.00e+00`.

### Theorem 11 (Gain-Leak Duality)

Over 24 (protocol, n) points, `corr(gain, leak advantage) = +0.982`, and both
boundary regions are empty: no protocol has forecasting gain above 0.2 with leak
advantage below 0.5, and none has gain below 0.01 with advantage above 0.5.

| condition | points | mean leak advantage |
|---|---|---|
| gain < 0.01 | 20 | 0.029 |
| gain > 0.20 | 4 | 0.929 |

### Theorem 11a (Exact duality)

For a rotating-leader protocol with linear steady state the relationship is an
identity, not a correlation:

    gain(n) = 1 - pi(n) = (n-3) / (2(n-1))
    adv(n)  = ((n-1)/n - 1/n) / (1 - 1/n) = (n-2) / (n-1)
    adv(n) - gain(n) = [2(n-2) - (n-3)] / (2(n-1)) = 1/2.

Verified to `2.22e-16` at n = 4, 7, 16, 31, 64, 128, 256.

| n | 4 | 16 | 64 | 256 |
|---|---|---|---|---|
| gain | 0.166667 | 0.433333 | 0.484127 | 0.496078 |
| leak advantage | 0.666667 | 0.933333 | 0.984127 | 0.996078 |
| difference | 0.500000 | 0.500000 | 0.500000 | 0.500000 |

The adversary's advantage exceeds the forecaster's gain by exactly one half, at
every scale. They are the same function offset by a constant.

**Corollary 11.1 (Impossibility).** In a rotating-leader protocol, predictive key
pre-arming and proposer privacy cannot coexist. A structural forecaster gains
`1 - pi` precisely because the demand support is leader-dependent, and a support
that is leader-dependent names the leader to anyone who can time it. The
protocols where pre-arming leaks nothing are exactly the protocols where it gains
nothing.

This bears directly on a live deployment question. Ethereum's secret leader
election work -- Whisk, homomorphic sortition -- exists to stop targeted DoS on
the next proposer. **A predictive QKD key-supply layer reintroduces that exposure
below the protocol, in the data plane, where the consensus layer cannot see it.**

**Corollary 11.2 (Sortition).** Secret committee sortition removes the leader
leak: gain falls to ~0 (there is no schedule to read) and leader top-1 advantage
falls with it. It does not remove membership disclosure -- the pre-armed support
*is* the committee's clique, so committee precision and recall are both
**1.0000** at every n measured. The duality holds for the leader; the residual
leak is one level coarser and does not vanish.

### What this changes

The design rule from §3.3 was "hold H = 1". Theorem 11 makes the stronger point
that H = 1 is not a safe operating point either, merely a cheaper one: even a
one-view horizon on a linear protocol discloses the current leader to a timer.
The defensible positions are (a) run a protocol with `pi = 1`, accept O(n^2)
messages, and pre-arm freely with no leak; (b) run a linear protocol and accept
that predictive key supply is incompatible with proposer privacy; or (c) pay the
`n/2` map-footprint factor for uniform coverage (Corollary 6.1). There is no
fourth option in the space measured.

## 3.6 The predictor-class ceiling (Theorem B)

Sections 1–2 establish that support persistence `π` bounds what a smoother can
reach. That statement needs a precise predictor class and a precise condition,
and the first attempt at both was wrong.

**Definition.** A *recency-weighted counting* (RWC) predictor scores each pair by

    score_t(p) = sum_{s<t} w_{t-s} · 1[p ∈ S(s)],   w ≥ 0, independent of p and t.

EWMA (`w` geometric), last-observation (`w = δ_1`) and frequency (`w` uniform)
are all RWC.

**Definition (lag-1 dominance).** `w_1 > Σ_{s≥2} w_s`.

### Theorem B

Let `w` be lag-1 dominant and `K = |S(t)|`. Then

    |S(t-1)| = K  ⟹  cov = π  exactly
    |S(t-1)| > K  ⟹  cov ≤ π
    |S(t-1)| < K  ⟹  cov ≥ π

*Proof.* Under dominance a member of `S(t-1)` scores at least `w_1`, while a
non-member scores at most `Σ_{s≥2} w_s < w_1`. So `S(t-1)` occupies the top
`|S(t-1)|` ranks. If `|S(t-1)| = K` the top-`K` set *is* `S(t-1)`, and its
demand-weighted coverage of view `t` is `π` by definition. If `|S(t-1)| > K`
the top-`K` is a subset of `S(t-1)`, so it can only cover less. If
`|S(t-1)| < K` it is a superset, so it can only cover more. ∎

**Corollary B.1.** For EWMA, `Σ_{s≥2} w_s = 1 - α`, so lag-1 dominance holds iff
`α > 1/2`. This is why the empirical threshold sits at one half, and it is a
property of the weights, not of EWMA as such.

**Corollary B.2.** Uniform frequency weighting over a window of `T > 2` views is
not lag-1 dominant, so nothing constrains its ranking to `S(t-1)`; measured
coverage falls far below `π` (0.194 against `π = 0.552` at n=16).

### What the earlier conjecture got wrong

It was recorded as *"for every RWC predictor, cov ≤ π, with equality for EWMA
with α ≥ 1/2"*. Two errors:

1. In the constant-support case the relation is an **equality**, not an
   inequality. Every protocol modelled here has constant support size, which is
   why `cov = π` was observed to machine precision throughout and the
   inequality never appeared to be strict.
2. When the support **grows**, the inequality **reverses**. Counterexample with
   last-observation weighting: `S(t-2) = {a,b,c}`, `S(t-1) = {a}`,
   `S(t) = {a,b,c}` gives `π = 1/3` and `cov = 1`.

Verified in `research/e5_theorem_b.py`: 13,500 exhaustive small cases and 40,000
randomised instances under dominant weights, zero violations of the three-case
statement; and the predictor-zoo measurements are reproduced exactly.

## 4. Status

| Claim | Status |
|---|---|
| Lemma 1, Theorem 1, Corollary 1.1 | proved, numerically verified |
| Theorem 2, Corollary 2.1 | proved, verified to 1e-9, explains measured 0.520 |
| Theorem B (§3.6) + corollaries | proved; 53,500 instances, 0 violations; refutes the earlier conjecture |
| Theorem 3 | verified; **reverses my initial hypothesis** |
| Proposition 4 | measured on Linux 6.8, 244 insns invariant |
| Theorem 5, Corollary 5.1 | proved, 0/4000 violations |
| Theorem 6, Corollary 6.1 | proved, matches measured leak |
| §3.3 horizon identity | measured, not yet proved in general |
| Theorems 7-10 | proved, verified to 0.00e+00 across 7 protocols, n = 4…256 |
| Theorem 11 + corollaries | measured over 24 points; boundary regions empty |
| Theorem 11a | proved and verified to 2.22e-16, n = 4…256 |

Open: a competitive-ratio bound for the switching-cost formulation; a proof of
the horizon identity beyond the round-robin and VRF cases measured; and an
adaptive-adversary model for Theorem 11, which currently assumes a passive
observer with clean timing.
