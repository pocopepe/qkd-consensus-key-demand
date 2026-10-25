#!/usr/bin/env python3
"""Read-only reproduction of the paper's E2 table from the frozen RAW traces.
Re-runs the frozen structural analyser on every round-robin raw trace and
compares the per-n mean with the value printed in the manuscript. Writes
nothing under research/results. Also reports the adjacency-correct happy-path
value (E3's correction) so the two definitions can be compared on E2 itself."""
import glob, json, os, re, statistics as st, sys
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, "..", "..")
sys.path.insert(0, os.path.join(H, ".."))
from e1_analyze import D_CORE, analyze
tex = open(os.path.join(ROOT, "paper", "paper.tex")).read()
printed = {int(n): float(v) for n, v in re.findall(r"^(\d+)\s*&\s*\d+\s*&\s*2\.0000\s*&\s*[\d.]+\s*&\s*[\d.]+\s*&\s*([\d.]+)", tex, re.M)}
rows = {}
for p in sorted(glob.glob(os.path.join(ROOT, "research/results/e2_full/raw/n*_roundrobin_run*.json"))):
    d = json.load(open(p)); n = d["n_validators"]; recs = [tuple(r) for r in d["records"]]
    tmo = {int(k) for k in d.get("timeout_views", {})}
    happy, _ = analyze([r for r in recs if r[0] not in tmo], n, D_CORE, "happy")     # the frozen definition
    _, per = analyze(recs, n, D_CORE, "all")
    present = {r["view"][0] for r in per}
    good = [r for r in per if r["pi"] is not None and r["view"][0] not in tmo
            and (r["view"][0] - 1) in present and (r["view"][0] - 1) not in tmo]
    adj = [r["pi"] for r in good]
    rows.setdefault(n, []).append((happy["pi_measured"], st.mean(adj), happy["k_mean"], st.mean(r["k"] for r in good), len(good)))
    print(f"  {os.path.basename(p):28s} pi(frozen happy)={happy['pi_measured']:.6f}  pi(adjacency-correct)={st.mean(adj):.6f}", flush=True)
bad = 0
print("\n n   printed    recomputed  adjacency-correct   predicted   k(frozen)  k(adj-correct)  transitions")
for n in sorted(rows):
    rec = st.mean(x[0] for x in rows[n]); adj = st.mean(x[1] for x in rows[n]); pred = 0.5 + 1 / (n - 1)
    ok = abs(rec - printed[n]) < 5e-7
    bad += not ok
    print(f"{n:2d}   {printed[n]:.6f}   {rec:.6f}    {adj:.6f}          {pred:.6f}   {st.mean(x[2] for x in rows[n]):.4f}     {st.mean(x[3] for x in rows[n]):.4f}          {sum(x[4] for x in rows[n])}   "
          f"|adj-pred|={abs(adj - pred):.1e}   {'MATCH' if ok else 'MISMATCH'}")
sys.exit(1 if bad else 0)
