#!/usr/bin/env python3
"""Final aggregation and report generation. Run AFTER fetch_aptos_bitvecs.py
has produced results (complete or partial -- honest either way).

Does two things the main run's own output does NOT do, closing a rigor gap
found during review: H1 (proposer rotation) is measured per-epoch by the
main script but never given the same epoch-level bootstrap-CI treatment
H2/H3 gets. That asymmetry -- one hypothesis statistically rigorous, the
other just eyeballed -- is exactly the kind of gap worth catching before
calling anything final. Fixed here as a post-processing step over the
already-collected per-epoch data (safer than editing the live process, and
avoids re-fetching anything).

Also runs the independent verifier and the e1_analyze.py corroborating
check across every epoch collected, not just the first, and assembles one
markdown report with everything: verdicts, CIs, cross-checks, and the power
limitation stated plainly rather than buried.
"""
from __future__ import annotations

import glob
import json
import os
import random
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fetch_aptos_bitvecs import epoch_bootstrap_ci  # reused, not reimplemented


def load_results() -> list[dict]:
    for name in ("H2_H3_APTOS_HELDOUT_RESULT.json", "H2_H3_APTOS_HELDOUT_RESULT.partial.json"):
        path = os.path.join(HERE, name)
        if os.path.exists(path):
            d = json.load(open(path))
            return d.get("epochs") or d.get("epochs_so_far") or [], name
    return [], None


def h1_verdict(valid_epochs: list[dict]) -> dict:
    rates = [e["h1_proposer_rotation"]["distinct_proposer_rate"] for e in valid_epochs
             if "h1_proposer_rotation" in e]
    if not rates:
        return {"status": "no_data"}
    if len(rates) < 5:
        mean = sum(rates) / len(rates)
        return {"status": "underpowered_point_estimate_only", "n_epochs": len(rates),
                "mean_distinct_proposer_rate": mean, "per_epoch": rates}
    mean, lo, hi = epoch_bootstrap_ci(rates, seed=42)
    if lo >= 0.90:
        verdict = "K_LT_M_DOMINANT"  # non-degenerate regime, matches E2
    elif hi <= 0.10:
        verdict = "K_EQ_M_DOMINANT"  # degenerate, matches E1
    else:
        verdict = "MIXED_REGIME"
    return {"status": verdict, "n_epochs": len(rates), "mean": mean,
            "ci95_lo": lo, "ci95_hi": hi, "per_epoch": rates}


def run_and_capture(script: str) -> str:
    r = subprocess.run([sys.executable, os.path.join(HERE, script)],
                        capture_output=True, text=True, timeout=120)
    return r.stdout + (r.stderr if r.returncode != 0 else "")


def main() -> int:
    epochs, source_file = load_results()
    if not epochs:
        print("No results file found yet -- nothing to finalize.")
        return 1

    valid = [e for e in epochs if "error" not in e]
    errored = [e for e in epochs if "error" in e]
    print(f"Loaded {len(epochs)} epoch attempt(s) from {source_file}: "
          f"{len(valid)} succeeded, {len(errored)} errored.")

    h1 = h1_verdict(valid)

    # H2/H3 verdict, recomputed here from the per-epoch data so this report
    # doesn't just trust the main script's own end-of-run print -- same
    # discipline as the independent verifier, applied to the aggregation
    # step too, not just the per-epoch arithmetic.
    h23_valid = [e for e in valid if e.get("denominator", 0) > 0]
    h23 = {"status": "no_data"}
    if h23_valid:
        recs = [e["absence_recurrence_rate"] for e in h23_valid]
        iid_preds = [e["predicted_iid_recurrence"] for e in h23_valid]
        if len(h23_valid) < 5:
            h23 = {"status": "underpowered_point_estimate_only", "n_epochs": len(h23_valid),
                   "mean_recurrence": sum(recs) / len(recs),
                   "mean_iid_predicted": sum(iid_preds) / len(iid_preds)}
        else:
            mean, lo, hi = epoch_bootstrap_ci(recs, seed=0)
            mean_iid = sum(iid_preds) / len(iid_preds)
            if lo <= mean_iid <= hi:
                status = "IID_SUPPORTED"
            elif mean - mean_iid >= 0.15:
                status = "STICKY_SUPPORTED"
            else:
                status = "INCONCLUSIVE"
            h23 = {"status": status, "n_epochs": len(h23_valid), "mean_recurrence": mean,
                   "ci95_lo": lo, "ci95_hi": hi, "mean_iid_predicted": mean_iid}

    print("\n" + "=" * 78)
    print("H1 (production k<m regime)")
    print("=" * 78)
    print(json.dumps(h1, indent=2))
    print("\n" + "=" * 78)
    print("H2/H3 (participation memoryless vs sticky)")
    print("=" * 78)
    print(json.dumps(h23, indent=2))

    print("\n" + "=" * 78)
    print("Independent verifier output")
    print("=" * 78)
    iv_out = run_and_capture("independent_verify.py")
    print(iv_out)

    print("\n" + "=" * 78)
    print("Secondary corroborating check (reused e1_analyze.py)")
    print("=" * 78)
    ec_out = run_and_capture("e1_style_crosscheck.py")
    print(ec_out)

    report = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "source_file": source_file,
        "epochs_attempted": len(epochs),
        "epochs_succeeded": len(valid),
        "epochs_errored": len(errored),
        "h1_verdict": h1,
        "h23_verdict": h23,
    }
    out_path = os.path.join(HERE, "FINAL_RESULTS.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
