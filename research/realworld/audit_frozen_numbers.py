#!/usr/bin/env python3
# Checks the numbers paper.tex quotes from the frozen experiments and the measured fast path, each read from a
# named field of its result file. Read-only.
import glob
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
RESULTS = os.path.join(ROOT, "research", "results")


def load(*parts):
    return json.load(open(os.path.join(*parts)))


def strip_separators(text):
    return re.sub(r"(?<=\d)(\\,|\{,\})(?=\d)", "", text)


def flatten(text):
    return re.sub(r"\s+", " ", text)


def sci(x, d=1):
    mant, exp = f"{x:.{d}e}".split("e")
    return mant + r"\times10^{" + str(int(exp)) + "}"


tex_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "paper", "paper.tex")
tex = flatten(strip_separators(open(tex_path).read()))
checks = []


def add(name, text):
    checks.append((name, text))


# loopback campaign (frozen e2_full)
t1 = load(RESULTS, "e2_full", "tables", "table1_roundrobin.json")
t2 = load(RESULTS, "e2_full", "tables", "table2_control.json")
runs = load(RESULTS, "e2_full", "processed", "all_runs.json")
rr = [r for r in runs if r["mode"] == "roundrobin"]
fx = [r for r in runs if r["mode"] != "roundrobin"]
ratios = []
for row in t1:
    n = row["n"]
    mine = [r for r in rr if r["n"] == n]
    meas = statistics.mean(row["per_run_pi"])
    pred = (n + 1) / (2 * (n - 1))
    for r in mine:
        assert r["happy"]["m"] == 2 and r["happy"]["rho"] == 0
        assert r["leader_change_rate"] == 1.0 and r["happy"]["support"] == 2 * n - 3
    k = statistics.mean(r["happy"]["k"] for r in mine)
    add(f"loopback row n={n}", f"{n} & ${row['views']}$ & 2.0000 & {k:.4f} & {pred:.6f} & {meas:.6f} & ${sci(abs(round(pred, 10) - meas))}$")
    ratios.append((meas - 0.5) * (n - 1))
add("loopback ratios", f"is ${ratios[0]:.4f}$ at\n$n=4$ and ${ratios[-1]:.4f}$ at $n=32$".replace("\n", " "))
add("loopback sd n=32", f"to ${sci(t1[-1]['pi_sd'])}$ at $n=32$")
add("loopback worst residual", f"${sci(max(r['error'] for r in t1))}$, at $n=32$")
add("loopback views", f"${min(r['views'] for r in t1)}$ to ${max(r['views'] for r in t1)}$ analyzed views")
k32 = statistics.mean(r["happy"]["k"] for r in rr if r["n"] == 32)
add("loopback k", f"$k$ is $1.0000$ at $n\\le7$ and ${k32:.4f}$ at $n=32$")
for n in (4, 7):
    assert f"{statistics.mean(r['happy']['k'] for r in rr if r['n'] == n):.4f}" == "1.0000"
add("loopback runs", f"{len(runs)} runs of both arms")
add("leader change", "$100.0\\%$ of consecutive views")
for r in fx:
    assert r["happy"]["m"] == 1 and r["happy"]["k"] == 1 and r["happy"]["pi"] == 1 and r["happy"]["support"] == r["n"] - 1
add("control views", f"${min(r['views'] for r in t2)}$ to ${max(r['views'] for r in t2)}$ views per cell")

# the two implementations at k = m (frozen e1)
e1 = {(r["impl"], r["regime"], r["model"]): r for r in load(RESULTS, "e1", "tables", "table1_theory_vs_measured.json")}
c = e1["CometBFT", "steady", "D-core"]
l = e1["libhotstuff", "stable-leader", "D-core"]
assert c["rho"] == 0 and c["pi_measured"] == 1 and l["rho"] == 0 and l["pi_measured"] == 1 and l["m"] == 1
add("CometBFT", f"(${c['views']}$ views at $n=4$)")
add("CometBFT cover", f"size ${c['m']:.3f}$ on average")
add("libhotstuff views", f"(${l['views']}$ views)")

