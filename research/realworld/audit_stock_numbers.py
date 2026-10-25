#!/usr/bin/env python3
# Checks every standing-stock number in paper.tex against stock/*.json.
# usage: audit_stock_numbers.py [--rows] [results.json]
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.join(HERE, "..", "..", "paper")
args = [a for a in sys.argv[1:] if a != "--rows"]

S = json.load(open(args[0] if args else os.path.join(HERE, "stock", "STOCK_RESULTS.json")))
F = json.load(open(os.path.join(HERE, "stock", "FORECAST_RESULTS.json")))["cells"]
Rt = json.load(open(os.path.join(HERE, "stock", "RETAIN_RESULTS.json")))["cells"]
V = json.load(open(os.path.join(HERE, "qkd", "QKD_FEASIBILITY.json")))["observed_view_rates"]["aptos_rounds_per_s"]["mean"]

N = 84
TAG = 128
PAIRS = N * (N - 1) // 2
RATE = 2 * (N - 1) * TAG * V
C = {(c["delta"], c["rule"], c["param"]): c for c in S["cells"].values()}
DS = sorted({c["delta"] for c in S["cells"].values()})
WORD = {3: "three", 4: "four", 6: "six", 8: "eight", 10: "ten", 12: "twelve", 16: "sixteen"}
checks = []


def need(d, t, rule):
    return S["need"][f"{d}|{t}|{rule}"]


def dur(d):
    if d / V < 1:
        return f"{1000 * d / V:.0f}~ms"
    return f"{d / V:.2f}~s"


def add(name, text):
    checks.append((name, text))


rows = []
for d in DS:
    u9 = need(d, 0.99, "uniform")
    s9 = need(d, 0.99, "stake")
    u99 = need(d, 0.999, "uniform")
    s99 = need(d, 0.999, "stake")
    rows.append(f"{d} & {dur(d)} & {S['need'][f'{d}|rr']} & {u9['param']} & {s9['stock_per_pair']:.2f} & {u99['param']} & {s99['stock_per_pair']:.2f}\\\\")
    add(f"table row lead {d}", rows[-1])
if "--rows" in sys.argv:
    print("\n".join(rows))
    sys.exit(0)

tags = sum(r["total"] for r in C[(1, "uniform", 1)]["per_epoch"])
add("held-out epochs", f"other ${len(S['epochs'])}$")
add("tags demanded", f"${tags / 1e6:.1f}$ million tags")
add("model gap", f"differs by at most ${S['max_abs_model_gap']:.4f}$")
add("cells", f"${len(C)}$ combinations")
add("uniform 2 at lead 1", f"${100 * C[(1, 'uniform', 2)]['fill']:.1f}\\%$")
add("uniform 3 at lead 1", f"${100 * C[(1, 'uniform', 3)]['fill']:.2f}\\%$")

saving = 0
for d in DS:
    for t in (0.99, 0.999):
        saving = max(saving, 1 - need(d, t, "stake")["stock_per_pair"] / need(d, t, "uniform")["stock_per_pair"])
add("largest stake saving", f"up to ${100 * saving:.0f}\\%$ less")

big = need(50, 0.999, "uniform")["param"]
small = need(5, 0.99, "uniform")["param"]
bits = big * PAIRS * TAG
add("largest stock in Mbit", f"${bits / 1e6:.1f}$~Mbit")
add("largest stock in seconds", f"${bits / RATE:.1f}$~s")
add("stock at lead 5 in Mbit", f"${small * PAIRS * TAG / 1e6:.1f}$~Mbit")
add("abstract depths", f"with {WORD[small]} tags when relaying takes five views and $99.9\\%$ with {WORD[big]} at fifty")
assert all(S["need"][f"{d}|rr"] <= 4 for d in DS)
assert C[(50, "uniform", 4)]["rr_fill"] == 1

half = 0
for d in DS:
    for t in (0.99, 0.999):
        for rule in ("uniform", "stake"):
            ci = need(d, t, rule)["ci"]
            half = max(half, (ci[1] - ci[0]) / 2)
add("widest interval", f"half-widths of at most ${-(-half * 1e4 // 1) / 1e4:.4f}$")

f0 = F["0"]
f1 = F["1"]
assert f0["armed_per_pair"] < 0.1
for k, c in F.items():
    if k != "0":
        assert abs(c["fill"] - f1["fill"]) < 0.001, "carry-forward under delay is not flat"
