#!/usr/bin/env python3
"""An ETSI GS QKD 014 compliant Key Management Entity, over TLS.

The point of building this rather than assuming a constant: the slow path in
every measurement so far was a 3 ms figure taken from the literature. That makes
the headline a ratio between one measurement and one assumption. A real KME
exposes the actual cost -- TLS session establishment, HTTP framing, JSON
encoding, base64 key material, and the key-store lookup -- so both sides of the
comparison are measured.

Implements the three resources of the specification:

  GET  /api/v1/keys/{slave_SAE_ID}/status
  GET  /api/v1/keys/{slave_SAE_ID}/enc_keys?number=N&size=B
  POST /api/v1/keys/{slave_SAE_ID}/enc_keys
  POST /api/v1/keys/{master_SAE_ID}/dec_keys

Mutual TLS is what the specification requires between a SAE and its KME; the
harness generates a throwaway CA and both certificates at start-up.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import ssl
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

DEFAULT_KEY_SIZE = 352          # bits; the specification's default
MAX_KEY_COUNT = 128


class KeyStore:
    """Key material a QKD link has already produced, indexed by key_ID.

    A real KME is fed by the quantum layer; here it is pre-filled and refilled
    at a configurable secret-key rate so the store can run dry exactly the way a
    real one does when demand outruns generation."""

    def __init__(self, rate_bps: float = 1.5e6, initial_bits: float = 4.0e6,
                 capacity_bits: float = 8.0e6):
        self.rate = rate_bps
        self.capacity = capacity_bits
        self.bits = min(initial_bits, capacity_bits)
        self.issued: dict[str, bytes] = {}
        self.lock = threading.Lock()
        self.last = time.monotonic()
        self.served = 0
        self.exhausted = 0

    def _refill(self):
        now = time.monotonic()
        self.bits = min(self.capacity, self.bits + (now - self.last) * self.rate)
        self.last = now

    def available_bits(self) -> float:
        with self.lock:
            self._refill()
            return self.bits

    def take(self, n: int, size_bits: int):
        with self.lock:
            self._refill()
            need = n * size_bits
            if self.bits < need:
                self.exhausted += 1
                return None
            self.bits -= need
            out = []
            for _ in range(n):
                kid = str(uuid.uuid4())
                material = secrets.token_bytes(max(1, size_bits // 8))
                self.issued[kid] = material
                out.append({"key_ID": kid,
                            "key": base64.b64encode(material).decode()})
            self.served += n
            return out

    def get_by_ids(self, ids):
        out = []
        with self.lock:
            for kid in ids:
                m = self.issued.get(kid)
                if m is None:
                    return None
                out.append({"key_ID": kid,
                            "key": base64.b64encode(m).decode()})
        return out


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    # Without this the server writes headers and body as separate small
    # segments, Nagle holds the second one, and the client's delayed ACK adds a
    # flat 40 ms to every request. That is a measurement artefact of the test
    # harness, not a cost of the specification, and it swamped the real number
    # by a factor of twenty before it was found.
    disable_nagle_algorithm = True
    store: KeyStore = None
    kme_id = "KME-QKD-01"
    extra_delay_s = 0.0

    def log_message(self, *a):
        pass                                     # keep stderr out of the timings

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        head = (f"{self.protocol_version} {code} OK\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(body)}\r\n\r\n").encode()
        # one write, so the response leaves in a single segment
        self.wfile.write(head + body)

    def _status(self, sae):
        b = self.store.available_bits()
        return {
            "source_KME_ID": self.kme_id,
            "target_KME_ID": "KME-QKD-02",
            "master_SAE_ID": "SAE-A",
            "slave_SAE_ID": sae,
            "key_size": DEFAULT_KEY_SIZE,
            "stored_key_count": int(b // DEFAULT_KEY_SIZE),
            "max_key_count": MAX_KEY_COUNT,
            "max_key_per_request": 64,
            "max_key_size": 1024,
            "min_key_size": 64,
            "max_SAE_ID_count": 0,
        }

    def do_GET(self):
        if self.extra_delay_s:
            time.sleep(self.extra_delay_s)
        u = urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        if len(parts) < 4 or parts[0] != "api" or parts[1] != "v1" or parts[2] != "keys":
            return self._send(404, {"message": "not found"})
        sae = parts[3]
        res = parts[4] if len(parts) > 4 else ""
        if res == "status":
            return self._send(200, self._status(sae))
        if res == "enc_keys":
            q = parse_qs(u.query)
            n = int(q.get("number", ["1"])[0])
            size = int(q.get("size", [str(DEFAULT_KEY_SIZE)])[0])
            keys = self.store.take(min(n, 64), size)
            if keys is None:
                return self._send(503, {"message": "insufficient key material"})
            return self._send(200, {"keys": keys})
        return self._send(404, {"message": "not found"})

    def do_POST(self):
        if self.extra_delay_s:
            time.sleep(self.extra_delay_s)
        ln = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(ln) or b"{}")
        except Exception:
            return self._send(400, {"message": "bad json"})
        u = urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        if len(parts) < 5:
            return self._send(404, {"message": "not found"})
        res = parts[4]
        if res == "enc_keys":
            n = int(body.get("number", 1))
            size = int(body.get("size", DEFAULT_KEY_SIZE))
            keys = self.store.take(min(n, 64), size)
            if keys is None:
                return self._send(503, {"message": "insufficient key material"})
            return self._send(200, {"keys": keys})
        if res == "dec_keys":
            ids = [k["key_ID"] for k in body.get("key_IDs", [])]
            keys = self.store.get_by_ids(ids)
            if keys is None:
                return self._send(400, {"message": "unknown key_ID"})
            return self._send(200, {"keys": keys})
        return self._send(404, {"message": "not found"})


def make_certs(dirpath):
    """Throwaway CA plus server and client certs, for the mutual TLS the spec wants."""
    os.makedirs(dirpath, exist_ok=True)
    ca_key = os.path.join(dirpath, "ca.key")
    ca_crt = os.path.join(dirpath, "ca.crt")
    s_key = os.path.join(dirpath, "server.key")
    s_crt = os.path.join(dirpath, "server.crt")
    c_key = os.path.join(dirpath, "client.key")
    c_crt = os.path.join(dirpath, "client.crt")
    if all(os.path.exists(p) for p in (ca_crt, s_crt, c_crt)):
        return s_crt, s_key, ca_crt, c_crt, c_key
    import subprocess
    def run(cmd):
        subprocess.run(cmd, shell=True, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run(f"openssl req -x509 -newkey rsa:2048 -nodes -keyout {ca_key} -out {ca_crt} "
        f"-days 2 -subj '/CN=QKD-Test-CA'")
    for key, crt, cn in ((s_key, s_crt, "localhost"), (c_key, c_crt, "SAE-A")):
        csr = crt + ".csr"
        run(f"openssl req -newkey rsa:2048 -nodes -keyout {key} -out {csr} -subj '/CN={cn}'")
        run(f"openssl x509 -req -in {csr} -CA {ca_crt} -CAkey {ca_key} "
            f"-CAcreateserial -out {crt} -days 2")
        os.unlink(csr)
    return s_crt, s_key, ca_crt, c_crt, c_key


def serve(host="127.0.0.1", port=8443, certdir="/tmp/qkd_certs",
          rate_bps=1.5e6, mutual_tls=True, extra_delay_s=0.0):
    s_crt, s_key, ca_crt, _, _ = make_certs(certdir)
    Handler.store = KeyStore(rate_bps=rate_bps)
    Handler.extra_delay_s = extra_delay_s
    httpd = ThreadingHTTPServer((host, port), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(s_crt, s_key)
    if mutual_tls:
        ctx.load_verify_locations(ca_crt)
        ctx.verify_mode = ssl.CERT_REQUIRED
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
    return httpd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8443)
    ap.add_argument("--rate-bps", type=float, default=1.5e6)
    ap.add_argument("--no-mtls", action="store_true")
    ap.add_argument("--extra-delay-ms", type=float, default=0.0)
    a = ap.parse_args()
    httpd = serve(a.host, a.port, rate_bps=a.rate_bps, mutual_tls=not a.no_mtls,
                  extra_delay_s=a.extra_delay_ms / 1000.0)
    print(f"ETSI GS QKD 014 KME on https://{a.host}:{a.port} "
          f"(mTLS={'off' if a.no_mtls else 'on'}, rate={a.rate_bps/1e6:.2f} Mbit/s)",
          flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
