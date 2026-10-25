#!/usr/bin/env python3
# Checks the numbers the real-world sections of paper.tex quote against the archived result files.
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(*parts):
    return json.load(open(os.path.join(HERE, *parts)))


def strip_separators(text):
    return re.sub(r"(?<=\d)(\\,|\{,\})(?=\d)", "", text)


def f(x, d=4):
    return f"{x:.{d}f}"


def thousands(x):
    return f"{x:,}".replace(",", "{,}")


tex = strip_separators(open(os.path.join(HERE, "..", "..", "paper", "paper.tex")).read())
v2 = load("V2_RESULTS.json")
V = v2["verdicts"]
per = v2["per_epoch"]
ph = load("V2_POSTHOC.json")
h7 = load("H7_RESULTS.json")["verdicts"]
e3 = load("e3", "E3C_RESULTS.json")
E = e3["verdicts"]
W = [r for r in e3["runs"] if not r["silent"]]
FC = [r for r in e3["runs"] if r["silent"]]
cells = E["P2_full_participation_theory"]["cells"]
cos = load("cosmos", "COSMOS_RESULTS.json")
CV = cos["verdicts"]
CP = cos["per_window"]
e3d = load("e3", "E3D_RESULTS.json")
DV = e3d["verdicts"]
DR = e3d["runs"]
roles = load("e3", "E3D_POSTHOC_ROLES.json")

# the E2 table reproduced from the raw traces by reproduce_e2_from_raw.py
e2 = open(os.path.join(HERE, "E2_REPRODUCTION.txt")).read()
e2_trans = sum(int(x) for x in re.findall(r"\s(\d{4,6})\s+\|adj-pred\|", e2))
e2_worst = max(float(x) for x in re.findall(r"\|adj-pred\|=([0-9.e+-]+)", e2))
assert e2.count("MATCH") == 5 and "MISMATCH" not in e2, "E2 table no longer reproduces from raw traces"

