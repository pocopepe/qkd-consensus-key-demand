# Formula checks

Independent checks of every theorem, corollary, proposition and formula-derived number in `paper/paper.tex`, written by a checker
that re-derived each result and then enumerated or simulated the process the paper defines.

Run each script with a Python that has `sympy` (`pip install sympy`); the others need only the standard library:

    python3 thm1_lemma.py         # Theorem 1 over 66,178 realisations; Lemma 1 and its uniqueness condition   (sympy)
    python3 stake_cor.py          # stake-weighted corollary by exact enumeration; stake thresholds             (sympy)
    python3 coverage_prop.py      # coverage proposition on random histories; EWMA dominance condition          (sympy)
    python3 role_loss.py          # role-dependent vote loss: exact enumeration and Monte Carlo
    python3 stock.py              # base-stock on-hand formula against a simulated queue; round-robin depths
    python3 feasibility_numbers.py  keyrate_unrounded.py  heaviest_pair.py  stale_carryforward.py

All nine exit 0 on the submitted text (2026-10-13).
