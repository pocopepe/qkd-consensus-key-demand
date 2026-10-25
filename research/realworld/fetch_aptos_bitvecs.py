#!/usr/bin/env python3
"""Pull consecutive Aptos block_metadata_transactions and test the locked
H2/H3 falsifier: is validator absence memoryless (IID) or sticky (the same
validators keep missing)?

This is the held-out data run for the prediction locked in
PREDICTION_LOCK_H2_H3.md, written and hashed BEFORE this script existed.
Read-only public REST calls only. Writes only under research/realworld/ --
never touches research/results/ or research/freeze/.

Epoch selection: picked here, before looking at any epoch's data, by taking
epochs spread across the available NewEpochEvent history, explicitly
EXCLUDING epoch 17314 (already inspected during Phase 0 feasibility checks,
per the lock file's rule against reusing the peeked-at sample).
"""
from __future__ import annotations

import glob
import json
import os
import random
import sys
import time
import urllib.request
from datetime import datetime, timezone

BASE = "https://fullnode.mainnet.aptoslabs.com/v1"
OUT = os.path.dirname(os.path.abspath(__file__))
# Anonymous-IP limit observed live: 40,000 compute units / 300s window (429
# response names it explicitly). Scaled down and self-throttled to stay well
# under it rather than hammering and hoping the retry logic saves us.
BLOCKS_PER_EPOCH_TARGET = 120
BATCH = 100
REQUEST_DELAY_S = 0.5
EPOCH_COUNT = 5           # what the lock requires for a defensible bootstrap CI
INTER_EPOCH_SPACING_S = 300  # >= the observed rate-limit window; guarantees a
                              # clean budget per epoch rather than relying on
                              # reactive 429 backoff to bail us out
RAW_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw")


def get(url: str, retries: int = 6) -> dict | list:
    for attempt in range(retries):
        try:
            time.sleep(REQUEST_DELAY_S)
            with urllib.request.urlopen(url, timeout=20) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 30 * (attempt + 1)
                print(f"    (429 rate-limited, backing off {wait}s)")
                time.sleep(wait)
                continue
            if attempt == retries - 1:
                raise
            time.sleep(2.0)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2.0)
    raise RuntimeError(f"exhausted retries for {url}")


def epoch_start_versions(count: int = 40) -> list[tuple[int, int]]:
    """Recent (epoch, version) pairs where that epoch began."""
    events = get(f"{BASE}/accounts/0x1/events/0x1::reconfiguration::Configuration/events?limit={count}")
    return sorted((int(e["data"]["epoch"]), int(e["version"])) for e in events)


def popcount_bits(byte_list: list[int], n: int) -> set[int]:
    """previous_block_votes_bitvec -> set of validator INDICES that signed,
    matching Aptos's documented bit order (MSB-first within each byte,
    index 0 = first bit of first byte)."""
    signed = set()
    idx = 0
    for byte in byte_list:
        for bit in range(8):
            if idx >= n:
                break
            if byte & (0x80 >> bit):
                signed.add(idx)
            idx += 1
    return signed


def pull_epoch_segment(start_version: int, n_blocks: int) -> list[dict]:
    """Pull consecutive block_metadata_transactions starting at start_version,
    until n_blocks distinct rounds are collected or we give up after a
    generous version budget."""
    rounds: list[dict] = []
    v = start_version
    max_versions = n_blocks * 40  # generous upper bound; batches ~6/100 seen above
    fetched = 0
    while len(rounds) < n_blocks and fetched < max_versions:
        batch = get(f"{BASE}/transactions?start={v}&limit={BATCH}")
        if not batch:
            break
        for tx in batch:
            if tx.get("type") == "block_metadata_transaction":
                rounds.append(tx)
        fetched += len(batch)
        v += len(batch)
        if len(batch) < BATCH:
            break  # caught up to chain tip
    return rounds


def validator_index_map(ledger_version: int) -> dict[str, int]:
    d = get(f"{BASE}/accounts/0x1/resource/0x1::stake::ValidatorSet?ledger_version={ledger_version}")
    active = d["data"]["active_validators"]
    return {v["addr"]: i for i, v in enumerate(active)}


def analyze_proposer_rotation(rounds: list[dict]) -> dict:
    """H1: fraction of consecutive rounds with a distinct proposer.
    >=0.90 -> k<m dominant (matches E2). <=0.10 -> k=m dominant (matches E1).
    Rides on the same `rounds` data H2/H3 already pulls; no extra cost."""
    by_round = {int(r["round"]): r["proposer"] for r in rounds}
    sorted_rounds = sorted(by_round)
    distinct, total = 0, 0
    for r in sorted_rounds:
        nxt = r + 1
        if nxt in by_round:
            total += 1
            if by_round[r] != by_round[nxt]:
                distinct += 1
    return {
        "consecutive_pairs": total,
        "distinct_proposer_rate": distinct / total if total else float("nan"),
    }


