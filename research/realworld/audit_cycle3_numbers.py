#!/usr/bin/env python3
# Checks the Cycle-3 numbers in paper.tex (volume corollary, Proposition 1 gap, QKD feasibility, the final-view
# reanalysis, E3T, C1, V3, the activity-weighted form, the key budget, the summary tables) against the result files.
import glob
import json
import math
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PAPER = os.path.join(HERE, "..", "..", "paper")
sys.path.insert(0, os.path.join(HERE, "theory"))
sys.path.insert(0, os.path.join(HERE, "e3"))
sys.path.insert(0, HERE)
from chain_model import exact_expected_pi, prop1
from e3t_crosscheck import run_pi
import make_figure_e3t


def strip_separators(text):
    return re.sub(r"(?<=\d)(\\,|\{,\})(?=\d)", "", text)


def load(path):
    return json.load(open(os.path.join(HERE, path)))


def f(x, d=4):
    return f"{x:.{d}f}"


def sci(x, d=1):
    mant, exp = f"{x:.{d}e}".split("e")
    return mant + r"\times10^{" + str(int(exp)) + "}"


def interval(d, a=3, b=None):
    return f"{f(d['mean'], a)}\\ [{f(d['lo'], b or a)},{f(d['hi'], a)}]"


def signed(x, d=4):
    return ("+" if x >= 0 else "") + f(x, d)


def signed1(v):
    r = round(v * 1e4, 1)
    if v > 0 and abs(v) > 1e-9:
        sign = "+"
    elif r < 0:
        sign = "-"
    else:
        sign = ""
    return sign + f"{abs(r):.1f}"


tex_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(PAPER, "paper.tex")
tex = strip_separators(open(tex_path).read())
checks = []


def add(name, text):
    checks.append((name, text))


def bound(name, value, literal):
    # the printed bound must hold and be tight to its last digit
    step = 10 ** -len(literal.split(".")[1]) if "." in literal else 1
    assert value <= float(literal) < value + step, f"{name}: bound {literal} is false or loose for {value}"
    add(name, literal)


# volume corollary and Proposition 1 gap
add("broadcast/unicast ratio n=84", f"{(84 + 1) / 2:.1f}\\times$ at $n=84")
def ratio_of_expectations(n, p):
    # E[carried] / E[total] for equal loss probability p: eq. (11) plus the omitted term p^2 in the numerator
    mu2, mu1 = 2 * p, (n - 3) * p
    return (n + 1 - 2 * mu2 - mu1 + p * p) / (2 * (n - 1) - mu2 - mu1)


add("prop1 gap n=8 1%", sci(exact_expected_pi(8, .01, .01, .01, .01) - ratio_of_expectations(8, .01)))
add("prop1 gap n=16 1%", sci(exact_expected_pi(16, .01, .01, .01, .01) - ratio_of_expectations(16, .01)))

# QKD feasibility
F = load("qkd/QKD_FEASIBILITY.json")
O = F["observed_view_rates"]
rate = O["aptos_rounds_per_s"]["mean"]
add("aptos rounds/s", f"{rate:.1f}$ rounds")
add("aptos min", f"{O['aptos_rounds_per_s']['min']:.1f}$--$")
add("aptos max", f"--${O['aptos_rounds_per_s']['max']:.1f}$")
add("cosmos block time", f"{1 / O['cosmos_blocks_per_s']['mean']:.1f}$~s")
T = {(r["link"], r["n"]): r for r in F["table"] if r["tag_bits"] == 128}


def fmt(x):
    if x >= 100:
        return f"{x:.0f}"
    if x >= 10:
        return f"{x:.1f}"
    return f"{x:.2f}"


LINKS = ("Cambridge 5.0 km (2.22 Mbps)", "Tokyo 45 km (304 kbps)", "Tokyo 45 km (81.7 kbps)")
for n in (16, 32, 64, 100):
    cols = []
    for link in LINKS:
        cols.append(fmt(T[(link, n)]["vmax_unicast"]))
        cols.append(fmt(T[(link, n)]["vmax_broadcast"]))
    add(f"qkd row n={n}", f"{n} & " + " & ".join(cols))
