#!/usr/bin/env bash
# Validates the auto-expiring lease: arm pairs, send no traffic to some of them,
# and confirm the data plane reclaims exactly the silent ones and credits their
# validators rather than leaving them starved.
set -euo pipefail
cd "$(cd "$(dirname "$0")/.." && pwd)"
source test/lib.sh
need_root
trap 'net_teardown; ./src/enforcer_loader --iface qkd0 --detach >/dev/null 2>&1 || true' EXIT
mount -t bpf bpf /sys/fs/bpf 2>/dev/null || true
net_setup
start_kme
./src/enforcer_loader --iface "$HOST_IF" --max-entries 4096 --mode skb
python3 - <<'PY'
import sys, time
sys.path.insert(0, '.')
from src.daemon import _Libbpf, KernelPlane

kp = KernelPlane(_Libbpf())
for v in range(16):
    kp.set_token_bucket(v, 4_000_000, 2_000_000)

# 40 pairs, 300 ms lease, 400 ms hard ceiling
pairs = [(a, b) for a in range(16) for b in range(a+1, 16)][:40]
for a, b in pairs:
    kp.arm(a, b, 400_000, lease_ms=300, max_life_ms=400)
print(f"armed {len(kp.live_pairs())} pairs, lease=300ms ceiling=400ms")

s0 = kp.read_stats()
print(f"t=0.0s  live={len(kp.live_pairs()):3d}  gc_reclaimed={s0['gc_reclaimed']}")
for t in (0.5, 1.0):
    time.sleep(0.5)
    st = kp.read_stats()
    print(f"t={t:.1f}s  live={len(kp.live_pairs()):3d}  gc_reclaimed={st['gc_reclaimed']}"
          f"  (no traffic: GC needs packets to run)")
PY
echo
echo "--- now drive packets so the amortised sweep executes ---"
ip netns exec "$NS" ./test/consensus_client --dst "$HOST_IP" --requests 400 \
    --validators 16 --timeout-ms 200 | tail -4
python3 - <<'PY'
import sys; sys.path.insert(0, '.')
from src.daemon import _Libbpf, KernelPlane
kp = KernelPlane(_Libbpf())
st = kp.read_stats()
print(f"\nafter traffic: live={len(kp.live_pairs()):3d}  gc_reclaimed={st['gc_reclaimed']}"
      f"  expired={st['expired']}  renewals={st['renewals']}")
cred = sum((kp.read_token_bucket(v) or {}).get('starved_credits', 0) for v in range(16))
print(f"starvation credits handed back to the daemon: {cred}")
PY