def analyze_epoch(rounds: list[dict], addr_to_idx: dict[str, int]) -> dict:
    """For consecutive VOTE-rounds (r, r+1): among validators absent from
    round r's vote, what fraction are also absent from round r+1's vote?

    IMPORTANT indexing note, found by checking the field semantics rather
    than assuming them: Aptos's `previous_block_votes_bitvec` on the
    block_metadata_transaction whose own `round` field is r describes votes
    cast FOR ROUND r-1's block, not round r's. Re-key everything by
    `voted_round = tx['round'] - 1` so "absent from voted_round X" and
    "proposer of voted_round X" (the validator whose block those votes
    certify) refer to the same round consistently. Getting this wrong
    doesn't change the PAIRWISE-adjacency structure of the recurrence test
    (adjacent bitvecs in round order are still adjacent), but it does change
    which proposer gets excluded from the "absent" tally each round, and
    that exclusion is who this correctness check is protecting against
    being silently wrong.
    """
    n = len(addr_to_idx)
    by_voted_round: dict[int, dict] = {}
    for tx in rounds:
        voted_round = int(tx["round"]) - 1
        by_voted_round[voted_round] = tx  # tx carries the bitvec FOR voted_round
    sorted_rounds = sorted(by_voted_round)

    # proposer(voted_round) = whoever proposed the block these votes certify.
    # That's the proposer field of the tx whose OWN round equals voted_round,
    # not the tx that carries the bitvec (which is voted_round+1's proposer).
    proposer_of_round = {int(tx["round"]): tx.get("proposer") for tx in rounds}

    numer, denom = 0, 0
    p_samples = []
    signed_cache: dict[int, set[int]] = {}
    for r in sorted_rounds:
        tx = by_voted_round[r]
        signed = popcount_bits(tx.get("previous_block_votes_bitvec", []), n)
        signed_cache[r] = signed
        absent = set(range(n)) - signed
        proposer_idx = addr_to_idx.get(proposer_of_round.get(r))
        if proposer_idx is not None:
            absent.discard(proposer_idx)  # correct round's proposer excluded now
        p_samples.append(len(signed) / max(1, n - 1))
        nxt = r + 1
        if nxt in signed_cache or nxt in by_voted_round:
            signed2 = signed_cache.get(nxt) or popcount_bits(
                by_voted_round[nxt].get("previous_block_votes_bitvec", []), n)
            absent2 = set(range(n)) - signed2
            still_absent = absent & absent2
            numer += len(still_absent)
            denom += len(absent)
    recurrence = numer / denom if denom else float("nan")
    mean_p = sum(p_samples) / len(p_samples) if p_samples else float("nan")
    return {
        "rounds_seen": len(sorted_rounds),
        "round_range": [min(sorted_rounds), max(sorted_rounds)] if sorted_rounds else None,
        "mean_participation_p": mean_p,
        "absence_recurrence_rate": recurrence,
        "predicted_iid_recurrence": 1 - mean_p if mean_p == mean_p else None,
        "numerator": numer,
        "denominator": denom,
    }


def epoch_bootstrap_ci(per_epoch_values: list[float], n_boot: int = 5000,
                        seed: int = 0) -> tuple[float, float, float]:
    """95% CI on the mean of a per-epoch statistic, resampling EPOCHS (not
    the underlying round-transitions within them) with replacement. This is
    the stats standard the main plan requires ("bootstrap over epochs, not
    blocks") -- pooling all raw transitions into one ratio would treat
    within-epoch, highly-correlated events as independent samples and
    understate uncertainty. Returns (mean, lo, hi)."""
    rng = random.Random(seed)
    k = len(per_epoch_values)
    mean = sum(per_epoch_values) / k
    if k < 2:
        return mean, float("nan"), float("nan")
    boot_means = []
    for _ in range(n_boot):
        sample = [per_epoch_values[rng.randrange(k)] for _ in range(k)]
        boot_means.append(sum(sample) / k)
    boot_means.sort()
    lo = boot_means[int(0.025 * n_boot)]
    hi = boot_means[int(0.975 * n_boot) - 1]
    return mean, lo, hi


