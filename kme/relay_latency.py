#!/usr/bin/env python3
# How long does it take to relay one key over h trusted-relay hops through an ETSI GS QKD 014 key management
# entity? At every hop the sending node fetches a link key (Get key), encrypts the relayed key with it, and the
# receiving node fetches the same key by its ID (Get key with key IDs) and decrypts: two KME calls per hop over
# mutual TLS on a pooled connection. Loopback only, so the result is a lower bound on a real network; an optional
# per-hop delay stands in for one network round trip.
# usage: relay_latency.py [out.json]
import base64
import http.client
import json
import os
import socket
import ssl
import statistics
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from kme.etsi_kme import make_certs, serve

PORT = 18453
HOPS = (1, 2, 4, 8, 16, 42)
RTT_MS = (0.0, 1.0, 5.0)
REPEATS = 200
KEY_BITS = 128


def connection(certdir):
    _, _, ca, crt, key = make_certs(certdir)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(ca)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.load_cert_chain(crt, key)
    conn = http.client.HTTPSConnection("127.0.0.1", PORT, context=ctx, timeout=10)
    conn.connect()
    conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return conn


def get_key(conn):
    conn.request("GET", f"/api/v1/keys/SAE-B/enc_keys?number=1&size={KEY_BITS}")
    r = conn.getresponse()
    body = json.loads(r.read())
    assert r.status == 200, body
    return body["keys"][0]


def get_by_id(conn, key_id):
    conn.request("POST", "/api/v1/keys/SAE-A/dec_keys", body=json.dumps({"key_IDs": [{"key_ID": key_id}]}),
                 headers={"Content-Type": "application/json"})
    r = conn.getresponse()
    body = json.loads(r.read())
    assert r.status == 200, body
    return body["keys"][0]


def relay(conn, hops, rtt_s, payload):
    for _ in range(hops):
        k = get_key(conn)
        pad = base64.b64decode(k["key"])
        wrapped = bytes(a ^ b for a, b in zip(payload, pad))
        if rtt_s:
            time.sleep(rtt_s)
        k2 = get_by_id(conn, k["key_ID"])
        payload = bytes(a ^ b for a, b in zip(wrapped, base64.b64decode(k2["key"])))
    return payload


def main():
    certdir = "/tmp/qkd_certs_relay"
    httpd = serve("127.0.0.1", PORT, certdir=certdir, rate_bps=1e9, mutual_tls=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.5)
    conn = connection(certdir)
    payload = os.urandom(KEY_BITS // 8)
    assert relay(conn, 3, 0.0, payload) == payload
    out = {"note": "loopback; two KME calls per hop over pooled mutual TLS; rtt_ms is a sleep per hop", "rows": []}
    for rtt in RTT_MS:
        for hops in HOPS:
            lat = []
            for _ in range(REPEATS):
                t0 = time.perf_counter()
                relay(conn, hops, rtt / 1000.0, payload)
                lat.append((time.perf_counter() - t0) * 1e3)
            lat.sort()
            row = {"rtt_ms": rtt, "hops": hops, "repeats": REPEATS, "p50_ms": statistics.median(lat),
                   "p99_ms": lat[int(0.99 * (REPEATS - 1))], "mean_ms": statistics.mean(lat), "max_ms": lat[-1]}
            out["rows"].append(row)
            print(f"rtt {rtt:4.1f} ms  {hops:2d} hops: p50 {row['p50_ms']:8.2f} ms  p99 {row['p99_ms']:8.2f} ms  max {row['max_ms']:8.2f} ms", flush=True)
    httpd.shutdown()
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "RELAY_LATENCY.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