# predictor table (frozen corrected zoo) and the enumeration
zoo = load(RESULTS, "predictor_zoo_corrected", "P-predictor-zoo-corrected-001.json")
zoo_rows = {row["n"]: row for row in zoo["rows"] if row["schedule"] == "round_robin"}
for n in (16, 32):
    assert zoo_rows[n]["ewma0.7"] == zoo_rows[n]["last"] == zoo_rows[n]["pi"]
add("zoo pi", f"exactly, ${zoo_rows[16]['pi']:.6f}$ at $n=16$")
add("zoo periodic", f"reaches ${zoo_rows[16]['periodic']:.6f}$ and")
add("zoo markov", f"reaches ${zoo_rows[16]['markov1']:.6f}$")
add("zoo freq", f"reaches only ${zoo_rows[16]['freq']:.6f}$.")
add("zoo views", f"over ${zoo['config']['views']}$ views (${zoo['config']['burn_in']}$ of warm-up")

# provisioning simulation (frozen E4, E4TTL, E6)
e4 = load(RESULTS, "E4-operational-001.json")
tt = load(RESULTS, "E4TTL-001.json")
e6 = {a: load(RESULTS, f"E6-sharedpool-{a}.json") for a in ("fifo", "random")}
pis = sorted(r["pi"] for r in e4["q1_ceiling"])
assert len(pis) == 6
for r in e4["q1_ceiling"]:
    lo = min(r["hit_by_R"])
    hi = max(r["hit_by_R"])
    if r["pi"] < 1:
        assert hi - lo == 0, "sweep changes the hit rate where pi < 1"
assert tt["seeds"] == e6["fifo"]["seeds"] == e6["random"]["seeds"]
carry = [r for r in tt["rows"] if r["predictor"] == "carry"]
over = [r for r in carry if r["hit_fresh"] > r["pi"]]
assert over and all((r["m"], r["k"]) == (2, 0) for r in over), "fresh hits exceed pi somewhere other than (2,0)"
excess = max(r["hit_fresh"] - r["pi"] for r in carry)
assert excess <= 0.0044 < excess + 1e-4
assert abs(max(r["hit_fresh"] for r in over) - 4 / 29) < 1e-3 and abs(over[0]["pi"] - 4 / 30) < 1e-12
starve = []
for arm in e6.values():
    cr = [r for r in arm["rows"] if r["predictor"] == "carry"]
    assert len(cr) == 48
    assert all((r["m"], r["k"]) == (2, 0) for r in cr if r["fresh"] > r["pi"])
    starve += [r["starve"] for r in arm["rows"] if r["predictor"] == "structural" and r["regime"] == "high" and r["pi"] == 1]
assert all(f"{100 * x:.0f}" in ("27", "28") for x in starve) and 0.265 < statistics.mean(starve) < 0.275

# relay time through the ETSI 014 KME, two calls per hop (kme/relay_latency.py)
rl = {(r["rtt_ms"], r["hops"]): r for r in load(ROOT, "kme", "RELAY_LATENCY.json")["rows"]}
V = load(HERE, "qkd", "QKD_FEASIBILITY.json")["observed_view_rates"]["aptos_rounds_per_s"]["mean"]
assert all(r["repeats"] == 200 for r in rl.values())
add("relay repeats", "Over $200$ relays per setting")
add("relay one hop", f"${rl[(0.0, 1)]['p99_ms']:.1f}$~ms for one hop")
add("relay 42 hops", f"${rl[(0.0, 42)]['p99_ms']:.0f}$~ms for $42$ hops")
add("relay 42 hops rtt", f"it is ${rl[(5.0, 42)]['p99_ms']:.0f}$~ms, under ${-(-rl[(5.0, 42)]['p99_ms'] * V // 1000):.0f}$ views")
assert rl[(5.0, 42)]["p99_ms"] * V / 1000 < 10, "text: under 10 views"
for rtt in (0.0, 1.0, 5.0):
    per_hop = [rl[(rtt, h)]["p50_ms"] / h for h in (8, 16, 42)]
    assert max(per_hop) / min(per_hop) < 1.6, "text: grows linearly in the hop count"
