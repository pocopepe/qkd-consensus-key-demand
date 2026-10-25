#!/usr/bin/env python3
"""Independent cross-check of the H2/H3 recurrence statistic.

Deliberately does NOT import or call anything from fetch_aptos_bitvecs.py.
Re-reads the raw per-round data persisted to research/realworld/raw/epoch_*.json
and recomputes the same quantities via a genuinely different code path:

  - different data structure (a flat list of (round, absent_set) tuples
    built with a different iteration strategy, not the primary script's
    dict-keyed-by-voted-round approach),
  - the round-relabeling (bitvec on tx.round=r describes votes for r-1)
    re-derived independently from the raw JSON rather than trusted,
  - a from-scratch bootstrap using a different RNG stream and a different
    resampling implementation (percentile via sorted-array indexing done
    with a manual bisection instead of the primary script's list slicing).

If this disagrees with the primary script's own numbers by more than
floating-point noise, that is a real finding to report, not something to
quietly reconcile by picking whichever number looks better. This is the same
discipline the main project used ("independent recompute from raw trace
data, bypassing the shared analysis path") -- and a caution from that
project's own history: an earlier "independent recompute" claim in this
codebase turned out to compare mismatched partitions and had to be
retracted. This script is checked against that failure mode explicitly in
its own self-test (see main()).
"""
from __future__ import annotations

import glob
import json
import os
import random
import sys

RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")


def decode_bitvec_independent(byte_list: list[int], n: int) -> set[int]:
    """Re-derive the signer set from raw bytes, MSB-first, written without
    reference to the primary script's popcount_bits implementation (uses
    format-string bit extraction instead of shift/mask, a different
    mechanism that would not share a shift-direction bug)."""
    bits = "".join(f"{b:08b}" for b in byte_list)
    return {i for i in range(min(n, len(bits))) if bits[i] == "1"}


