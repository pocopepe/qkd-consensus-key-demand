#!/usr/bin/env python3
"""Run every experiment and write results/*.txt."""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXPS = ["exp1_forecast", "exp2_endtoend", "exp3_budgets", "exp4_sidechannel"]

os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
for e in EXPS:
    print(f"--- {e} ---", flush=True)
    out = subprocess.run([sys.executable, os.path.join(HERE, "experiments", f"{e}.py")],
                         capture_output=True, text=True)
    path = os.path.join(HERE, "results", f"{e.split('_')[0]}.txt")
    with open(path, "w") as fh:
        fh.write(out.stdout + out.stderr)
    print(out.stdout)
    if out.returncode:
        print(out.stderr, file=sys.stderr)