add("carry-forward armed", f"holds ${f0['armed_per_pair']:.3f}$ tags per pair")
add("carry-forward no delay", f"serves ${100 * f0['fill']:.1f}\\%$ of the tags on time")
add("carry-forward delay", f"it serves ${100 * f1['fill']:.1f}\\%$, and\n${100 * f1['rr_fill']:.1f}\\%$ under round-robin")
add("abstract carry-forward", f"with any delay it serves ${100 * f1['fill']:.1f}\\%$ in simulation on the Aptos")

add("retained", f"serves ${100 * Rt['1']['fill']:.1f}\\%$ of the tags on time at $\\delta=1$ while holding ${Rt['1']['standing_per_pair']:.2f}$ tags per pair, "
                f"${100 * Rt['5']['fill']:.1f}\\%$ at $\\delta=5$ with ${Rt['5']['standing_per_pair']:.2f}$, and ${100 * Rt['50']['fill']:.1f}\\%$ at $\\delta=50$ with ${Rt['50']['standing_per_pair']:.2f}$")
# the follow-and-keep manager with warm pools (post hoc): start-up effect and long runs
W = json.load(open(os.path.join(HERE, "stock", "RETAIN_WARM.json")))
q1 = W["by_quarter"]["1"]["late_by_quarter"]
add("retained first quarter", f"${100 * q1[0]:.1f}\\%$ in the first quarter of an epoch to ${100 * q1[3]:.2f}\\%$ in the last")
add("retained demand per pair", f"about ${round(W['by_quarter']['1']['tags_per_pair_per_epoch'], -2):.0f}$ tags per")
views = sorted(r["views"] for r in W["long"] if r["delta"] == 1)
add("retained long views", f"${round(views[0], -3)}$ and ${round(views[1], -3)}$")
add("retained long late", f"at most ${100 * max(r['late_all'] for r in W['long']):.2f}\\%$ of the tags late")
for d, text in ((1, "tags per pair at $\\delta=1$"), (5, "at $\\delta=5$"), (50, "at $\\delta=50$")):
    pos = sorted(r["final_position_per_pair"] for r in W["long"] if r["delta"] == d)
    add(f"retained long position {d}", f"${pos[0]:.1f}$ to ${pos[-1]:.1f}$ {text}")
    assert abs(pos[0] - need(d, 0.999, "uniform")["stock_per_pair"]) < 3, "text: about the depths of the table for 99.9%"
    assert all(r["late_last_tenth"] < 0.001 for r in W["long"] if r["delta"] == d)

# the same runs scored by view: a quorum of stake served on time (post hoc)
VW = json.load(open(os.path.join(HERE, "stock", "VIEW_RESULTS.json")))["cells"]
for key, cell in VW.items():
    if cell["rule"] == "uniform" and (cell["delta"], "uniform", cell["param"]) in C:
        assert abs(cell["all"]["fill"] - C[(cell["delta"], "uniform", cell["param"])]["fill"]) < 1e-12, key


def by_view(d, B):
    return 100 * VW[f"{d}|uniform|{B}"]["all"]["quorum_stake"]


assert need(1, 0.99, "uniform")["param"] == 3 and small == 4 and need(50, 0.99, "uniform")["param"] == 12 and big == 16
add("views at lead 1", f"three tags per pair at $\\delta=1$ serve ${by_view(1, 3):.2f}\\%$ of the views")
add("views at lead 5", f"four at $\\delta=5$ serve ${by_view(5, 4):.1f}\\%$")
add("views at lead 50", f"twelve and sixteen at $\\delta=50$ serve ${by_view(50, 12):.1f}\\%$ and ${by_view(50, 16):.2f}\\%$")
shallow = VW["50|uniform|4"]["all"]
add("shallow pools", f"serve ${100 * shallow['fill']:.0f}\\%$ of the tags on time and ${100 * shallow['quorum_stake']:.0f}\\%$ of the views")
add("lead 100", f"At a relay time of $100$ views, ${100 / V:.1f}$~s, twenty tags per pair serve ${by_view(100, 20):.1f}\\%$ of the views")
for d, B in ((1, 3), (5, 4), (50, 12), (50, 16)):
    assert abs(by_view(d, B) - 100 * C[(d, "uniform", B)]["fill"]) < 0.3, "text: the two measures agree at the depths of the table"

