#!/usr/bin/env bash
# Network testbed: a veth pair across a namespace, the XDP pre-arm program on
# the host side, a KME stub behind it, and a consensus client in the namespace.
#
# Requests for pre-armed pairs are answered by XDP and turned around without
# ever entering the host's network stack; everything else falls through to the
# stub. The client separates the two by the flag the kernel sets, so the two
# populations are distinguished by mechanism, not by a latency cutoff.
set -euo pipefail

NS=qkdns
HOST_IF=qkd0
PEER_IF=qkd1
HOST_IP=10.77.0.1
PEER_IP=10.77.0.2
PREFIX=24
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MAX_ENTRIES=${MAX_ENTRIES:-4096}
REQUESTS=${REQUESTS:-3000}
VALIDATORS=${VALIDATORS:-16}
ARM_FRACTION=${ARM_FRACTION:-0.5}
KME_DELAY_US=${KME_DELAY_US:-3000}
MODE=${MODE:-skb}

need_root() { [ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }; }

teardown() {
  set +e
  [ -n "${CTL_PID:-}" ] && kill "$CTL_PID" 2>/dev/null
  [ -n "${KME_PID:-}" ] && kill "$KME_PID" 2>/dev/null
  ip netns pids "$NS" 2>/dev/null | xargs -r kill 2>/dev/null
  ip link del "$HOST_IF" 2>/dev/null
  ip netns del "$NS" 2>/dev/null
  rm -f /tmp/prearm_ctl.in
  set -e
}

setup() {
  teardown
  ip netns add "$NS"
  ip link add "$HOST_IF" type veth peer name "$PEER_IF"
  ip link set "$PEER_IF" netns "$NS"
  ip addr add "$HOST_IP/$PREFIX" dev "$HOST_IF"
  ip link set "$HOST_IF" up
  ip netns exec "$NS" ip addr add "$PEER_IP/$PREFIX" dev "$PEER_IF"
  ip netns exec "$NS" ip link set "$PEER_IF" up
  ip netns exec "$NS" ip link set lo up
  # a static neighbour keeps ARP off the measured path
  ip neigh replace "$PEER_IP" lladdr "$(ip netns exec "$NS" cat /sys/class/net/$PEER_IF/address)" dev "$HOST_IF"
  ip netns exec "$NS" ip neigh replace "$HOST_IP" lladdr "$(cat /sys/class/net/$HOST_IF/address)" dev "$PEER_IF"
  echo "testbed: $NS($PEER_IP) <-> host($HOST_IP) on $HOST_IF"
}

main() {
  need_root
  cd "$ROOT"
  trap teardown EXIT
  setup

  python3 test/kme_stub.py --bind "$HOST_IP" --delay-us "$KME_DELAY_US" \
      > /tmp/kme.log 2>&1 &
  KME_PID=$!
  sleep 0.5

  mkfifo /tmp/prearm_ctl.in
  ./bpf/prearm_ctl --iface "$HOST_IF" --max-entries "$MAX_ENTRIES" --mode "$MODE" \
      < /tmp/prearm_ctl.in > /tmp/prearm_ctl.log 2>&1 &
  CTL_PID=$!
  exec 3>/tmp/prearm_ctl.in
  sleep 1.0
  grep -E "PROG|ATTACHED" /tmp/prearm_ctl.log || { cat /tmp/prearm_ctl.log; exit 1; }

  echo
  echo "--- arming ${ARM_FRACTION} of all validator pairs ---"
  python3 - "$VALIDATORS" "$ARM_FRACTION" >&3 <<'PY'
import sys, random
n = int(sys.argv[1]); frac = float(sys.argv[2])
random.seed(7)
pairs = [(a, b) for a in range(n) for b in range(a + 1, n)]
random.shuffle(pairs)
for a, b in pairs[:int(len(pairs) * frac)]:
    print(f"ARM {a} {b} 4000000 60000")
print("COMMIT BATCH")
PY
  sleep 0.7
  echo "COUNT" >&3
  sleep 0.3
  grep -E "COMMITTED|COUNT" /tmp/prearm_ctl.log | tail -3

  echo
  echo "--- running client from inside $NS ---"
  ip netns exec "$NS" "$ROOT/test/consensus_client" \
      --dst "$HOST_IP" --requests "$REQUESTS" --validators "$VALIDATORS"

  echo "STATS" >&3
  sleep 0.4
  echo
  grep "STATS" /tmp/prearm_ctl.log | tail -1
  echo "QUIT" >&3
  sleep 0.3
}

main "$@"
