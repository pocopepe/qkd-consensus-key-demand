#!/usr/bin/env bash
# Reproducible build of the E3T emulator: relab/hotstuff at 3179c6e6 + frozen E2 logging
# patch + per-message-delay fix + vote-suppression injector. Usage: build_e3t.sh <out-binary>
set -euo pipefail
RW=$(cd "$(dirname "$0")/.." && pwd); SRC=/home/pocopepe/code/predictive/ext/relab-hotstuff
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
git clone -q --shared "$SRC" "$T/hs" && cd "$T/hs" && git checkout -q 3179c6e6
git -C "$SRC" diff -- protocol/comm/clique.go protocol/comm/factory.go protocol/synchronizer/synchronizer.go twins/node.go > "$T/e2.diff"
git apply "$T/e2.diff"; git apply "$RW/e3/emulation_fix.diff"; git apply "$RW/e3/e3t_injector.diff"
GOFLAGS=-mod=mod go build -trimpath -buildvcs=false -o "$1" ./cmd/hotstuff