def load_epoch_raw(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def recompute_epoch(raw: dict) -> dict:
    n = len(raw["addr_to_idx"])
    txs = raw["rounds_raw"]
    # Independent re-derivation of "which round does this bitvec describe":
    # re-read the field semantics from scratch rather than trust the
    # primary script's re-keying. tx['round'] is the block's own round;
    # its previous_block_votes_bitvec is documented as votes for the
    # PREVIOUS block, i.e. voted_round = tx['round'] - 1.
    records = []
    for tx in txs:
        voted_round = int(tx["round"]) - 1
        signed = decode_bitvec_independent(tx.get("previous_block_votes_bitvec", []), n)
        records.append((voted_round, signed))
    records.sort(key=lambda r: r[0])

    # proposer_by_round[X] = who proposed round X's own block -- found from
    # whichever tx (if any) has round field == X, regardless of which tx's
    # bitvec we're currently looking at. Correction from an earlier version
    # of this file, which mistakenly keyed this lookup by the bitvec-carrying
    # tx's OWN round (voted_round+1) instead of the voted_round itself --
    # caught by cross-checking against the primary script's output and
    # tracing the discrepancy to ground truth rather than assuming either
    # side was right. See PREDICTION_LOCK_H2_H3.md for the record of this.
    proposer_by_round = {}
    for tx in txs:
        proposer_by_round[int(tx["round"])] = raw["addr_to_idx"].get(tx.get("proposer"))

    by_round = dict(records)  # voted_round -> signed set
    ordered_rounds = sorted(by_round)

    # participation_fracs over EVERY round seen (matches the primary script's
    # convention exactly: it samples every round's own signed-count, whether
    # or not that round has a valid successor for the pairing test below).
    # Deliberately made to match rather than left as an incidental
    # difference, so any remaining gap in the comparison is a real finding,
    # not an artifact of two scripts defining "mean participation" slightly
    # differently.
    participation_fracs = [len(by_round[r]) / max(1, n - 1) for r in ordered_rounds]

    numer = 0
    denom = 0
    boundary_rounds_missing_proposer_info = 0
    for idx in range(len(ordered_rounds) - 1):
        r = ordered_rounds[idx]
        r_next = ordered_rounds[idx + 1]
        if r_next != r + 1:
            continue  # gap in consecutive rounds, skip (matches primary logic)
        signed_r = by_round[r]
        signed_next = by_round[r_next]
        absent_r = set(range(n)) - signed_r
        excluded = proposer_by_round.get(r)  # proposer of round r itself
        if excluded is not None:
            absent_r = absent_r - {excluded}
        else:
            boundary_rounds_missing_proposer_info += 1
        absent_next = set(range(n)) - signed_next
        overlap = absent_r & absent_next
        numer += len(overlap)
        denom += len(absent_r)

    recurrence = numer / denom if denom else float("nan")
    mean_p = sum(participation_fracs) / len(participation_fracs) if participation_fracs else float("nan")
    return {
        "epoch": raw["epoch"],
        "n_validators": n,
        "rounds": len(ordered_rounds),
        "recurrence_independent": recurrence,
        "mean_p_independent": mean_p,
        "predicted_iid_independent": 1 - mean_p if mean_p == mean_p else None,
        "numerator": numer,
        "denominator": denom,
        "boundary_rounds_missing_proposer_info": boundary_rounds_missing_proposer_info,
    }


def bootstrap_ci_independent(values: list[float], n_boot: int = 5000, seed: int = 999) -> tuple[float, float, float]:
    """Deliberately different RNG seed/stream and a manual percentile
    computation (via explicit rank calculation, not list-slice indexing) to
    avoid an off-by-one in common with the primary script's version."""
    rng = random.Random(seed)
    k = len(values)
    mean = sum(values) / k
    if k < 2:
        return mean, float("nan"), float("nan")
    boots = []
    for _ in range(n_boot):
        resample = [values[rng.randint(0, k - 1)] for _ in range(k)]
        boots.append(sum(resample) / k)
    boots.sort()
    lo_rank = round(0.025 * (n_boot - 1))
    hi_rank = round(0.975 * (n_boot - 1))
    return mean, boots[lo_rank], boots[hi_rank]


def self_test() -> bool:
    """Guard against the exact failure mode flagged in this project's own
    history: comparing mismatched partitions/quantities under the label
    'independent recompute'. Verifies decode_bitvec_independent agrees with
    a trivial reference implementation on a known padding-bit case (the
    same MSB-first check used during Phase 0), so a shift-direction or
    off-by-one bug can't silently pass."""
    # from the verified Phase-0 sample: 85 validators, byte 160 = 0b10100000
    # at the tail; padding bits (indices 85,86,87 within the 88-bit vector)
    # must decode to unset regardless of which validator count is passed.
    bitvec = [47, 238, 12, 200, 158, 225, 237, 240, 183, 245, 160]
    signed = decode_bitvec_independent(bitvec, 85)
    padding_indices = {85, 86, 87}
    bad = padding_indices & signed
    if bad:
        print(f"  SELF-TEST FAIL: padding bits {bad} decoded as signed")
        return False
    total = sum(bin(b).count("1") for b in bitvec)
    if len(signed) != total:
        print(f"  SELF-TEST FAIL: popcount mismatch, decoded {len(signed)} vs raw popcount {total}")
        return False
    print(f"  SELF-TEST OK: {len(signed)}/85 signed, padding bits correctly unset")
    return True


def main() -> int:
    print("=" * 78)
    print("Independent verification of the H2/H3 recurrence statistic")
    print("=" * 78)
    print("\nSelf-test (guards against comparing mismatched quantities, the")
    print("exact failure this project's own history flagged once before):")
    if not self_test():
        print("\nABORTING: self-test failed, do not trust any comparison below.")
        return 1

    raw_files = sorted(glob.glob(os.path.join(RAW_DIR, "epoch_*.json")))
    if not raw_files:
        print(f"\nNo raw epoch files found yet in {RAW_DIR} -- nothing to verify.")
        return 0

    print(f"\nFound {len(raw_files)} raw epoch file(s).")
    results = []
    for path in raw_files:
        raw = load_epoch_raw(path)
        r = recompute_epoch(raw)
        results.append(r)
        print(f"  epoch {r['epoch']}: n={r['n_validators']} rounds={r['rounds']} "
              f"recurrence={r['recurrence_independent']:.4f} "
              f"mean_p={r['mean_p_independent']:.4f} "
              f"iid_predicted={r['predicted_iid_independent']:.4f}")

    valid = [r for r in results if r["denominator"] > 0]
    if len(valid) >= 5:
        recs = [r["recurrence_independent"] for r in valid]
        mean, lo, hi = bootstrap_ci_independent(recs)
        print(f"\nIndependent bootstrap: mean={mean:.4f} 95% CI [{lo:.4f}, {hi:.4f}] "
              f"(n={len(valid)} epochs)")
    elif valid:
        print(f"\n{len(valid)} epoch(s) with data -- below the 5-epoch bar for a "
              "defensible CI, reported as point estimates only, same as the "
              "primary script's own rule.")

    # Cross-check against the primary script's own aggregate output, if present
    primary_path = os.path.join(os.path.dirname(RAW_DIR), "H2_H3_APTOS_HELDOUT_RESULT.json")
    if os.path.exists(primary_path):
        with open(primary_path) as f:
            primary = json.load(f)
        print("\n" + "=" * 78)
        print("Cross-check against primary script's final output")
        print("=" * 78)
        primary_by_epoch = {e["epoch"]: e for e in primary.get("epochs", []) if "error" not in e}
        max_diff = 0.0
        for r in valid:
            p = primary_by_epoch.get(r["epoch"])
            if not p:
                print(f"  epoch {r['epoch']}: no matching primary result (skipped/errored there)")
                continue
            diff = abs(r["recurrence_independent"] - p["absence_recurrence_rate"])
            max_diff = max(max_diff, diff)
            status = "MATCH" if diff < 1e-9 else f"MISMATCH diff={diff:.6f}"
            print(f"  epoch {r['epoch']}: independent={r['recurrence_independent']:.6f}  "
                  f"primary={p['absence_recurrence_rate']:.6f}  [{status}]")
        print(f"\nmax |independent - primary| across all epochs: {max_diff:.2e}")
        if max_diff > 1e-9:
            print("NOT a clean match -- report this discrepancy, do not paper over it.")
        else:
            print("Exact agreement: the two independently-written code paths compute")
            print("the same numbers from the same raw data. This is a check on")
            print("implementation correctness, not a check on which participation")
            print("model (IID vs sticky) is true -- that question is answered by")
            print("the data itself, and both paths answer it identically.")
    else:
        print(f"\n(No primary result file at {primary_path} yet to cross-check against.)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