add("broadcast ceiling n=64 text", f"beyond ${T[(LINKS[0], 64)]['vcap_broadcast']:.1f}$ views per second")
add("U/D at n=84", f"${100 * 81 / 166:.0f}\\%$ at $n=84$")
add("uncarried share", f"${100 * 13 / 30:.0f}\\%$ at $16$ validators, ${100 * 81 / 166:.0f}\\%$ at $84$")

# final-view reanalysis
R = load("e3/REANALYSIS_FINAL_VIEW.json")
L = R["with_final_view_as_locked"]
D = R["final_view_dropped"]
add("min participation dropped", f"{D['wide_area_min_participation']:.4f}")
add("worst run dropped", sci(D["wide_area_worst_run"]))
add("max |cell| dropped", sci(max(abs(v) for v in D["wide_area_cell_residuals"].values()), 0))
add("missing total", f"${L['wide_area_missing_votes']}$ missing votes")
add("missing in final view", f"${L['wide_area_missing_in_final_view']}$ of the")
add("missing genuine", f"${D['wide_area_missing_votes']}$ in")
add("transitions dropped", f"{D['wide_area_transitions']}$ transitions")
for n, v in D["wide_area_cell_residuals"].items():
    add(f"locked|post hoc cell n={n}", f"${signed1(L['wide_area_cell_residuals'][n])}$ & ${signed1(v)}$ &")

# E3T: pre-specified, post hoc de-duplicated, and the independent cross-check
E = load("e3/E3T_RESULTS.json")
EV = E["verdicts"]
ER = E["runs"]
ED = load("e3/E3T_RESULTS_DEDUP_POSTHOC.json")["verdicts"]
add("E3T runs", f"${len(ER)}$ runs")
add("E3T transitions", f"{sum(r['transitions'] for r in ER)}$ transitions")
add("E3T suppressed", f"${sum(r['suppressed'] for r in ER)}$ suppressed")
for n in (16, 32):
    v = EV[f"n{n}"]
    add(f"D meas n={n}", f"{f(v['D_measured'], 5)}\\ [{f(v['D_ci'][0], 5)},{f(v['D_ci'][1], 5)}]")
    add(f"D pred n={n}", f(v["D_prop1"], 5))
    add(f"D blind n={n}", sci(v["D_blind"], 0))
    assert v["D_measured"] / v["D_blind"] >= 100, "conclusion: role-blind misses by two orders of magnitude"
    assert abs(ED[f"n{n}"]["D_measured"] - v["D_measured"]) < 1e-5, "D moves by less than 1e-5 after de-duplication"
add("D predicted n16", f"by $\\Delta={f(EV['n16']['D_prop1'], 5)}$ at $n=16$")
add("D measured n16", f"${f(EV['n16']['D_measured'], 5)}\\ [")
roles_max = max(abs(EV[f"n{n}"][k]) for n in (16, 32) for k in ("a_minus_g", "b_minus_other"))
bound("T3 roles", roles_max / 1e-4, "3.2")
add("T3 literal", "3.2\\times10^{-4}")
bound("T1 max", EV["T1"]["max_abs"], "0.0016")
bound("T4 max", max(EV["T4"]["max_prop1"], EV["T4"]["max_blind"]), "0.0015")
bound("T6 max", max(a["after_suppression"] - a["baseline"] for a in EV["T6"]["arms"].values()), "0.035")
add("T5 locked", f"off by ${f(EV['T5']['max_abs'])}$")
add("T5 dedup", f"deviation is ${f(ED['T5']['max_abs'])}$")
bound("T1 dedup", ED["T1"]["max_abs"], "0.0006")

total_records = 0
duplicates = 0
pi = {}
for path in sorted(glob.glob(os.path.join(HERE, "e3", "raw_t", "*.json"))):
    d = json.load(open(path))
    seen = set()
    total_records += len(d["records"])
    for r in d["records"]:
        key = tuple(r)
        if r[4] == "Proposal" and key in seen:
            duplicates += 1
        seen.add(key)
    m = d["e3_meta"]
    pi[m["n"], m["geo_seed"], m["arm"]] = run_pi(path)[1]
    if m["tag"] == "t_n16_g5_none":
        votes = {}
        for v, _, s, t, kind in d["records"]:
            if kind == "Vote":
                votes.setdefault(v, set()).add(s)
        last = max(votes)
        misses = [v for v in votes if v != last and len(votes[v]) < m["n"] - 1]
        proposals = Counter(tuple(r) for r in d["records"] if r[4] == "Proposal")
        doubled = {k[0] for k, x in proposals.items() if x > 1}
        assert all(v + 1 in doubled for v in misses), "every miss is followed by a doubled proposal"
        add("failing run misses", f"${len(misses)}$ times")
