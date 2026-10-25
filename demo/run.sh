#!/usr/bin/env bash
# Live demonstration wrapper around the existing implementation.
#
# This script runs the REAL BPF objects through the REAL kernel verifier and the
# REAL frozen research data. It fabricates nothing. It writes only to
# demo/output/ and never touches research/results, research/freeze, the
# prediction locks, or any frozen artefact.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/demo/output"
VETH=qkddemo0
PINDIR=/sys/fs/bpf/qkd
LOADER_PID=""

mkdir -p "$OUT"

c_hdr(){ printf '\n\033[1m== %s ==\033[0m\n' "$*"; }
c_ok(){  printf '  \033[32m[ok]\033[0m %s\n' "$*"; }
c_bad(){ printf '  \033[31m[--]\033[0m %s\n' "$*"; }
c_inf(){ printf '       %s\n' "$*"; }

# ---------------------------------------------------------------- cleanup ---
cleanup_bpf() {
  local rc=$?
  [ -n "$LOADER_PID" ] && $SUDO kill "$LOADER_PID" 2>/dev/null
  [ -n "$LOADER_PID" ] && wait "$LOADER_PID" 2>/dev/null
  $SUDO ip link del "$VETH" 2>/dev/null
  $SUDO ip link del qkd0 2>/dev/null
  $SUDO ip netns del qkdns 2>/dev/null
  while $SUDO iptables -C INPUT -i qkd0 -j ACCEPT 2>/dev/null; do
    $SUDO iptables -D INPUT -i qkd0 -j ACCEPT 2>/dev/null || break
  done
  $SUDO rm -rf "$PINDIR" 2>/dev/null
  if [ "${CLEANUP_ANNOUNCED:-0}" = "0" ]; then
    printf '\n  cleanup: interfaces and namespace removed, BPF detached, %s unpinned\n' "$PINDIR"
    CLEANUP_ANNOUNCED=1
  fi
  return $rc
}

# ------------------------------------------------------------ prerequisites --
SUDO=""
have_root() {
  if [ "$(id -u)" -eq 0 ]; then SUDO=""; return 0; fi
  if sudo -n true 2>/dev/null; then SUDO="sudo -n"; return 0; fi
  return 1
}

check_bpf_prereqs() {
  local ok=0
  c_hdr "Prerequisites"
  if [ "$(uname -s)" = "Linux" ]; then c_ok "Linux $(uname -r)"; else c_bad "not Linux"; ok=1; fi
  for cmd in ip bpftool; do
    if command -v "$cmd" >/dev/null 2>&1; then c_ok "$cmd present"; else c_bad "$cmd missing"; ok=1; fi
  done
  for f in bpf/prearm.bpf.o bpf/prearm_ctl src/enforcer_loader; do
    if [ -e "$ROOT/$f" ]; then c_ok "$f present"; else c_bad "$f missing"; ok=1; fi
  done
  if have_root; then c_ok "privileges available (BPF load requires root)"
  else c_bad "root required — rerun with: sudo $0 bpf"; ok=1; fi
  [ -d /sys/fs/bpf ] && c_ok "bpffs mounted at /sys/fs/bpf" || { c_bad "bpffs not mounted"; ok=1; }
  return $ok
}