# block refill, per-pair ring relay times, timeouts (post hoc; stock/stock_refill.py)
RF = json.load(open(os.path.join(HERE, "stock", "REFILL_RESULTS.json")))
blk = {T: RF["blocks"][T]["need"]["0.99"]["depth"] for T in ("10", "30", "90")}
add("block refill mean", f"${RF['blocks']['30']['formula_4vT_over_n']:.0f}$ tags at $T=30$~s, $n=84$")
add("block refill depths", f"${blk['10']}$ tags per pair serve $99\\%$ of the tags on time at $T=10$~s, ${blk['30']}$ at $30$~s, and ${blk['90']}$ at $90$~s")
add("block refill bytes", f"at ${blk['30'] * TAG / 8 / 1000:.1f}$~kB per pair for $30$~s")
for T in ("10", "30", "90"):
    ratio = blk[T] / RF["blocks"][T]["formula_4vT_over_n"]
    assert 1.9 <= ratio <= 2.5, ("text: about twice the mean", T, ratio)
    assert abs(RF["blocks"][T]["mean_tags_per_pair_per_period"] / RF["blocks"][T]["formula_4vT_over_n"] - 1) < 0.03, "text: whose mean is 4vT/n"
rg = {h: RF["ring"][h]["need"]["0.99"] for h in ("1", "2", "5")}
assert RF["ring"]["1"]["max_delta_views"] == 42
add("ring one view per hop", f"a uniform depth of ${rg['1']['uniform']}$ tags serves $99\\%$ of the tags, where depths set from each pair's own distance and stake average ${rg['1']['bydist_mean_depth']:.1f}$")
add("ring two and five", f"at two views per hop the figures are ${rg['2']['uniform']}$ and ${rg['2']['bydist_mean_depth']:.1f}$, and at five, ${rg['5']['uniform']}$ and ${rg['5']['bydist_mean_depth']:.1f}$")
add("ring in VIII-D", f"gives ${rg['1']['uniform']}$ tags per pair for $99\\%$, or ${rg['1']['bydist_mean_depth']:.1f}$ on\naverage when depths follow distance")
rlx = {(r["rtt_ms"], r["hops"]): r for r in json.load(open(os.path.join(HERE, "..", "..", "kme", "RELAY_LATENCY.json")))["rows"]}
per_hop_views = rlx[(5.0, 42)]["p99_ms"] / 42 / 1000 * V
assert 0.2 <= per_hop_views <= 0.3, ("text: a quarter of a view per hop", per_hop_views)
assert 8 <= 37.3 / (rlx[(0.0, 42)]["p50_ms"] / 42) <= 14, "text: one view per hop is ten times the measured base"
for h in ("1", "2", "5"):
    saving = 1 - rg[h]["bydist_mean_depth"] / rg[h]["uniform"]
    assert 0.25 <= saving <= 0.42, ("text: save about a third", h, saving)
assert RF["timeouts"]["4"] == 2 and RF["timeouts"]["16"] == 8
add("timeouts", "two at the four tags of $\\delta=5$ and eight at sixteen")

# the procedure figure cites tables and figures by number; check them against the aux file
aux = open(os.path.join(PAPER, "paper.aux")).read()
proc = open(os.path.join(PAPER, "figures", "fig-procedure.tex")).read()


def number_of(label):
    return re.search(r"\\newlabel\{" + re.escape(label) + r"\}\{\{(?:\\mbox\s*\{)?([^}]*)\}", aux).group(1)


for prefix, label in (("Section~", "sec:model:extract"), ("Table~", "tab:stock"), ("Fig.~", "fig:stock"), ("Table~", "tab:qkd"), ("Fig.~", "fig:qkd")):
    text = prefix + number_of(label)
    # a section number may be wrapped in \mbox{} so that it cannot break across lines
    assert text in proc or text.replace(prefix, prefix + "\\mbox{") + "}" in proc, f"fig-procedure.tex does not cite {label} as {text!r}"
assert f"${N}$ validators and ${V:.1f}$ views/s" in proc

sys.path.insert(0, HERE)
import make_figure_stock
assert open(make_figure_stock.P).read() == make_figure_stock.build(), "fig-stock.tex is not what make_figure_stock.py generates"

tex = open(os.path.join(PAPER, "paper.tex")).read()
tex = re.sub(r"(?<=\d)(\\,|\{,\})(?=\d)", "", tex)
flat = re.sub(r"\s+", " ", tex)
bad = []
for name, text in checks:
    if re.sub(r"\s+", " ", text) not in flat:
        bad.append((name, text))
        print("MISSING in paper.tex:", name, repr(text))
print(f"{len(checks) - len(bad)}/{len(checks)} standing-stock numbers verified against the result file")
sys.exit(1 if bad else 0)
