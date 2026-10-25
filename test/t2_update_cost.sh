#!/usr/bin/env bash
# T2 -- cost of changing the pre-arm set. Every changed entry is a syscall, so
# this sets U_max. Times both serial updates and BPF_MAP_UPDATE_BATCH.
set -euo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"
source test/lib.sh
need_root
trap 'net_teardown' EXIT

ip link set lo up
rm -f "$FIFO"; mkfifo "$FIFO"
./bpf/prearm_ctl --iface lo --max-entries 1048576 --mode skb \
    < "$FIFO" > "$CTL_LOG" 2>&1 &
CTL_PID=$!
exec 3>"$FIFO"
sleep 0.8
grep -q ATTACHED "$CTL_LOG" || { cat "$CTL_LOG"; exit 1; }

echo "=== T2: cost of committing a pre-arm plan ==="
printf "%10s  %14s  %14s  %14s  %14s\n" \
       "entries" "serial_us" "serial_ns/op" "batch_us" "batch_ns/op"

for N in 16 32 64 128 256 1024 4096; do
  for MODE in "COMMIT" "COMMIT BATCH"; do
    ctl "CLEAR"
    sleep 0.15
    python3 -c "
import sys
n=$N
for i in range(n):
    print(f'ARM {i//1000} {1000+i%1000} 4000000 60000')
" >&3
    ctl "$MODE"
    sleep 0.35
  done
  ser=$(grep COMMITTED "$CTL_LOG" | tail -2 | head -1)
  bat=$(grep COMMITTED "$CTL_LOG" | tail -1)
  sw=$(sed -n 's/.*wall_ns=\([0-9]*\).*/\1/p' <<<"$ser")
  sp=$(sed -n 's/.*ns_per_op=\([0-9.]*\).*/\1/p' <<<"$ser")
  bw=$(sed -n 's/.*wall_ns=\([0-9]*\).*/\1/p' <<<"$bat")
  bp=$(sed -n 's/.*ns_per_op=\([0-9.]*\).*/\1/p' <<<"$bat")
  printf "%10s  %14.1f  %14s  %14.1f  %14s\n" \
         "$N" "$(echo "$sw/1000"|bc -l)" "$sp" "$(echo "$bw/1000"|bc -l)" "$bp"
done

echo
echo "U_max is this rate times the view budget. At a 250 ms view spending 1% of"
echo "it on map updates, the serial column gives the number of entries the"
echo "control plane may revise per view -- which is what the pre-arm selection"
echo "has to be solved against."
ctl "QUIT"; sleep 0.3