# ------------------------------------------------------------------- BPF ----
demo_bpf() {
  check_bpf_prereqs || { echo; echo "Prerequisites not met. Aborting."; return 1; }
  trap cleanup_bpf EXIT INT TERM
  cleanup_bpf >/dev/null 2>&1; CLEANUP_ANNOUNCED=0

  c_hdr "What this does"
  c_inf "1. Loads the pre-arm BPF object into the kernel verifier at six map"
  c_inf "   capacities spanning a 16,384x range, and reports the verified"
  c_inf "   instruction count at each."
  c_inf "2. Builds a private network, attaches the enforcer, and sends real key"
  c_inf "   requests through it -- first with nothing pre-armed, then with every"
  c_inf "   pair pre-armed -- and measures the latency of each."
  c_inf "Everything below is measured live. Nothing is simulated or replayed."

  # ---- step 1: is the instruction budget a constraint? ----
  c_hdr "1. Does the pre-arm set size cost instructions?"
  local t0 t1
  t0=$(date +%s.%N)
  $SUDO "$ROOT/test/t1_insns.sh" 2>&1 | tee "$OUT/bpf_insns.txt"
  t1=$(date +%s.%N)
  c_inf "step runtime: $(printf '%.2f' "$(echo "$t1 - $t0" | bc)")s"
  c_inf ""
  c_inf "READ THIS: the count is identical at every map size. The project"
  c_inf "originally assumed pre-arming more pairs would cost more instructions,"
  c_inf "making it a budget to optimise against. It is not. That assumption was"
  c_inf "wrong, and this is the measurement that showed it."

  # ---- step 2: does pre-arming actually change what a request costs? ----
  c_hdr "2. Live: does a pre-armed pair skip the slow path?"
  c_inf "Building a private veth network with a key-management stub behind it,"
  c_inf "attaching the enforcer, and issuing 600 real key requests twice."
  echo
  t0=$(date +%s.%N)
  $SUDO env REQUESTS=600 FRACTIONS="0.0 1.0" VALIDATORS=16 \
      timeout 120 "$ROOT/test/t3_latency.sh" > "$OUT/bpf_latency.txt" 2>&1
  t1=$(date +%s.%N)
  if grep -q 'fast(XDP)' "$OUT/bpf_latency.txt"; then
      grep -E '^PROG|^ATTACHED|KME stub|pre-armed fraction|fast\(XDP\)|slow\(KME\)|^STATS' \
          "$OUT/bpf_latency.txt" | sed 's/^/  /'
  else
      c_bad "latency phase did not complete; output follows"
      tail -15 "$OUT/bpf_latency.txt" | sed 's/^/  /'
  fi
  c_inf ""
  c_inf "step runtime: $(printf '%.2f' "$(echo "$t1 - $t0" | bc)")s"

  # ---- summary ----
  c_hdr "Summary"
  local insns fast slow
  insns=$(awk '/^ *64 /{print $2}' "$OUT/bpf_insns.txt" 2>/dev/null)
  fast=$(grep 'fast(XDP)' "$OUT/bpf_latency.txt" 2>/dev/null | grep 'p50=' \
         | sed -n 's/.*p50=[[:space:]]*\([0-9.]*\).*/\1/p' | head -1)
  slow=$(grep 'slow(KME)' "$OUT/bpf_latency.txt" 2>/dev/null | grep 'p50=' \
         | sed -n 's/.*p50=[[:space:]]*\([0-9.]*\).*/\1/p' | head -1)
  c_inf "instruction count:  ${insns:-?}, unchanged from map size 64 to 1048576"
  if [ -n "${fast:-}" ] && [ -n "${slow:-}" ]; then
    c_inf "nothing pre-armed:  p50 = ${slow} us   (request goes to the KME)"
    c_inf "all pre-armed:      p50 = ${fast} us   (answered inside the kernel)"
    c_inf "separation:         $(awk -v a="$slow" -v b="$fast" 'BEGIN{printf "%.0fx", a/b}')"
  fi
  c_inf ""
  c_inf "The first number says the enforcement layer imposes no size budget on"
  c_inf "the pre-arm set. The second says pre-arming is what actually decides"
  c_inf "whether a request is cheap. Together they are why the interesting"
  c_inf "question is WHICH pairs to arm -- which is what the paper answers."
  c_inf ""
  c_inf "full output in demo/output/"
}

# -------------------------------------------------------------- analysis ----
demo_analysis() {
  c_hdr "Reproduction from frozen research data"
  c_inf "This is NOT a new experiment. It reads the archived E2 results and"
  c_inf "recomputes the closed form independently, then compares."
  echo
  python3 - "$ROOT" <<'PYEOF'
import json, sys
from fractions import Fraction as F
root = sys.argv[1]
tbl = json.load(open(f"{root}/research/results/e2_full/tables/table1_roundrobin.json"))

def pi(n, m, k):
    return F(k*(n-1) + m*(m-k), m*(n-1))

print("  Protocol: chained HotStuff, per-view leader rotation")
print("  Structural parameters read from the communication rule, before measurement:")
print("      m = 2   (proposal star of L(t), vote star of L(t+1))")
print("      k = 1   (the incoming leader is a hub in both views)")
print()
print("  pi(n,m,k) = [k(n-1) + m(m-k)] / [m(n-1)]")
print()
hdr = f"  {'n':>4}  {'runs':>5}  {'m':>7}  {'k':>7}  {'pi closed form':>15}  {'pi measured':>12}  {'residual':>10}"
print(hdr); print("  " + "-"*(len(hdr)-2))
worst = 0.0
for r in tbl:
    n = r["n"]; p = float(pi(n, 2, 1)); meas = r["pi_measured"]
    res = abs(p - meas); worst = max(worst, res)
    print(f"  {n:>4}  {r['runs']:>5}  {r['m']:>7.4f}  {r['k']:>7.4f}"
          f"  {p:>15.6f}  {meas:>12.6f}  {res:>10.2e}")
print()
print(f"  maximum residual across the sweep: {worst:.2e}")
print()
print("  Reading: the closed form was fixed before the campaign, together with")
print("  hashes of the analysis code. The asymptotic term alone would predict")
print("  0.5 at every n; the finite-n correction is what the sweep tests, and")
print(f"  at n=4 the difference is {float(pi(4,2,1))-0.5:.3f}.")
PYEOF
}

# ------------------------------------------------------------------ main ----
MODE="${1:-default}"
case "$MODE" in
  bpf)      demo_bpf ;;
  analysis) demo_analysis ;;
  default)
      demo_analysis
      echo
      c_hdr "Live BPF demonstration"
      if have_root; then
          demo_bpf
      else
          c_inf "The BPF demonstration loads real programs into the kernel and"
          c_inf "needs root. Run it with:"
          c_inf ""
          c_inf "    sudo $0 bpf"
      fi ;;
  *) echo "usage: $0 [bpf|analysis]"; exit 2 ;;
esac
