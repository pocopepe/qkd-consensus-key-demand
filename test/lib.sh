# Shared testbed setup, sourced by the t*.sh scripts.
#
# Note: ufw defaults to DROP on INPUT but permits ICMP, so the namespace pings
# fine while every UDP probe vanishes. We insert one ACCEPT scoped to the test
# veth and remove it on teardown.

NS=${NS:-qkdns}
HOST_IF=${HOST_IF:-qkd0}
PEER_IF=${PEER_IF:-qkd1}
HOST_IP=${HOST_IP:-10.77.0.1}
PEER_IP=${PEER_IP:-10.77.0.2}
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIFO=/tmp/prearm_ctl.in
CTL_LOG=/tmp/prearm_ctl.log
KME_LOG=/tmp/kme.log

need_root() { [ "$(id -u)" -eq 0 ] || { echo "ERROR: run with sudo" >&2; exit 1; }; }

fw_open()  { iptables -C INPUT -i "$HOST_IF" -j ACCEPT 2>/dev/null || \
             iptables -I INPUT 1 -i "$HOST_IF" -j ACCEPT; }
fw_close() { while iptables -C INPUT -i "$HOST_IF" -j ACCEPT 2>/dev/null; do
               iptables -D INPUT -i "$HOST_IF" -j ACCEPT; done; }

net_teardown() {
  set +e
  [ -n "${CTL_PID:-}" ] && kill "$CTL_PID" 2>/dev/null
  [ -n "${KME_PID:-}" ] && kill "$KME_PID" 2>/dev/null
  exec 3>&- 2>/dev/null
  ip netns pids "$NS" 2>/dev/null | xargs -r kill -9 2>/dev/null
  fw_close
  ip link del "$HOST_IF" 2>/dev/null
  ip netns del "$NS" 2>/dev/null
  rm -f "$FIFO"
  set -e
}

net_setup() {
  net_teardown
  ip netns add "$NS"
  ip link add "$HOST_IF" type veth peer name "$PEER_IF"
  ip link set "$PEER_IF" netns "$NS"
  ip addr add "$HOST_IP/24" dev "$HOST_IF"
  ip link set "$HOST_IF" up
  ip netns exec "$NS" ip addr add "$PEER_IP/24" dev "$PEER_IF"
  ip netns exec "$NS" ip link set "$PEER_IF" up
  ip netns exec "$NS" ip link set lo up
  sysctl -qw "net.ipv4.conf.$HOST_IF.rp_filter=0" 2>/dev/null || true
  fw_open
  # static neighbours keep ARP resolution off the measured path
  ip neigh replace "$PEER_IP" \
     lladdr "$(ip netns exec "$NS" cat /sys/class/net/$PEER_IF/address)" dev "$HOST_IF"
  ip netns exec "$NS" ip neigh replace "$HOST_IP" \
     lladdr "$(cat /sys/class/net/$HOST_IF/address)" dev "$PEER_IF"
}

start_kme() {
  python3 "$ROOT/test/kme_stub.py" --bind "$HOST_IP" \
      --delay-us "${KME_DELAY_US:-3000}" > "$KME_LOG" 2>&1 &
  KME_PID=$!
  sleep 0.6
}

# start_ctl <iface> <max_entries> [mode] -- leaves fd 3 open as the command channel
start_ctl() {
  local iface=$1 maxe=$2 mode=${3:-skb}
  rm -f "$FIFO"; mkfifo "$FIFO"
  "$ROOT/bpf/prearm_ctl" --iface "$iface" --max-entries "$maxe" --mode "$mode" \
      < "$FIFO" > "$CTL_LOG" 2>&1 &
  CTL_PID=$!
  exec 3>"$FIFO"
  sleep 0.8
  if ! grep -q ATTACHED "$CTL_LOG"; then
    echo "ERROR: XDP attach failed" >&2; cat "$CTL_LOG" >&2; return 1
  fi
}

ctl() { echo "$*" >&3; }
