# Draft issue for relab/hotstuff (not yet posted)

**Title:** Latency emulation serializes delays per sender, because `addNetworkDelay` sleeps while the gorums stream is held

**Summary.** In `server/server.go` the `Propose`, `Vote`, `NewView` and `Timeout` handlers call
`impl.srv.addNetworkDelay(id)`, which sleeps for the emulated latency *before* the handler returns. Gorums holds the
per-sender stream while a handler runs, so the sleeps for successive messages from one sender add up instead of
overlapping. A message queued behind another from the same sender therefore arrives after the sum of both delays,
not after its own.

**Observed effect** (commit 3179c6e6, `locations` latency matrix, round-robin, n = 8–64): votes miss their deadline,
and they are concentrated on the replica that proposed in the previous view. In 20 runs, 555 of 663 missing votes
came from that role. The latency matrix rules out a genuine race: the distant proposal is due after 136 ms, and the
next cannot be issued before 152 ms, yet it is logged first.

**Fix.** Release the stream before sleeping. We added `ctx.Release()` immediately before `addNetworkDelay(id)` in the
four handlers (4 lines). With the fix, delays apply per message, vote participation is ≥ 0.9989 in every run, and
the loss is no longer concentrated on any role.

```diff
+	ctx.Release()
 	impl.srv.addNetworkDelay(id)
```

(The full diff is in `research/realworld/e3/emulation_fix.diff`.)
