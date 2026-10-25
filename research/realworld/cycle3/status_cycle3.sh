#!/usr/bin/env bash
# One-screen progress report for the Cycle-3 campaigns.
RW=/home/pocopepe/code/predictive/research/realworld
echo "E3T runs:       $(ls $RW/e3/raw_t/t_*.json 2>/dev/null | wc -l) / 72   (invalid set aside: $(ls $RW/e3/raw_t/invalid/*.json 2>/dev/null | wc -l))"
echo "Cosmos chunks:  $(ls $RW/cosmos/raw_bulk/chunk_*.json 2>/dev/null | wc -l) / 100"
echo "Aptos epochs:   $(ls $RW/raw_v3/epoch_*.json 2>/dev/null | wc -l) / 40   (full-epoch archive: $(ls $RW/raw_v3_full/*.gz 2>/dev/null | wc -l))"
echo "Stages done:    $(cd $RW/cycle3 && ls *.done 2>/dev/null | tr '\n' ' ')"
echo "Running:        $(pgrep -fc 'run_cycle3.sh') scheduler, $(pgrep -fc 'e3t_driver|cosmos_bulk_fetch|v3_fetch|v3_archive|cosmos_loss_sim|v3_analyze|cor2_activity') workers"
echo "Load (1 min):   $(cut -d' ' -f1 /proc/loadavg)"
tail -4 $RW/cycle3/logs/cycle3.log 2>/dev/null
