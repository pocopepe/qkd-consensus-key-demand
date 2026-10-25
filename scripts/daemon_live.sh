#!/usr/bin/env bash
# Live test: load the enforcer, pin its maps, and drive them from the Python
# daemon with native bpf() calls while real consensus traffic flows.
set -euo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"
source test/lib.sh
need_root
trap 'net_teardown; ./src/enforcer_loader --iface '"${HOST_IF}"' --detach >/dev/null 2>&1 || true' EXIT

VIEWS=${VIEWS:-120}
REQUESTS=${REQUESTS:-3000}
mount -t bpf bpf /sys/fs/bpf 2>/dev/null || true

net_setup
start_kme

./src/enforcer_loader --iface "$HOST_IF" --max-entries 4096 --mode skb
echo

echo "--- daemon: forecasting and committing to kernel maps ---"
python3 src/daemon.py --views "$VIEWS" --validators 16 --max-updates 64 &
DPID=$!
sleep 3

echo
echo "--- consensus client through the live enforcer ---"
ip netns exec "$NS" ./test/consensus_client --dst "$HOST_IP" \
    --requests "$REQUESTS" --validators 16 --timeout-ms 300 || true

wait $DPID 2>/dev/null || true
