#!/usr/bin/env bash
# E1 campaign: N validator counts x R runs, each collecting >= TARGET views.
# timeout_commit is lowered to produce views faster. This changes timing, not
# the per-view message graph, and is recorded in the report as a deviation.
set -u
CB=/home/pocopepe/code/predictive/ext/cometbft/build/cometbft
OUT=/home/pocopepe/code/predictive/research/results/e1/raw
RUNS=${RUNS:-5}
TARGET=${TARGET:-1000}
COMMIT_MS=${COMMIT_MS:-150}
mkdir -p "$OUT"

for N in ${NS:-4 7 10 16}; do
for RUN in $(seq 1 $RUNS); do
  TAG="n${N}_run${RUN}"
  NET=/tmp/e1net_$TAG
  LOGS=/tmp/e1logs_$TAG
  pkill -f "cometbft start" >/dev/null 2>&1; sleep 2
  rm -rf "$NET" "$LOGS"; mkdir -p "$LOGS"
  $CB testnet --v $N --o "$NET" --populate-persistent-peers \
      --starting-ip-address 127.0.0.1 >/dev/null 2>&1
  python3 - "$N" "$NET" "$COMMIT_MS" <<'PY'
import sys
n, net, cms = int(sys.argv[1]), sys.argv[2], sys.argv[3]
for i in range(n):
    ip = f"127.0.0.{i+1}"
    p = f"{net}/node{i}/config/config.toml"
    s = open(p).read()
    s = s.replace('laddr = "tcp://127.0.0.1:26657"', f'laddr = "tcp://{ip}:26657"')
    s = s.replace('laddr = "tcp://0.0.0.0:26656"', f'laddr = "tcp://{ip}:26656"')
    s = s.replace('external_address = ""', f'external_address = "{ip}:26656"')
    s = s.replace('addr_book_strict = true', 'addr_book_strict = false')
    s = s.replace('allow_duplicate_ip = false', 'allow_duplicate_ip = true')
    s = s.replace('timeout_commit = "1s"', f'timeout_commit = "{cms}ms"')
    open(p, 'w').write(s)
PY
  for i in $(seq 0 $((N-1))); do
    setsid $CB start --home "$NET/node$i" --proxy_app=kvstore \
      --log_level=debug > "$LOGS/node$i.log" 2>&1 < /dev/null &
  done
  # wait until target height or timeout
  for _ in $(seq 1 120); do
    sleep 5
    H=$(grep -c "finalizing commit of block" "$LOGS/node0.log" 2>/dev/null || echo 0)
    [ "$H" -ge "$TARGET" ] && break
  done
  pkill -f "cometbft start" >/dev/null 2>&1; sleep 2
  echo "$TAG heights=$(grep -c 'finalizing commit of block' $LOGS/node0.log)" >> /tmp/e1_campaign.log
  python3 /home/pocopepe/code/predictive/research/e1_parse.py \
      "$LOGS" "$NET" "$OUT/comet_${TAG}.json" >> /tmp/e1_campaign.log 2>&1
  rm -rf "$LOGS" "$NET"
done
done
echo CAMPAIGN_DONE >> /tmp/e1_campaign.log