# each hop adds about a tenth of a view without the pause and about a quarter with it
view_ms = 1000 / V
assert 0.09 < rl[(0.0, 42)]["p99_ms"] / 42 / view_ms < 0.12 and 0.2 < rl[(5.0, 42)]["p99_ms"] / 42 / view_ms < 0.27
add("per hop view fraction", "each hop adds about a tenth of a view, a quarter with the pause")

# Aptos first sample: facts read from the raw epochs
v2 = load(HERE, "V2_RESULTS.json")
ph = load(HERE, "V2_POSTHOC.json")
table = load(HERE, "raw_v2", "_epoch_table.json")
add("distinct leaders", f"${100 * v2['verdicts']['H1']['mean']:.2f}\\%$ of cases")
add("candidate epochs", f"from the ${table['candidates']}$ eligible epochs")
ns = sorted({p["n"] for p in v2["per_epoch"]})
add("validator counts", f"$n={ns[0]}$--${ns[-1]}$")
durations = []
first = []
last = []
for path in glob.glob(os.path.join(HERE, "raw_v2", "epoch_*.json")):
    ts = [int(e["data"]["time_microseconds"]) for e in json.load(open(path))["events"]]
    durations.append((max(ts) - min(ts)) / 1e6)
    first.append(min(ts))
    last.append(max(ts))
add("window duration", f"a median of ${statistics.median(durations):.0f}$~s of chain time")
assert 7.5 < (max(last) - min(first)) / 86400e6 < 8.5, "about eight days"
three = [100 * s for s, c in zip(ph["never_seen_stake"], ph["never_seen_count"]) if c == 3]
four = [100 * s for s, c in zip(ph["never_seen_stake"], ph["never_seen_count"]) if c == 4]
assert set(ph["never_seen_count"]) == {3, 4} and len(four) == 6
assert all(f"{x:.2f}" in ("0.88", "0.89") for x in three)
extra = [x - statistics.mean(three) for x in four]
assert all(1.3 < x < 1.5 for x in extra)
add("never-seen stake", f"holding ${min(three):.2f}\\%$ of stake")
add("fourth validator", f"holding about ${statistics.mean(extra):.1f}\\%$ is absent in six")
add("failed leaders", f"${v2['verdicts']['H10']['total_round_gaps']}$ rounds in ${sum(p['rounds'] for p in v2['per_epoch'])}$")

# wide-area campaign: derived statements
e3 = load(HERE, "e3", "E3C_RESULTS.json")
cells = e3["verdicts"]["P2_full_participation_theory"]["cells"]
ratios = [f"{(cells[n]['pi_happy_mean'] - 0.5) * (int(n) - 1):.3f}" for n in ("8", "16", "32")]
add("wide-area ratios", "$" + "$, $".join(ratios) + f"$, and ${(cells['64']['pi_happy_mean'] - 0.5) * 63:.3f}$")
for c in cells.values():
    assert abs(c["pi_all_mean"] - c["pi_happy_mean"]) < 1e-4, "timeout views move the value by less than 1e-4"
add("cover size two", f"${100 * e3['verdicts']['P1_structure']['min_m2_fraction']:.2f}\\%$ of transitions")

# arithmetic stated in the text
m = re.search(r"Of the \$(\d+)\$\s+missing votes, \$(\d+)\$ come from the previous leader", tex)
assert m and int(m.group(2)) < int(m.group(1)) and int(m.group(2)) / int(m.group(1)) > 0.6, "text: most missing votes come from the previous leader"

bad = []
for name, text in checks:
    if flatten(strip_separators(text)) not in tex:
        bad.append(name)
        print("MISSING in paper.tex:", name, repr(text))
print(f"{len(checks) - len(bad)}/{len(checks)} frozen-experiment numbers verified against result files")
sys.exit(1 if bad else 0)
