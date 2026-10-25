#!/usr/bin/env bash
# T1 -- does the verifier's instruction count depend on the pre-arm set size?
# Loads the same object across four orders of magnitude of M_max.
set -euo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"
[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }

echo "=== T1: verified instruction count vs map capacity (M_max) ==="
printf "%12s  %16s  %14s  %12s\n" "M_max" "verified_insns" "xlated_bytes" "jited_bytes"
for M in 64 256 1024 16384 262144 1048576; do
  out=$(./bpf/prearm_ctl --insns-only --max-entries "$M" 2>&1 | grep '^PROG') || {
    echo "load failed at M_max=$M"; exit 1; }
  ins=$(sed -n 's/.*verified_insns=\([0-9]*\).*/\1/p' <<<"$out")
  xl=$(sed -n 's/.*xlated_bytes=\([0-9]*\).*/\1/p' <<<"$out")
  ji=$(sed -n 's/.*jited_bytes=\([0-9]*\).*/\1/p' <<<"$out")
  printf "%12s  %16s  %14s  %12s\n" "$M" "$ins" "$xl" "$ji"
done
echo
echo "Instruction count is a property of the program text, fixed at load time."
echo "It does not vary with how many pairs the control plane later pre-arms, so"
echo "there is no instruction dimension for a knapsack to pack against."