def main() -> int:
    print("=" * 78, flush=True)
    print("H2/H3 held-out test: absence autocorrelation on Aptos mainnet", flush=True)
    print("=" * 78, flush=True)

    os.makedirs(RAW_DIR, exist_ok=True)

    # Resume support: if a previous run (possibly killed by session teardown,
    # not a bug in the logic -- see PREDICTION_LOCK_H2_H3.md) already fetched
    # and persisted an epoch's raw data, reuse it rather than re-spending
    # rate-limit budget re-fetching. Recomputed via the SAME analyze_epoch /
    # analyze_proposer_rotation functions used for freshly-fetched epochs --
    # not hand-copied numbers, so a cached epoch is treated identically to a
    # fresh one downstream.
    cached_results = []
    cached_epochs = set()
    for raw_path in sorted(glob.glob(os.path.join(RAW_DIR, "epoch_*.json"))):
        try:
            raw = json.load(open(raw_path))
        except Exception:
            continue
        addr_to_idx = raw["addr_to_idx"]
        rounds = raw["rounds_raw"]
        stats = analyze_epoch(rounds, addr_to_idx)
        stats["epoch"] = raw["epoch"]
        stats["n_validators"] = len(addr_to_idx)
        stats["h1_proposer_rotation"] = analyze_proposer_rotation(rounds)
        stats["raw_file"] = raw_path
        stats["resumed_from_cache"] = True
        cached_results.append(stats)
        cached_epochs.add(raw["epoch"])
    if cached_results:
        print(f"resumed {len(cached_results)} epoch(s) from cached raw data: "
              f"{sorted(cached_epochs)}", flush=True)

    candidates = epoch_start_versions(60)
    excluded = {17314} | cached_epochs  # 17314: already inspected during Phase 0
    picks = [c for c in candidates if c[0] not in excluded]
    remaining_needed = max(0, EPOCH_COUNT - len(cached_results))
    # spread selection: every ~Nth candidate epoch, chosen by position alone
    # (not by any property of the data) to avoid cherry-picking
    step = max(1, len(picks) // max(1, remaining_needed)) if remaining_needed else 1
    chosen = picks[::step][:remaining_needed]
    # next-epoch boundary for each chosen epoch, so a randomized start offset
    # can be kept safely inside the epoch rather than spilling across it
    by_epoch_version = dict(candidates)
    next_boundary = {}
    for epoch, version in chosen:
        later = sorted(v for e, v in candidates if v > version)
        next_boundary[epoch] = later[0] if later else version + 2_000_000
    print(f"epoch candidates available: {len(candidates)}, need {remaining_needed} more "
          f"(have {len(cached_results)} cached), chosen: {[e for e, _ in chosen]}",
          flush=True)

    # random start offset within each epoch, seeded deterministically so the
    # choice is reproducible and was fixed before this run started reading
    # any epoch's actual data -- not tuned after seeing results.
    offset_rng = random.Random("h2h3-offset-2026-09-17")

    def ts() -> str:
        return datetime.now(timezone.utc).strftime("%H:%M:%S")

    start_time = time.time()
    hard_deadline = start_time + (max(1, remaining_needed) * (INTER_EPOCH_SPACING_S + 120)) + 300
    results = list(cached_results)
    for i, (epoch, version) in enumerate(chosen):
        if time.time() > hard_deadline:
            print(f"[{ts()}] hard overall deadline hit, stopping with "
                  f"{len(results)}/{len(chosen)} epochs attempted")
            break
        if i > 0:
            print(f"[{ts()}] spacing {INTER_EPOCH_SPACING_S}s before next epoch "
                  f"pull, to stay clear of the rate-limit window rather than "
                  f"relying on reactive backoff", flush=True)
            time.sleep(INTER_EPOCH_SPACING_S)

        span = next_boundary[epoch] - version
        safe_span = max(1000, int(span * 0.7))
        offset = offset_rng.randrange(0, safe_span)
        start_version = version + offset
        print(f"\n[{ts()}] --- epoch {epoch} (epoch start {version}, sampling "
              f"from {start_version}, offset {offset}/{span}) ---", flush=True)
        try:
            addr_to_idx = validator_index_map(start_version)
            rounds = pull_epoch_segment(start_version, BLOCKS_PER_EPOCH_TARGET)
            # Persist raw per-round records BEFORE aggregating, so a
            # hostile/independent reviewer can recompute every statistic
            # from disk without re-hitting the (rate-limited) chain, and so
            # this epoch's work survives even if a later epoch fails.
            raw_path = os.path.join(RAW_DIR, f"epoch_{epoch}.json")
            with open(raw_path, "w") as f:
                json.dump({
                    "epoch": epoch, "start_version": start_version,
                    "addr_to_idx": addr_to_idx, "rounds_raw": rounds,
                }, f)
            stats = analyze_epoch(rounds, addr_to_idx)
            stats["epoch"] = epoch
            stats["n_validators"] = len(addr_to_idx)
            stats["h1_proposer_rotation"] = analyze_proposer_rotation(rounds)
            stats["raw_file"] = raw_path
            results.append(stats)
            if stats["mean_participation_p"] == stats["mean_participation_p"]:
                print(f"[{ts()}]   n={stats['n_validators']}  "
                      f"rounds_seen={stats['rounds_seen']}  "
                      f"mean_p={stats['mean_participation_p']:.4f}  "
                      f"recurrence={stats['absence_recurrence_rate']:.4f}  "
                      f"iid_predicts={stats['predicted_iid_recurrence']:.4f}  "
                      f"h1_distinct_rate={stats['h1_proposer_rotation']['distinct_proposer_rate']:.4f}",
                      flush=True)
            else:
                print(f"[{ts()}]   n={stats['n_validators']}  "
                      f"rounds_seen={stats['rounds_seen']}  "
                      f"(insufficient absence samples)", flush=True)
        except Exception as e:
            print(f"[{ts()}]   SKIPPED (fetch/parse error): {e}", flush=True)
            results.append({"epoch": epoch, "error": str(e)})
        # checkpoint partial results after every epoch, not just at the end
        with open(os.path.join(OUT, "H2_H3_APTOS_HELDOUT_RESULT.partial.json"), "w") as f:
            json.dump({"utc": datetime.now(timezone.utc).isoformat(),
                        "epochs_so_far": results}, f, indent=2)

    valid = [r for r in results if "error" not in r and r.get("denominator", 0) > 0]
    print()
    print("=" * 78)
    print("Verdict against the locked falsification bands")
    print("=" * 78)
    boot_ci = None
    if not valid:
        print("INCONCLUSIVE: no epoch produced enough absence events to test.")
        print("(This itself is informative -- see PREDICTION_LOCK_H2_H3.md 'what")
        print(" would make this uninteresting': near-total participation observed.)")
        verdict = "inconclusive_insufficient_absences"
    elif len(valid) < 5:
        print(f"only {len(valid)} epoch(s) produced usable data -- too few for a")
        print("defensible epoch-level bootstrap CI (need several independent")
        print("epochs, not several samples from one). Reporting the point")
        print("estimate honestly as UNDERPOWERED rather than manufacturing a CI")
        print("from too little data.")
        recs = [r["absence_recurrence_rate"] for r in valid]
        iid_preds = [r["predicted_iid_recurrence"] for r in valid]
        mean_rec = sum(recs) / len(recs)
        mean_iid_pred = sum(iid_preds) / len(iid_preds)
        for r in valid:
            print(f"  epoch {r['epoch']}: recurrence={r['absence_recurrence_rate']:.4f}  "
                  f"iid_predicted={r['predicted_iid_recurrence']:.4f}  "
                  f"n_transitions={r['denominator']}")
        print(f"gap (point estimate, no CI): {mean_rec - mean_iid_pred:+.4f}")
        verdict = "underpowered_point_estimate_only"
    else:
        recs = [r["absence_recurrence_rate"] for r in valid]
        iid_preds = [r["predicted_iid_recurrence"] for r in valid]
        mean_rec, lo, hi = epoch_bootstrap_ci(recs)
        mean_iid_pred = sum(iid_preds) / len(iid_preds)
        gap = mean_rec - mean_iid_pred
        boot_ci = {"mean": mean_rec, "ci95_lo": lo, "ci95_hi": hi}
        print(f"epochs used: {len(valid)}")
        print(f"mean absence-recurrence rate: {mean_rec:.4f}  95% CI [{lo:.4f}, {hi:.4f}] "
              f"(bootstrap over epochs, not raw transitions)")
        print(f"mean IID-predicted rate (1-p): {mean_iid_pred:.4f}")
        print(f"gap: {gap:+.4f}")
        if mean_iid_pred >= lo and mean_iid_pred <= hi:
            verdict = "IID_SUPPORTED"  # IID prediction falls inside the observed CI
        elif abs(gap) <= 0.05:
            verdict = "IID_SUPPORTED"
        elif gap >= 0.15:
            verdict = "STICKY_SUPPORTED"
        else:
            verdict = "INCONCLUSIVE"
        print(f"\nVERDICT: {verdict}")

    out = {
        "experiment_id": "H2-H3-APTOS-HELDOUT-001",
        "utc": datetime.now(timezone.utc).isoformat(),
        "excluded_epoch_phase0_peek": 17314,
        "epochs": results,
        "bootstrap_ci": boot_ci,
        "verdict": verdict,
    }
    path = os.path.join(OUT, "H2_H3_APTOS_HELDOUT_RESULT.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
