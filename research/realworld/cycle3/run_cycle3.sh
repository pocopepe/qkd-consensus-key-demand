#!/usr/bin/env bash
# Cycle-3 campaigns.  Usage: run_cycle3.sh prefetch|all|archive
#   prefetch  download the held-out data only (Cosmos range, Aptos epochs); no experiment, no analysis
#   all       everything: downloads (resumed if already started), emulation, analyses
#   archive   Aptos full-epoch archive (raw_v3_full/; sensible only with an API key; not analysed by the locks)
# Everything runs on logical CPUs 6-15 (taskset) at nice 10; CPUs 0-5 stay free. Safe to re-run after a crash or
# reboot: finished streams are skipped, fetchers resume, the emulation driver skips finished runs. One instance only.
set -uo pipefail
MODE=${1:-}; [[ "$MODE" =~ ^(prefetch|all|archive)$ ]] || { echo "usage: $0 prefetch|all|archive"; exit 2; }
RW=/home/pocopepe/code/predictive/research/realworld; C3=$RW/cycle3; L=$C3/logs; mkdir -p "$L"
exec 8>"$C3/.instance.lock"; flock -n 8 || { echo "another run_cycle3.sh is already running"; exit 1; }
PIN="taskset -c 6-15 nice -n 10"
stamp() { date -u +%FT%TZ; }
say() { echo "$(stamp) [$MODE] $*" | tee -a "$L/cycle3.log"; }
[ "$(df --output=avail -BG /home | tail -1 | tr -dc 0-9)" -ge 5 ] || { say "less than 5 GB free - not starting"; exit 1; }
python3 "$C3/verify_locks.py" "$RW/e3/PREDICTION_LOCK_E3T.md" "$RW/theory/PREDICTION_LOCK_C1.md" "$RW/PREDICTION_LOCK_V3.md" > "$L/verify_locks.log" 2>&1 \
  || { say "LOCK VERIFICATION FAILED - nothing started (see verify_locks.log)"; exit 1; }
say "locks verified; starting"
passes() {   # passes <name> <donefile> <cmd...>: retry an incomplete fetch up to 6 times, 5 min apart
  local name=$1 done=$2; shift 2
  [ -f "$done" ] && { say "$name already complete"; return 0; }
  for p in 1 2 3 4 5 6; do
    "$@" >> "$L/$name.log" 2>&1 && { touch "$done"; say "$name complete (pass $p)"; return 0; }
    say "$name incomplete after pass $p; retrying in 5 min"; sleep 300
  done
  say "$name STILL INCOMPLETE after 6 passes"; return 1
}
cosmos() { cd "$RW/cosmos" && passes cosmos_fetch "$C3/cosmos_fetch.done" $PIN python3 cosmos_bulk_fetch.py; }
aptos()  { cd "$RW" && passes aptos_fetch "$C3/aptos_fetch.done" $PIN python3 v3_fetch.py; }
if [ "$MODE" = archive ]; then
  cd "$RW" && passes aptos_archive "$C3/archive.done" $PIN python3 v3_archive.py; exit $?
fi
if [ "$MODE" = prefetch ]; then
  cosmos & aptos & wait; say "prefetch finished"; exit 0
fi
# MODE=all
rm -f "$C3/e3t.finished"
( if [ ! -f "$C3/e3t.done" ]; then
    cd "$RW/e3" && $PIN python3 e3t_driver.py heldout >> "$L/e3t_runs.log" 2>&1
    runs=$(ls "$RW/e3/raw_t"/t_*.json 2>/dev/null | wc -l)
    if $PIN python3 e3t_analyze.py raw_t E3T_RESULTS.json > "$L/e3t_analysis.log" 2>&1 && [ "$runs" -eq 72 ]; then
      touch "$C3/e3t.done"; say "E3T finished: 72/72 runs (results: e3/E3T_RESULTS.json)"
    else
      say "E3T INCOMPLETE: $runs/72 runs or analysis error (see e3t_runs.log, e3t_analysis.log); re-run the scheduler to resume"
    fi
  fi
  touch "$C3/e3t.finished" ) &
( cosmos
  until [ -f "$C3/e3t.finished" ]; do sleep 30; done
  if [ ! -f "$C3/c1.done" ]; then
    ( flock 9; cd "$RW/theory" && WORKERS=10 $PIN python3 cosmos_loss_sim.py ../cosmos/raw_bulk C1_SIM.json > "$L/c1_sim.log" 2>&1 \
      && $PIN python3 c1_verdicts.py C1_SIM.json C1_RESULTS.json > "$L/c1_verdicts.log" 2>&1 && touch "$C3/c1.done" ) 9>"$C3/.cpu.lock"
    say "C1 finished (results: theory/C1_RESULTS.json)"
  fi ) &
( aptos
  if [ -s "$HOME/.config/predictive/aptos_api_key" ] && [ ! -f "$C3/archive.done" ]; then    # large local archive; not analysed by the locks
    ( cd "$RW" && passes aptos_archive "$C3/archive.done" $PIN python3 v3_archive.py ) &
  fi
  until [ -f "$C3/e3t.finished" ]; do sleep 30; done
  if [ ! -f "$C3/v3.done" ]; then
    ( flock 9; cd "$RW" && WORKERS=10 $PIN python3 v3_analyze.py raw_v3 V3_RESULTS.json > "$L/v3_analysis.log" 2>&1 && touch "$C3/v3.done" ) 9>"$C3/.cpu.lock"
    say "V3 replication finished (results: V3_RESULTS.json)"
  fi
  wait ) &
wait; say "ALL STREAMS FINISHED"
