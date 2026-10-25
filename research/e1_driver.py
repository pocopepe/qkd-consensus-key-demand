#!/usr/bin/env python3
"""Resumable E1 campaign driver.

Written after the shell version was repeatedly killed by process-group cleanup:
this one records each completed run to disk immediately and skips work already
done, so relaunching resumes rather than restarting.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time

ROOT = "/home/pocopepe/code/predictive"
CB = f"{ROOT}/ext/cometbft/build/cometbft"
OUT = f"{ROOT}/research/results/e1/raw"


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)


def patch(net, n, commit_ms):
    for i in range(n):
        ip = f"127.0.0.{i+1}"
        p = f"{net}/node{i}/config/config.toml"
        s = open(p).read()
        s = s.replace('laddr = "tcp://127.0.0.1:26657"', f'laddr = "tcp://{ip}:26657"')
        s = s.replace('laddr = "tcp://0.0.0.0:26656"', f'laddr = "tcp://{ip}:26656"')
        s = s.replace('external_address = ""', f'external_address = "{ip}:26656"')
        s = s.replace('addr_book_strict = true', 'addr_book_strict = false')
        s = s.replace('allow_duplicate_ip = false', 'allow_duplicate_ip = true')
        s = s.replace('timeout_commit = "1s"', f'timeout_commit = "{commit_ms}ms"')
        open(p, "w").write(s)


def one_run(n, run, target, commit_ms, max_wait):
    tag = f"n{n}_run{run}"
    dest = f"{OUT}/comet_{tag}.json"
    if os.path.exists(dest):
        print(f"  {tag}: already done, skipping", flush=True)
        return
    net, logs = f"/tmp/e1net_{tag}", f"/tmp/e1logs_{tag}"
    sh("pkill -f 'cometbft start'"); time.sleep(2)
    shutil.rmtree(net, ignore_errors=True); shutil.rmtree(logs, ignore_errors=True)
    os.makedirs(logs, exist_ok=True)
    sh(f"{CB} testnet --v {n} --o {net} --populate-persistent-peers "
       f"--starting-ip-address 127.0.0.1")
    patch(net, n, commit_ms)
    procs = []
    for i in range(n):
        f = open(f"{logs}/node{i}.log", "w")
        procs.append(subprocess.Popen(
            [CB, "start", "--home", f"{net}/node{i}", "--proxy_app=kvstore",
             "--log_level=p2p:debug,consensus:info,*:error"],
            stdout=f, stderr=subprocess.STDOUT, start_new_session=True))
    t0 = time.time()
    h = 0
    while time.time() - t0 < max_wait:
        time.sleep(5)
        r = sh(f"grep -c 'finalizing commit' {logs}/node0.log")
        try:
            h = int(r.stdout.strip() or 0)
        except ValueError:
            h = 0
        if h >= target:
            break
    for p in procs:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except Exception:
            pass
    sh("pkill -f 'cometbft start'"); time.sleep(2)
    print(f"  {tag}: {h} blocks in {time.time()-t0:.0f}s", flush=True)
    sh(f"python3 {ROOT}/research/e1_parse.py {logs} {net} {dest}")
    shutil.rmtree(logs, ignore_errors=True); shutil.rmtree(net, ignore_errors=True)


def main():
    ns = [int(x) for x in (sys.argv[1] if len(sys.argv) > 1 else "4,7,10,16").split(",")]
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    target = int(sys.argv[3]) if len(sys.argv) > 3 else 800
    os.makedirs(OUT, exist_ok=True)
    for n in ns:
        for r in range(1, runs + 1):
            print(f"n={n} run={r}", flush=True)
            one_run(n, r, target, 100, max_wait=420)
    print("DRIVER_DONE", flush=True)


if __name__ == "__main__":
    main()
