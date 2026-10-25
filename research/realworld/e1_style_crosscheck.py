#!/usr/bin/env python3
"""Secondary corroborating check (per PREDICTION_LOCK_H2_H3.md item #4):
does the AGGREGATE measured persistence on real Aptos data sit closer to
pi_p (participation-corrected) than to the full-participation pi(n,2,1)?

Reuses research/e1_analyze.py's analyze() FUNCTION DIRECTLY, unmodified --
the same frozen, previously-verified code that produced the E1 results in
the main paper. This is not a reimplementation; it is the existing tool
pointed at new data.

Honest disclosure, stated once here and not hidden: the PROPOSE side of
every view is ASSUMED complete (broadcast reaches all n-1 others), because
proposal reception isn't observable from on-chain data -- only the VOTE
side (who actually signed) is measured from previous_block_votes_bitvec.
analyze() has no way to distinguish assumed from measured edges; it treats
whatever records it's given as ground truth for the support. That
asymmetry is inherent to what Aptos's public API exposes, not a shortcut
taken here, and was already flagged in PREDICTION_LOCK_H1.md / H2_H3.
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from e1_analyze import analyze  # frozen, unmodified, reused directly

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pi_p_model import pi_p_closed_form, pi_original

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")


def build_records(raw: dict) -> tuple[list[tuple], int]:
    """(h, r, src, dst, type) tuples matching e1_analyze.build_views's
    expected shape. h is a synthetic per-round slot (round, 0) since Aptos
    round numbers alone are already a valid, monotonic view key -- no real
    "height" concept needed here, e1_analyze.py doesn't care about the
    semantics, only that (h, r) sorts in true temporal order."""
    n = len(raw["addr_to_idx"])
    txs = raw["rounds_raw"]
    proposer_of_round: dict[int, str] = {int(tx["round"]): tx.get("proposer") for tx in txs}
    idx_of = raw["addr_to_idx"]

    def decode(byte_list, n):
        bits = "".join(f"{b:08b}" for b in byte_list)
        return {i for i in range(min(n, len(bits))) if bits[i] == "1"}

    records = []
    all_idx = set(range(n))
    for tx in txs:
        own_round = int(tx["round"])
        voted_round = own_round - 1
        leader_this = proposer_of_round.get(voted_round)  # L(t): proposes voted_round
        leader_next = proposer_of_round.get(own_round)    # L(t+1): this tx's own proposer
        if leader_this is None or leader_next is None:
            continue  # boundary round, missing one side's proposer info
        leader_this_idx = idx_of.get(leader_this)
        if leader_this_idx is None:
            continue
        # Propose star: L(t) -> everyone else. ASSUMED complete, not measured.
        for v in all_idx:
            if v != leader_this_idx:
                records.append((voted_round, 0, leader_this_idx, v, "Propose"))
        # Vote star: actual signers -> L(t+1). MEASURED from the bitvec.
        signed = decode(tx.get("previous_block_votes_bitvec", []), n)
        leader_next_idx = idx_of.get(leader_next)
        for v in signed:
            if leader_next_idx is not None and v != leader_next_idx:
                records.append((voted_round, 0, v, leader_next_idx, "Vote"))
    return records, n


def main() -> int:
    print("=" * 78)
    print("Secondary check: aggregate measured pi vs pi_p, real Aptos data")
    print("(reusing research/e1_analyze.py's analyze(), unmodified)")
    print("=" * 78)
    print("\nCAVEAT stated up front: propose-side edges are ASSUMED complete,")
    print("not measured -- Aptos exposes vote bitmaps, not proposal reception.")
    print("Only the vote side reflects real observed participation.\n")

    raw_files = sorted(glob.glob(os.path.join(RAW_DIR, "epoch_*.json")))
    if not raw_files:
        print("No raw epoch data yet.")
        return 0

    for path in raw_files:
        raw = json.load(open(path))
        records, n = build_records(raw)
        result, _ = analyze(records, n, types={"Propose", "Vote"}, label=f"aptos_{raw['epoch']}")
        # participation used for pi_p: fraction of the vote-star that's present
        # (n-1 possible signers per round; measured mean already computed
        # elsewhere, recomputed here independently and simply from the same
        # records for a self-contained check)
        vote_edges = sum(1 for r in records if r[4] == "Vote")
        propose_edges = sum(1 for r in records if r[4] == "Propose")
        mean_p = vote_edges / max(1, propose_edges) if propose_edges else float("nan")

        pi_full = pi_original(n, 2, 1)
        pi_participation_corrected = pi_p_closed_form(n, mean_p) if mean_p == mean_p else float("nan")

        print(f"epoch {raw['epoch']}  (n={result['n']}, {result['views']} views, "
              f"m_mean={result['m_mean']:.3f}, k_mean={result['k_mean']:.3f}, "
              f"rho_mean={result['rho_mean']:.4f})")
        print(f"  measured aggregate pi:        {result['pi_measured']:.4f} "
              f"(sd={result['pi_sd']:.4f})")
        print(f"  pi(n,2,1) full-participation: {pi_full:.4f}  "
              f"|diff|={abs(result['pi_measured']-pi_full):.4f}")
        print(f"  pi_p(n, measured p={mean_p:.4f}): {pi_participation_corrected:.4f}  "
              f"|diff|={abs(result['pi_measured']-pi_participation_corrected):.4f}")
        closer = "pi_p (participation-corrected)" if \
            abs(result['pi_measured']-pi_participation_corrected) < abs(result['pi_measured']-pi_full) \
            else "pi (full participation)"
        print(f"  measured aggregate pi sits closer to: {closer}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
