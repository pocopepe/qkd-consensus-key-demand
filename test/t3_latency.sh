#!/usr/bin/env bash
# T3 -- end to end: does a pre-armed pair skip the slow path? Armed pairs are
# answered by XDP without entering the host stack; misses go to the KME stub.
set -euo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"
source test/lib.sh
need_root
trap 'net_teardown' EXIT

MAX_ENTRIES=${MAX_ENTRIES:-4096}
REQUESTS=${REQUESTS:-4000}
VALIDATORS=${VALIDATORS:-16}
KME_DELAY_US=${KME_DELAY_US:-3000}
MODE=${MODE:-skb}

net_setup
start_kme
start_ctl "$HOST_IF" "$MAX_ENTRIES" "$MODE"
grep -E '^PROG|^ATTACHED' "$CTL_LOG"
echo "KME stub delay: ${KME_DELAY_US} us (modelled ETSI GS QKD 014 round trip)"

for FRAC in ${FRACTIONS:-0.0 0.25 0.5 0.75 1.0}; do
  ctl "CLEAR"; sleep 0.2
  python3 - "$VALIDATORS" "$FRAC" >&3 <<'PY'
import sys, random
n = int(sys.argv[1]); frac = float(sys.argv[2])
random.seed(7)
pairs = [(a, b) for a in range(n) for b in range(a + 1, n)]
random.shuffle(pairs)
k = int(round(len(pairs) * frac))
for a, b in pairs[:k]:
    print(f"ARM {a} {b} 400000000 60000")
print("COMMIT BATCH")
PY
  sleep 0.5
  echo
  echo "############ pre-armed fraction of pairs: $FRAC ############"
  ip netns exec "$NS" "$ROOT/test/consensus_client" \
      --dst "$HOST_IP" --requests "$REQUESTS" --validators "$VALIDATORS" \
      --timeout-ms 300
done

ctl "STATS"; sleep 0.4
echo; grep STATS "$CTL_LOG" | tail -1
ctl "QUIT"; sleep 0.3
