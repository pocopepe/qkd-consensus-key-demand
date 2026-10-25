# Live demonstration

A wrapper around the implementation already in this repository. It runs the real
BPF objects through the real kernel verifier and reads the real frozen research
data. **Nothing here is simulated or fabricated.**

## What this demonstrates

Two things, and only two:

1. **The data-plane measurements behind two claims in the paper.** First, the
   pre-arm BPF program is loaded at six map capacities spanning a 16,384× range
   and the kernel reports the verified instruction count at each — it does not
   change, which is what refuted the project's original premise that the
   instruction budget was a resource to optimise against. Second, a private
   virtual network is built with a key-management stub behind it, the enforcer
   is attached, and 600 real key requests are issued twice: once with nothing
   pre-armed and once with every pair pre-armed. The latency of each is
   measured.
2. **A reproduction of the paper's central empirical table** from frozen data:
   the closed form is recomputed independently and compared against the archived
   measured persistence for each validator count.

## Prerequisites

- Linux with BPF support (developed and measured on kernel 6.8).
- `ip` (iproute2) and `bpftool`.
- Python 3 for the analysis mode.
- The compiled objects `bpf/prearm.bpf.o`, `bpf/prearm_ctl` and
  `src/enforcer_loader`, all committed to the repository.

## Required privileges

The **BPF mode needs root** — loading a BPF program is a privileged operation.
The **analysis mode needs no privileges at all**.

## Quick start

```
./demo/run.sh
```

Runs the analysis reproduction, then runs the BPF demonstration if root is
available without a password prompt; otherwise it prints the command to run.

## BPF demonstration

```
sudo ./demo/run.sh bpf
```

## Analysis reproduction

```
./demo/run.sh analysis
```

## Expected runtime

Measured on the development machine (kernel 6.8.0-138, 16 cores):

| | Runtime |
|---|---|
| Analysis reproduction | **0.10 s** |
| BPF demonstration | **7.3 s** |
| Both (default mode) | **7.5 s** |
| Full E2 research campaign | **approximately 35 minutes** — see below |

The full campaign figure is *not* a guess. The E2 report records the configured
consensus durations (25 s for n ≤ 7, 30 s at n = 10, 40 s at n = 16, 60 s at
n = 32), which over 5 repetitions × 2 leader modes gives 30 minutes of consensus
runtime; and the modification timestamps of the 50 archived raw traces span
35.0 minutes end to end. The two agree, the difference being build and parsing
overhead. **The demonstration is not a shortened version of that campaign** — it
does not run consensus at all.

## What the professor will see

*Analysis mode* prints the five validator counts, the structural parameters `m`
and `k` that were fixed before measurement, the closed-form value of π, the
archived measured value, and the residual — with a maximum of `4.22e-04`. It is
labelled as a reproduction from frozen data.

*BPF mode* prints a table of verified instruction counts across six map
capacities — all `244`, unchanged — and then the live latency comparison. With
nothing pre-armed every request traverses the key-management stub, at a p50 of
roughly `3100 us`. With every pair pre-armed every request is answered inside
the kernel, at a p50 of roughly `17 us` — a separation of about `190x`,
measured on the spot with real packets. The run ends with the enforcer's own
counters, including the in-kernel service cost per hit.

The exact numbers vary by a few percent between runs; they are measurements,
not replays.

## What this does NOT demonstrate

- It is **not** the 50-run statistical campaign. It runs no consensus
  implementation and produces no new measurement.
- It does **not** re-derive the frozen results; it reads them.
- The BPF steps demonstrate the enforcement layer, which the paper presents as
  context rather than as a contribution. The latency separation is a property of
  the fast path versus a key-management round trip; it is not evidence for the
  persistence result, and the key-management delay is a stub modelling an ETSI
  round trip rather than a production key store.
- XDP runs here in `skb` (generic) mode on a virtual link, not natively on a
  NIC.

## Safety

The demo writes only to `demo/output/`. It never writes to `research/results/`,
`research/freeze/`, the prediction locks, or any frozen artefact. BPF mode
installs an `EXIT`/`INT`/`TERM` trap that removes both virtual interfaces and the
network namespace, drops the firewall rule the testbed adds, kills the loader and
the stub, and unpins `/sys/fs/bpf/qkd`. This was verified by interrupting a run
during the network phase and confirming that no interface, namespace, firewall
rule, pin, program or process remained. The same cleanup also runs at *startup*,
so a run that was killed hard leaves nothing that would break the next one — this
was verified by planting a leftover interface and namespace and confirming the
next run cleared them and completed normally.
