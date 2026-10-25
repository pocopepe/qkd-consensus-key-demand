# Prediction lock — H7 (provisioning loop on the real Aptos leader schedule)

Written 2026-09-18T23:32:45Z. Developed on two synthetic i.i.d. stake-weighted
schedules only (`SYNTH` mode); not yet run on any held-out epoch. The frozen
`research/e4_operational.py::run` is used unmodified; only its schedule source
is replaced by the real hubs {L(t), L(t+1)} from the first ten v2 epochs (by
epoch number), 300 views, warm-up 40, R in {256..65536} — the frozen Q1 sweep.

Locked predictions (paper claim C4 on a production schedule):
1. **Key supply cannot move the prediction-attributable ceiling**: carry-forward
   hit rate varies by <= 0.005 across the 256x key-rate sweep, in every epoch.
2. **The ceiling is set by schedule structure**: it never exceeds the
   schedule-implied pair-level carry rate (computed with no pools or rates) and
   lies within 0.02 below it in every epoch. (Development note: a first draft
   compared the ceiling with the demand-weighted E[pi]; the synthetic run showed
   that is the wrong target — the frozen loop counts hits per pair and truncates
   arming to K_t pairs — and the target was corrected before any real epoch was run.)
3. **A schedule-aware predictor is not so bounded**: hit rate >= 0.999 at the top rate.

    h7_provisioning.py      b0c5fb743897933f550982218881768bac9a810a9e8c0296cefda236d3379503
    ../e4_operational.py    dd2b436a43b7f701729197a38813c167b4cc8bb8733759122047cbe95996759b
    v2_analyze.py           5deb73ed54a43ce2096451286ab20972aafd95df8d8587883772d55ef207109f