add("dedup count", f"${duplicates}$ of ${total_records}$ records")
for n in (16, 32):
    geos = sorted({k[1] for k in pi if k[0] == n})
    diffs = [(pi[n, g, "b"] + pi[n, g, "other"]) / 2 - (pi[n, g, "a"] + pi[n, g, "g"]) / 2 for g in geos]
    assert abs(sum(diffs) / len(diffs) - EV[f"n{n}"]["D_measured"]) <= 2e-17, "independent D agrees to 2e-17"
add("crosscheck literal", "agrees to $2\\times10^{-17}$")

# C1: replayed Cosmos Hub absence
C1 = load("theory/C1_RESULTS.json")
C = C1["cells"]
rr = [c for k, c in C.items() if k.startswith("rr")]
sk = [c for k, c in C.items() if k.startswith("stake")]
assert C1["C1A"]["verdict"] == "SUPPORTED"
plan = load("cosmos/raw_bulk/_plan.json")
add("C1 blocks", f"${plan['len'] // 1000}\\,000$ further Cosmos")
add("C1 windows", f"${plan['len'] // plan['chunk']}$ windows")
assert all(c["windows"] == plan["len"] // plan["chunk"] for c in C.values())
stress = [c["mean_lost_per_view"] for k, c in C.items() if "stress" in k]
add("C1 max R", f"is ${max(c['R'] for c in rr):.3f}$, against")
add("C1 max R table", f"largest ${max(c['R'] for c in rr):.3f}$")
bound("abstract R %", 100 * max(c["R"] for c in rr), "2.2")
add("C1 distinct", f"only ${100 * min(c['distinct_share'] for c in sk):.0f}\\%$--${100 * max(c['distinct_share'] for c in sk):.0f}\\%$")
add("C1 stake R", f"from ${min(c['R'] for c in sk):.3f}$ to ${max(c['R'] for c in sk):.3f}$")

# V3 replication, directional predictions, activity-weighted amendment
V3 = load("V3_RESULTS.json")
W = V3["verdicts"]
P3 = V3["per_epoch"]
V2 = load("V2_RESULTS.json")
P2 = V2["per_epoch"]
r3 = sum(p["rounds"] for p in P3)
r2 = sum(p["rounds"] for p in P2)
add("V3 design", f"${len(P3)}$ further epochs of ${P3[0]['rounds']}$ rounds, ${r3}$ rounds in all")
assert W["H8"]["pooled_fraction_in_band"] == 1.0 and V2["verdicts"]["H8"]["pooled_fraction_in_band"] == 1.0
add("both samples rounds", f"${r2 + r3}$ rounds of both samples")
add("campaign table rounds", f"${r2 + r3}$ rounds, two samples")
add("H1 v3", f"${interval(W['H1'], 4)}$")
add("H1q v3", f"${interval(W['H1q'])}$")
add("H3 v3", f"$+{f(W['H3']['mean'])}\\ [{f(W['H3']['lo'], 5)},{f(W['H3']['hi'])}]$")
add("H2R v3", f"${f(W['H2R']['mean'], 3)}$ against ${f(W['H2R']['mean_iid_predicted'], 3)}$")
add("H2b v3", f"$+{interval(W['H2b'])}$")
add("H10 v3", f"${100 * W['H10']['pooled_failed_round_fraction']:.3f}\\%$")
learners = ("ewma0.5", "ewma0.7", "last", "freq", "markov1", "periodic")
closest = max(p["h6"][l] - p["h6"]["pi_mean"] for p in P3 for l in learners)
add("H6 v3 closest", f"${f(closest)}$; $0$ of ${W['H6']['theoremB_violations']['checked']}$")
assert sum(W["H6"]["theoremB_violations"][k] for k in ("eq", "gt", "lt")) == 0
add("H9 v3", f"${100 * W['H9']['epochs_meeting_bound']:.0f}\\%$ of its epochs")
add("D1", f"& ${f(W['H1q']['lo'], 3)}$ &")
add("D2", f"& ${sci(W['H3']['lo'], 0)}$ &")
A = load("COR2_ACTIVITY_V3.json")["summary"]
add("AW gain", f"${signed(A['abs_gain']['mean'])}\\ [{f(A['abs_gain']['lo'], 5)},{f(A['abs_gain']['hi'])}]$")
add("AW1 table", f"$+{interval(A['ratio_gain'])}$")

# QKD claims at Aptos's rate: "guaranteed" needs v_max >= rate, "cannot be sustained" needs v_cap < rate
cam = {n: T[(LINKS[0], n)] for n in (16, 32, 64, 100)}
t3 = {n: T[(LINKS[1], n)] for n in (16, 32, 64, 100)}
t8 = {n: T[(LINKS[2], n)] for n in (16, 32, 64, 100)}
assert cam[100]["vmax_unicast"] >= rate and cam[32]["vmax_broadcast"] >= rate > cam[64]["vcap_broadcast"]
assert t3[32]["vcap_broadcast"] < rate <= t3[16]["vcap_broadcast"]
assert t3[16]["vmax_broadcast"] < rate, "text: n=16 on 304 kbps is undetermined"
undecided = set()
for lk in LINKS:
    for nn in (16, 32, 64, 100):
        for design in ("unicast", "broadcast"):
            if T[(lk, nn)]["vmax_" + design] < rate <= T[(lk, nn)]["vcap_" + design]:
                undecided.add((lk, nn, design))
assert undecided == {(LINKS[1], 16, "broadcast"), (LINKS[1], 100, "unicast"), (LINKS[2], 32, "unicast")}, undecided
add("undecided cells", "Three cells lie between the guaranteed rate and the ceiling: broadcast at $n=16$")
assert min(t3[16]["vcap_broadcast"], t3[100]["vcap_unicast"], t8[32]["vcap_unicast"]) > rate
add("shortest-path rates of those cells", f"at ${t3[16]['vcap_broadcast']:.1f}$, ${t3[100]['vcap_unicast']:.1f}$, and ${t8[32]['vcap_unicast']:.1f}$ views per second")
assert t8[16]["vcap_broadcast"] < rate and t8[64]["vcap_unicast"] < rate <= t8[32]["vcap_unicast"]
for r in T.values():
    if r["n"] % 2 == 0:
        assert abs(r["vcap_broadcast"] / r["vmax_broadcast"] - 2 * (r["n"] - 1) / r["n"]) < 1e-12
add("ceiling factor", "$2(n-1)/n$ times")
# role effect at exactly 0.2 votes per view: 0.2 / (2 (n - 1) - 0.2)
assert [f"{0.2 / (2 * (n - 1) - 0.2):.4f}" for n in (16, 32)] == ["0.0067", "0.0032"]
add("nominal role effect", "($0.0067$ and $0.0032$ at exactly $0.2$ votes per view)")
# block refill: depth over the mean 4vT/n of a period
ratios = [d / (4 * 26.8 * T / 84) for T, d in ((10, 31), (30, 80), (90, 228))]
assert 1.95 < min(ratios) and max(ratios) < 2.5, ratios
add("refill ratio", "two to two and a half times the mean")

# key budget in bits per second: 128-bit tags at the measured Aptos view rate
for n in (16, 32, 64, 84, 100):
    Du = 2 * (n - 1)
    U = n - 3
    Db = (n + 1) * (n - 1)
    add(f"key budget row n={n}", f"{n} & {Du} & {U} & {Db} & {Du * 128 * rate / 1e3:.1f} & {U * 128 * rate / 1e3:.1f} & {Db * 128 * rate / 1e6:.2f}\\\\")
add("key budget text unicast", f"${166 * 128 * rate / 1e3:.1f}$~kbit/s of key")
add("key budget text fresh", f"${81 * 128 * rate / 1e3:.1f}$~kbit/s lands")
add("key budget text broadcast", f"${7055 * 128 * rate / 1e6:.2f}$~Mbit/s")
add("pairs n=84", f"${84 * 83 // 2}$ pairs")
add("per pair unicast", f"${166 * 128 * rate / (84 * 83 / 2):.0f}$~bit/s")
add("per pair broadcast", f"${7055 * 128 * rate / (84 * 83 / 2) / 1e3:.2f}$~kbit/s per pair")

# 256-bit tags, the commercial link rate, and block refill
T256 = {(r["link"], r["n"]): r for r in F["table"] if r["tag_bits"] == 256}
c256 = T256[(LINKS[0], 100)]
b256 = T256[(LINKS[0], 32)]
add("256-bit unicast n=100", f"at ${c256['vmax_unicast']:.1f}$ views per")
add("256-bit broadcast n=32", f"at $n=32$, at ${b256['vmax_broadcast']:.1f}$")
assert c256["vmax_unicast"] >= rate and b256["vmax_broadcast"] < rate
for row128 in T.values():
    row256 = T256[(row128["link"], row128["n"])]
    assert abs(row256["vmax_unicast"] * 2 - row128["vmax_unicast"]) < 1e-9
    assert abs(row256["vmax_broadcast"] * 2 - row128["vmax_broadcast"]) < 1e-9
VIENNA = "Vienna commercial (1.8 kbps)"
add("commercial n=16", f"guarantees ${T[(VIENNA, 16)]['vmax_unicast']:.2f}$ views per second for $16$ validators")
add("commercial n=100", f"and ${T[(VIENNA, 100)]['vmax_unicast']:.2f}$ for $100$")
assert T[(VIENNA, 16)]["vcap_unicast"] < rate, "text: commercial links sustain neither design at Aptos's rate"
refill = {(r["period_s"], r["n"]): r["tags_per_pair"] for r in F["block_refill"]}
assert abs(refill[(30, 84)] - 4 * rate * 30 / 84) < 1e-9 and refill[(30, 84)] > 2 * 16

add("stake skew", f"the heaviest pair draws ${F['stake_skew']['mean']:.1f}$ times the mean")
assert F["stake_skew"]["max"] - F["stake_skew"]["min"] < 0.1

# exponential smoothing at the weights of Stan et al. (post hoc)
LA = load("POSTHOC_LOW_ALPHA.json")
add("low alpha first", f"covers ${LA['first']['ewma0.1']:.3f}$ of the demand at weight $0.1$ and ${LA['first']['ewma0.3']:.3f}$ at $0.3$")
add("low alpha second", f"and ${LA['second']['ewma0.1']:.3f}$ and ${LA['second']['ewma0.3']:.3f}$ on the second")
for smp in ("first", "second"):
    assert 0.2 < LA[smp]["ewma0.1"] / LA[smp]["pi_mean"] < 0.3 and 0.2 < LA[smp]["ewma0.3"] / LA[smp]["pi_mean"] < 0.3
    assert LA[smp]["ewma0.1_epochs_above_pi"] == 0 and LA[smp]["ewma0.3_epochs_above_pi"] == 0

# the production-chain budget (chains/budget.py -> chains/CHAIN_BUDGET.json)
CB = load("chains/CHAIN_BUDGET.json")
CR = {r["chain"]: r for r in CB["rows"]}
assert CB["tag_bits"] == 128 and CB["links"] == {"megabit": 2.22e6, "kilobit": 1.8e3}


def si(bits):
    if bits >= 1e6:
        return f"${bits / 1e6:.3g}$~Mbit/s"
    return f"${bits / 1e3:.3g}$~kbit/s"


def thousands(x):
    return "$" + f"{x:,}".replace(",", "\\,") + "$"


def sig2(x):
    d = 1 - math.floor(math.log10(x))
    return f"{x:.{d}f}"


for name, dec_fmt in (("Aptos", "3"), ("Cosmos Hub", "3"), ("Solana", "3"), ("Avalanche", "3"), ("Ethereum", "2")):
    r = CR[name]
    rate = f"${r['rate_per_s']:.{dec_fmt}g}$"
    add(f"chain row {name}", f"& {thousands(r['n'])} & {thousands(round(r['tags_per_decision']))} & {rate} & {si(r['key_bit_per_s'])} & {si(r['ring_link_bit_per_s_needed'])} & ${r['sustainable_decisions_per_s_megabit']:.3g}$ & ${sig2(r['sustainable_decisions_per_s_kilobit'])}$\\\\")
for name in ("Polkadot", "Sui"):
    r = CR[name]
    add(f"chain row {name}", f"& {thousands(r['n'])} & {thousands(round(r['tags_per_decision']))} & -- & -- & -- & ${r['sustainable_decisions_per_s_megabit']:.3g}$ & ${sig2(r['sustainable_decisions_per_s_kilobit'])}$\\\\")
margin = CR["Solana"]["sustainable_decisions_per_s_megabit"] / CR["Solana"]["rate_per_s"]
assert 10.5 <= margin < 12, ("text: elevenfold", margin)
assert 5.5 <= CR["Cosmos Hub"]["sustainable_decisions_per_s_megabit"] / CR["Cosmos Hub"]["rate_per_s"] < 6.5, "text: margin of six"
assert 5.0 <= CR["Aptos"]["rate_per_s"] / CR["Aptos"]["sustainable_decisions_per_s_megabit"] < 6.0, "text: short by a factor of five"
assert 6.5 <= CR["Avalanche"]["rate_per_s"] / CR["Avalanche"]["sustainable_decisions_per_s_megabit"] < 7.5, "text: by seven"
assert 9 <= 1 / CR["Polkadot"]["sustainable_decisions_per_s_megabit"] < 11, "text: one GRANDPA round every ten seconds"
assert 4.0 <= CR["Sui"]["sustainable_decisions_per_s_megabit"] < 4.5, "text: Sui four rounds per second"
# chain margins on the conservative (guaranteed) basis: every sustained rate times n / (2 (n - 1))
cons = {k: CR[k]["sustainable_decisions_per_s_megabit"] * CR[k]["n"] / (2 * (CR[k]["n"] - 1)) for k in ("Solana", "Cosmos Hub", "Aptos", "Avalanche")}
assert f"{cons['Solana'] / CR['Solana']['rate_per_s']:.1f}" == "5.7" and f"{cons['Cosmos Hub'] / CR['Cosmos Hub']['rate_per_s']:.1f}" == "3.2"
assert CR["Aptos"]["rate_per_s"] / cons["Aptos"] > 10 and CR["Avalanche"]["rate_per_s"] / cons["Avalanche"] > 13
add("chain margins conservative", "become $5.7$ for Solana and $3.2$ for Cosmos Hub")
add("solana kilobit", f"one slot every ${1 / CR['Solana']['sustainable_decisions_per_s_kilobit']:.0f}$~s")
assert all(r["sustainable_decisions_per_s_kilobit"] < (r["rate_per_s"] or 1e9) for r in CB["rows"] if r["rate_per_s"]), "text: kilobit links sustain none"
add("ethereum minimum", f"is only ${CR['Ethereum']['key_bit_per_s'] / 1e3:.0f}$~kbit/s")
add("ethereum pools", f"rests on ${CR['Ethereum']['pairs'] / 1e11:.1f}\\times10^{{11}}$ pairwise pools, ${CR['Ethereum']['pairs'] * 128 / 1e12:.0f}$~Tbit of key")
assert CR["Solana"]["pattern"] == "2(n-1)" and CR["Aptos"]["pattern"] == "(2n+1)(n-1)"

# the floor of pairwise authentication (capacity/floor.py -> capacity/FLOOR_RESULTS.json)
FL = json.load(open(os.path.join(HERE, "..", "capacity", "FLOOR_RESULTS.json")))
F84 = FL["n84"]
assert F84["f"] == 27 and F84["floor_L1"] == 84 * 28
add("floor hybrid threshold", f"which at $n=84$ is\n${F84['hybrid_L_threshold']:.1f}$ views".replace("\n", " "))
assert abs(F84["broadcast_ratio"] - 3) < 0.01, "text: about three times that floor"
SA = FL["stake_weighted"]["aptos"]
add("floor stake aptos", f"${SA['smallest_count_over_third']}$ on Aptos, and the threshold ${SA['hybrid_L_threshold']:.1f}$ views")
FR = {r["chain"]: r for r in FL["rows"]}
add("floor chains", f"(Aptos ${FR['Aptos']['ratio_to_floor_L1']:.1f}$, or ${SA['broadcast_ratio_to_stake_floor']:.1f}$ against its stake-weighted\nfloor of ${SA['floor_L1'] // 1000}\\,{SA['floor_L1'] % 1000:03d}$; Cosmos Hub ${FR['Cosmos Hub']['ratio_to_floor_L1']:.1f}$; Polkadot ${FR['Polkadot']['ratio_to_floor_L1']:.1f}$; Sui ${FR['Sui']['ratio_to_floor_L1']:.1f}$".replace("\n", " "))
sol = FL["stake_weighted"]["solana"]
assert sol["n"] == CR["Solana"]["n"] == 672
add("floor solana", f"below its floor of\n${sol['floor_L1'] // 1000}\\,{sol['floor_L1'] % 1000:03d}$ (${sol['n']}\\times{sol['smallest_count_over_third']}$, with ${sol['smallest_count_over_third']}$ validators holding at least a third of the stake)\nfor any commit latency under ${sol['hybrid_L_threshold']:.1f}$ slots".replace("\n", " "))
assert FR["Solana"]["tags_per_decision"] == 1342 and all(5.9 <= FR[c]["ratio_to_floor_L1"] <= 6.0 for c in ("Aptos", "Cosmos Hub", "Polkadot")) and 2.9 <= FR["Sui"]["ratio_to_floor_L1"] <= 3

# figures: the suppression figure's bars and the feasibility figure's constants
fig_e3t = open(os.path.join(PAPER, "figures", "fig-e3t.tex")).read()
tb = make_figure_e3t.table()
for n in (16, 32):
    for key in ("meas", "prop1", "blind"):
        assert make_figure_e3t.coords(n, key, tb) in fig_e3t, f"fig-e3t.tex is stale: n={n} {key}"
    for a in ("a", "g"):
        for b in ("b", "other"):
            assert 2.5 < tb[n, a]["meas"] / tb[n, b]["meas"] < 3.6, "text: a or g costs about three times b or other"
        assert tb[n, a]["blind"] < 0.5 * tb[n, a]["meas"], "text: role-blind underestimates a and g"
    for b in ("b", "other"):
        assert tb[n, b]["blind"] > tb[n, b]["meas"], "text: role-blind overestimates b and other"
fig_qkd = open(os.path.join(PAPER, "figures", "fig-qkd.tex")).read()
for Rb in (2.22e6, 304e3, 81.7e3):
    for c in (Rb / 128, 2 * Rb / 128):
        assert f"{c:g}" in fig_qkd or repr(c).rstrip("0").rstrip(".") in fig_qkd, f"fig-qkd.tex constant {c} missing"

e3d_runs = load("e3/E3D_RESULTS.json")["runs"]
add("campaign table vote loss", f"${len(e3d_runs)}$ and ${len(ER)}$ runs; ${sum(r['transitions'] for r in e3d_runs)}$ and ${sum(r['transitions'] for r in ER)}$ transitions")
add("campaign table aptos", f"${r2 + r3}$ rounds, two samples")

# the counts in the text must agree with the appendix table
start = tex.index("\\label{tab:locks}")
locks = tex[start:tex.index("\\end{table*}", start)]
held = len(re.findall(r"& held\\\\", locks))
failed = len(re.findall(r"& \\textbf\{failed\}\\\\", locks))
inc = len(re.findall(r"& \\emph\{inconclusive\}\\\\", locks))
total = held + failed + inc
add("summary counts", f"Of the ${total}$, ${held}$ held, ${inc}$ was inconclusive, and ${failed}$ failed")
add("footnote counts", f"Of ${total}$ predictions, ${held}$ held, ${failed}$ failed, and ${inc}$ was inconclusive")
assert failed == 4
add("abstract failed", f"four of ${total}$ pre-specified predictions failed")

flat = re.sub(r"\s+", " ", tex)
bad = []
for name, text in checks:
    if re.sub(r"\s+", " ", strip_separators(text)) not in flat:
        bad.append(name)
        print("MISSING in paper.tex:", name, repr(text))
print(f"{len(checks) - len(bad)}/{len(checks)} Cycle-3 numbers verified against result files")
sys.exit(1 if bad else 0)
