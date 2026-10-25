# Prediction lock — C1: Proposition 1 under real, temporally correlated vote loss (Cosmos Hub)

Written 2026-09-21T20:12Z, **before the held-out range is fetched**. Amendments are dated and appended.

## Question

Proposition 1 is a first-order result derived for losses that interact only through the per-view accounting.
Real absence is persistent (Cosmos Hub: a validator absent in one block is absent in the next with probability
0.592 against 0.0067 under independence). Does the proposition still predict the persistence cost of real,
correlated loss?

## Design (fixed)

- Loss process: Cosmos Hub commit records. Validator v's vote in view t is lost iff v is absent from the commit
  of block t. Held-out range: heights **27,846,637 – 28,046,636** (200,000 consecutive blocks), drawn with seed
  `cosmos-bulk-select-2026-09-22` from the node's retained history, clear of the prune horizon, the chain tip,
  and all 30 development windows (plan: ../cosmos/raw_bulk/_plan.json). Fetched by ../cosmos/cosmos_bulk_fetch.py
  in 100 chunks of 2000 blocks; each chunk is one analysis window.
- Simulation (chain_model.simulate): chained rotation with complete proposal stars; votes to the next leader;
  demand counts messages. Validator sets per window: 'random' (seeded sample of n) and 'stress' (the n most often
  absent, excluding any absent from more than half the window, which are offline and could not form a quorum).
  Schedules: round-robin ('rr') and stake-weighted random with the validators' voting power ('stake', repeats
  allowed). n in {16, 32, 64}.
- Statistic: loss effect Delta_sim = pi(real absences) - pi(same leader sequence, no loss); predicted
  Delta_pred = (share of views with four distinct leaders) x (Proposition 1 at the measured per-role rates on those
  views - Corollary 1). Pooled relative error per cell: R = sum|Delta_sim - Delta_pred| / sum|Delta_sim|.

## Predictions and bands (constants in c1_verdicts.py)

| ID | Prediction | Band |
|---|---|---|
| **C1A** | Under round-robin, Proposition 1 predicts the loss effect of real correlated absence | R <= 0.15 in every round-robin cell (random and stress, n = 16, 32, 64); a cell whose mean \|Delta_sim\| < 1e-4 is reported but not scored |
| C1B | Stake-weighted schedules with repeated leaders are outside Proposition 1's domain | descriptive: R reported per cell with its distinct-leader share |

Band rationale: on development data (the 30 windows of 300 blocks) R was 0.003–0.05 in the round-robin cells,
while the loss effect itself was 3.8e-4 to 1.7e-3; a band of 0.15 is three times the worst development value and
far below R = 1, which is what ignoring the loss would give.

## Theory delivered with this lock (verified, not a prediction)

chain_model.py (self-check passes): an exact finite-sum expectation of pi under independent per-role loss, and the
complete first-order form. Proposition 1, a ratio of expectations, differs from the per-view average of
Definition 4 at first order by a term of order (loss)/n^2 (e.g., 7.8e-5 at n = 16 and 1% loss per sender); the
remainder after the complete first-order form is second order.

## Data that existed when this lock was written

Development only: the earlier campaign's 30 windows x 300 blocks (../cosmos/raw/), analysed to calibrate the
band and to fix the stress-selection rule (a first version selected permanently offline validators, giving
8.3 lost votes per view out of 15, which no quorum can survive). The held-out range has not been fetched.

## Hashes at lock time

    chain_model.py               ae4e9cb34e78496ed76cf43c1ed95fea96b5a353f484468dfaa4553c4be7dc1c
    cosmos_loss_sim.py           115a74d9fcb79a86133252d259c01ff15448e75f031e531b6cbd218db060e0d4
    c1_verdicts.py               52f3a1a18efeb8d0f4d26e409262018b47fd9ca307b2172625fa2ca89cf070ae
    ../cosmos/cosmos_bulk_fetch.py 79769405aed2863d5689795be848d2ff75b8ed90949caf8a43d0c37ded2a3264
    ../cosmos/raw_bulk/_plan.json  a1dac243353d0814f4773cbf1ede5d44275f8df8b1d79c19a51955452d549742
