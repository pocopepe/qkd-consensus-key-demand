#!/usr/bin/env python3
"""Slow-path stand-in for an ETSI GS QKD 014 key management entity."""
import argparse
import socket
import struct
import time

HDR = struct.Struct("<IIIIQII")   # src, dst, view, bits, t_send, seq, flags
FLAG_RESPONSE = 0x1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=7788)
    ap.add_argument("--delay-us", type=float, default=3000.0,
                    help="modelled KME round trip; 3 ms is the literature figure")
    a = ap.parse_args()

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((a.bind, a.port))
    print(f"kme_stub listening on {a.bind}:{a.port}, delay={a.delay_us:.0f} us",
          flush=True)

    delay = a.delay_us / 1e6
    served = 0
    while True:
        try:
            data, peer = s.recvfrom(2048)
        except KeyboardInterrupt:
            break
        if len(data) < HDR.size:
            continue
        src, dst, view, bits, t_send, seq, flags = HDR.unpack_from(data)
        if flags & FLAG_RESPONSE:
            continue
        if delay > 0:
            end = time.perf_counter() + delay
            while time.perf_counter() < end:
                pass
        out = HDR.pack(dst, src, view, bits, t_send, seq, flags | FLAG_RESPONSE)
        s.sendto(out, peer)
        served += 1
        if served % 500 == 0:
            print(f"  served {served}", flush=True)


if __name__ == "__main__":
    main()