checks = [
    ('e2 reanalysis transitions', thousands(e2_trans)),
    ('e2 reanalysis worst residual', f'{e2_worst * 10000000.0:.1f}' + '\\times10^{-7}'),
    ('cosmos blocks', thousands(cos['blocks'])),
    ('cosmos ge0.90 blocks', thousands(round(CV['CH0_not_truncated']['pooled_fraction_power_ge_0.90'] * cos['blocks']))),
    ('cosmos p count', f(CV['CH1_participation']['count']['mean'])),
    ('cosmos p count lo', f(CV['CH1_participation']['count']['lo'])),
    ('cosmos p count hi', f(CV['CH1_participation']['count']['hi'])),
    ('cosmos p power', f(CV['CH1_participation']['power']['mean'])),
    ('cosmos p power lo', f(CV['CH1_participation']['power']['lo'])),
    ('cosmos p power hi', f(CV['CH1_participation']['power']['hi'])),
    ('cosmos windows never-seen', str(sum((1 for r in CP if r['never_seen'] > 0)))),
    ('cosmos round>0 pct', f(100 * CV['CH3_low_fault_rate']['pooled_fraction_round_gt0'], 2)),
    ('cosmos recurrence', f(CV['CH2_absence_recurs']['mean_recurrence'], 3)),
    ('cosmos iid', f(CV['CH2_absence_recurs']['mean_iid'])),
    ('cosmos h2b pred', f(statistics.mean((r['h2b_pred'] for r in CP)), 3)),
    ('cosmos h2b obs', f(statistics.mean((r['h2b_obs'] for r in CP)), 3)),
    ('cosmos h2b resid', f(CV['CH2b_static_heterogeneity']['mean'], 3)),
    ('cosmos h2b lo', f(CV['CH2b_static_heterogeneity']['lo'], 3)),
    ('cosmos h2b hi', f(CV['CH2b_static_heterogeneity']['hi'], 3)),
    ('e3d runs', str(DV['R1_role_formula_fits']['runs'])),
    ('e3d transitions', str(sum((r['transitions'] for r in DR)))),
    ('e3d R1 max', f(DV['R1_role_formula_fits']['max_abs_residual'])),
    ('e3d lossy', str(DV['R2_beats_role_blind']['lossy_runs'])),
    ('e3d wins', str(DV['R2_beats_role_blind']['wins'])),
    ('e3d mean role', f(DV['R2_beats_role_blind']['lossy_mean_resid']['pi_role'])),
    ('e3d mean pip', f(DV['R2_beats_role_blind']['lossy_mean_resid']['pi_p'])),
    ('e3d mean full', f(DV['R2_beats_role_blind']['lossy_mean_resid']['pi_full'])),
    ('e3d missing prev', str(DV['R3_previous_leader_share']['missing_prev'])),
    ('e3d missing total', str(DV['R3_previous_leader_share']['missing_total'])),
    ('e3d prev share pct', f(100 * DV['R3_previous_leader_share']['share'], 0)),
    ('roles max resid', f(roles['max_abs_resid']['three_role'])),
    ('sensitivity n16', f((2 - 17 / 30) / (1 - 17 / 30), 1)),
    ('H1 mean', f(V['H1']['mean'])),
    ('H1 lo', f(V['H1']['lo'])),
    ('H1 hi', f(V['H1']['hi'])),
    ('H1q', f(V['H1q']['mean'], 3)),
    ('H1q lo', f(V['H1q']['lo'], 3)),
    ('H1q hi', f(V['H1q']['hi'], 3)),
    ('sum s2', f(V['H1q']['pooled_sum_s2'])),
    ('pi implied', f(V['H3']['mean_pi_schedule_implied'])),
    ('pi stake', f(V['H3']['mean_pi_stake_predicted'])),
    ('pi generic', f(V['H3']['mean_pi_generic'])),
    ('H3 diff', f(V['H3']['mean'])),
    ('H3 lo', f(V['H3']['lo'])),
    ('H3 hi', f(V['H3']['hi'])),
    ('failed pct', f(100 * V['H10']['pooled_failed_round_fraction'], 3)),
    ('H9 share', f(100 * V['H9']['epochs_meeting_bound'], 0)),
    ('H9 min', f(100 * V['H9']['min_live_stake'], 2)),
    ('H9 mean', f(100 * V['H9']['mean_live_stake'], 2)),
    ('recurrence', f(V['H2R']['mean'], 3)),
    ('iid', f(V['H2R']['mean_iid_predicted'], 3)),
    ('het resid', f(V['H2b']['mean'], 3)),
    ('het lo', f(V['H2b']['lo'], 3)),
    ('het hi', f(V['H2b']['hi'], 3)),
    ('het share', f(100 * ph['q2_share_explained'], 0)),
    ('zoo pi', f(V['H6']['pi_mean'])),
    ('zoo periodic', f(V['H6']['periodic']['mean_coverage'])),
    ('zoo markov', f(V['H6']['markov1']['mean_coverage'])),
    ('zoo last', f(V['H6']['last']['mean_coverage'])),
    ('zoo closest', f(-max((r['h6']['last'] - r['h6']['pi_mean'] for r in per)))),
    ('h7 ceiling', f(h7['mean_ceiling'])),
    ('h7 sched', f(h7['mean_pair_carry_rate'])),
    ('e3c m2', f(100 * E['P1_structure']['min_m2_fraction'], 2)),
    ('e3c rho', f(E['P1_structure']['max_rho'], 4)),
    ('e3c worst run e4', f(10000.0 * max((abs(r['pi_happy'] - r['pi_full']) for r in W)), 1)),
    ('e3c max cell e4', f(10000.0 * E['P2_full_participation_theory']['max_abs_residual'], 1)),
    ('e3c min p_vote', f(min((r['p_vote'] for r in W)))),
    ('f1 mean', f(E['F1_fault_mixture']['pi_all_mean'])),
    ('f1 sd', f(E['F1_fault_mixture']['pi_all_sd'])),
    ('f1 pred', f(E['F1_fault_mixture']['pi_mixture_pred'])),
    ('f5 mean', f(E['F5_fault_mixture']['pi_all_mean'])),
    ('f5 sd', f(E['F5_fault_mixture']['pi_all_sd'])),
    ('f5 pred', f(E['F5_fault_mixture']['pi_mixture_pred'])),
    ('f max resid', f(max(E['F1_fault_mixture']['max_abs_residual'], E['F5_fault_mixture']['max_abs_residual']))),
    ('f1 k0', f(E['F1_fault_mixture']['pi_k0_mean'])),
    ('f5 k0', f(E['F5_fault_mixture']['pi_k0_mean'])),
    ('f5 views', str(sum((r['views_present'] for r in FC if len(r['silent']) == 5)))),
    ('happy total', thousands(sum((r['happy_transitions'] for r in W)))),
]
for n, c in cells.items():
    checks.append((f"cell{n} meas", f(c["pi_happy_mean"])))
    checks.append((f"cell{n} sd", f(c["pi_happy_sd"])))
    checks.append((f"cell{n} pred", f(c["pi_full"])))
    checks.append((f"cell{n} resid e4", f(1e4 * (c["pi_happy_mean"] - c["pi_full"]), 1)))
    checks.append((f"cell{n} votes", f(c["p_vote_mean"])))
    checks.append((f"cell{n} tmo", f(100 * c["timeout_fraction_mean"], 1)))
    checks.append((f"cell{n} trans", str(sum(r["happy_transitions"] for r in W if r["n"] == int(n)))))

bad = []
for name, text in checks:
    if strip_separators(text).lstrip("-+") not in tex:
        bad.append(name)
        print("MISSING in paper.tex:", name, text)
print(f"{len(checks) - len(bad)}/{len(checks)} quoted numbers verified against result files")
sys.exit(1 if bad else 0)
