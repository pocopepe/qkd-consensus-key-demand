#!/usr/bin/env python3
"""Measure the real cost of an ETSI GS QKD 014 key fetch.

Four configurations, because the interesting question is not one number but
where the number comes from:

  cold TLS      a fresh handshake per request -- what an unpooled SAE pays
  resumed TLS   session reuse across requests
  pooled HTTP   one connection, keep-alive, many requests
  plaintext     the same API without TLS, to separate crypto from protocol

The fast path this is compared against is 14.2 us, measured in the kernel.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import ssl
import statistics
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kme.etsi_kme import make_certs, serve


def client_ctx(certdir, mutual=True):
    _, _, ca_crt, c_crt, c_key = make_certs(certdir)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(ca_crt)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    if mutual:
        ctx.load_cert_chain(c_crt, c_key)
    return ctx


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(len(v) * p / 100))]


def run_case(name, host, port, n, ctx, reuse_conn, reuse_session):
    lat = []
    sess = None
    conn = None
    fails = 0
    for i in range(n):
        t0 = time.perf_counter()
        try:
            if conn is None or not reuse_conn:
                if conn is not None:
                    conn.close()
                if ctx is None:
                    conn = http.client.HTTPConnection(host, port, timeout=5)
                else:
                    conn = http.client.HTTPSConnection(
                        host, port, context=ctx, timeout=5)
                    if reuse_session and sess is not None:
                        try:
                            conn.sock = ctx.wrap_socket(
                                conn._create_connection((host, port)),
                                server_hostname=host, session=sess)
                        except Exception:
                            pass
            if getattr(conn, "sock", None) is None:
                conn.connect()
            try:
                import socket as _s
                conn.sock.setsockopt(_s.IPPROTO_TCP, _s.TCP_NODELAY, 1)
            except Exception:
                pass
            conn.request("GET", "/api/v1/keys/SAE-B/enc_keys?number=1&size=352")
            r = conn.getresponse()
            body = r.read()
            if r.status != 200:
                fails += 1
            else:
                json.loads(body)
            if reuse_session and getattr(conn, "sock", None) is not None:
                try:
                    sess = conn.sock.session
                except Exception:
                    pass
            if not reuse_conn:
                conn.close()
                conn = None
        except Exception:
            fails += 1
            try:
                conn.close()
            except Exception:
                pass
            conn = None
        lat.append((time.perf_counter() - t0) * 1e6)
    if conn is not None:
        conn.close()
    return {"case": name, "n": n, "fails": fails,
            "mean_us": statistics.mean(lat), "p50_us": pct(lat, 50),
            "p99_us": pct(lat, 99), "min_us": min(lat)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--requests", type=int, default=400)
    ap.add_argument("--port", type=int, default=18443)
    a = ap.parse_args()
    certdir = "/tmp/qkd_certs"

    rows = []
    # --- TLS server (mutual) ---
    httpd = serve("127.0.0.1", a.port, certdir=certdir, mutual_tls=True)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    time.sleep(0.6)
    ctx = client_ctx(certdir, mutual=True)
    rows.append(run_case("cold mTLS handshake", "127.0.0.1", a.port,
                         a.requests, ctx, reuse_conn=False, reuse_session=False))
    rows.append(run_case("mTLS, session reuse", "127.0.0.1", a.port,
                         a.requests, ctx, reuse_conn=False, reuse_session=True))
    rows.append(run_case("mTLS, pooled connection", "127.0.0.1", a.port,
                         a.requests, ctx, reuse_conn=True, reuse_session=True))
    httpd.shutdown()

    # --- plaintext server, to separate crypto cost from protocol cost ---
    import http.server as hs
    from kme.etsi_kme import Handler, KeyStore
    Handler.store = KeyStore()
    plain = hs.ThreadingHTTPServer(("127.0.0.1", a.port + 1), Handler)
    t2 = threading.Thread(target=plain.serve_forever, daemon=True)
    t2.start()
    time.sleep(0.4)
    rows.append(run_case("plaintext, pooled", "127.0.0.1", a.port + 1,
                         a.requests, None, reuse_conn=True, reuse_session=False))
    plain.shutdown()

    print(f"\n=== ETSI GS QKD 014 key fetch, measured ({a.requests} requests each) ===")
    print(f"{'configuration':<26}{'mean us':>10}{'p50 us':>10}{'p99 us':>10}"
          f"{'min us':>10}{'errors':>8}")
    for r in rows:
        print(f"{r['case']:<26}{r['mean_us']:>10.1f}{r['p50_us']:>10.1f}"
              f"{r['p99_us']:>10.1f}{r['min_us']:>10.1f}{r['fails']:>8}")

    FAST_US = 14.2
    print(f"\nXDP fast path (measured, in kernel): {FAST_US} us")
    for r in rows:
        print(f"  vs {r['case']:<26} speedup at p50 = {r['p50_us']/FAST_US:8.1f}x")

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "results", "kme_bench.json")
    with open(out, "w") as f:
        json.dump({"fast_path_us": FAST_US, "cases": rows}, f, indent=2)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
