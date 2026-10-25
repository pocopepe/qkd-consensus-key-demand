#!/usr/bin/env python3
"""Assemble docs/report.html, inlining the generated SVG figures."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "results", "figures")


def svg(name):
    with open(os.path.join(FIG, name)) as f:
        return f.read().replace("<svg ", '<svg class="fig" ', 1)


HEAD = """<title>Pre-Arming the Ledger</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:ital,wght@0,400;0,600;0,800;1,400&family=Public+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;700&display=swap">
<style>
:root{
  --ground:#EEF1F5;--panel:#F8FAFC;--panel-2:#E3E8EF;
  --ink:#161B22;--ink-2:#41505F;--ink-3:#6B7B8C;
  --rule:#C9D3DE;--rule-soft:#DCE3EB;
  --signal:#A45B0C;--signal-bg:#F6E7D4;
  --verified:#1F6152;--verified-bg:#DCEDE7;
  --breach:#9A2F45;--breach-bg:#F5DEE3;
  --null:#5B5F73;--null-bg:#E4E4EC;
  --measure:68ch;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --ground:#10141A;--panel:#171C24;--panel-2:#1F2732;
  --ink:#E8EDF3;--ink-2:#AFBDCC;--ink-3:#7E8D9E;
  --rule:#2C3743;--rule-soft:#232C36;
  --signal:#E8A34A;--signal-bg:#3A2A12;
  --verified:#67C3AA;--verified-bg:#123029;
  --breach:#E8879C;--breach-bg:#3A1721;
  --null:#A5A9BE;--null-bg:#252734;
}}
:root[data-theme="dark"]{
  --ground:#10141A;--panel:#171C24;--panel-2:#1F2732;
  --ink:#E8EDF3;--ink-2:#AFBDCC;--ink-3:#7E8D9E;
  --rule:#2C3743;--rule-soft:#232C36;
  --signal:#E8A34A;--signal-bg:#3A2A12;
  --verified:#67C3AA;--verified-bg:#123029;
  --breach:#E8879C;--breach-bg:#3A1721;
  --null:#A5A9BE;--null-bg:#252734;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
  font-family:"Public Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:17px;line-height:1.65;-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding:0 28px 96px}
.mast{border-bottom:2px solid var(--ink);padding:56px 0 20px;margin-bottom:40px}
.kicker{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:11px;
  letter-spacing:.16em;text-transform:uppercase;color:var(--signal);margin-bottom:22px}
h1{font-family:Spectral,Georgia,serif;font-weight:800;
  font-size:clamp(2.6rem,6vw,4.1rem);line-height:1.02;letter-spacing:-.022em;
  margin:0 0 18px;text-wrap:balance}
.standfirst{font-family:Spectral,Georgia,serif;font-size:clamp(1.05rem,2.1vw,1.3rem);
  line-height:1.55;color:var(--ink-2);max-width:60ch;margin:0 0 26px}
.byline{display:flex;flex-wrap:wrap;gap:8px 22px;
  font-family:"JetBrains Mono",ui-monospace,monospace;font-size:11.5px;
  letter-spacing:.05em;color:var(--ink-3)}
.alert{background:var(--breach-bg);border-left:3px solid var(--breach);
  padding:22px 26px;margin:0 0 52px}
.alert h2{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:11px;
  letter-spacing:.15em;text-transform:uppercase;color:var(--breach);
  margin:0 0 12px;font-weight:700}
.alert p{margin:0 0 12px;max-width:var(--measure);font-size:16px}
.alert p:last-child{margin-bottom:0}
.alert cite{font-style:italic;color:var(--ink)}
section{margin:0 0 56px}
.fhead{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;
  padding-bottom:10px;border-bottom:1px solid var(--rule);margin-bottom:20px}
.fnum{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:12px;
  color:var(--ink-3);font-weight:700}
h2.ftitle{font-family:Spectral,Georgia,serif;font-weight:600;
  font-size:clamp(1.4rem,3vw,1.85rem);line-height:1.2;letter-spacing:-.012em;
  margin:0;flex:1 1 320px;text-wrap:balance}
.chip{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:10px;
  letter-spacing:.11em;text-transform:uppercase;padding:4px 9px;font-weight:700;
  white-space:nowrap}
.chip.new{background:var(--signal-bg);color:var(--signal)}
.chip.over{background:var(--breach-bg);color:var(--breach)}
.chip.conf{background:var(--verified-bg);color:var(--verified)}
.chip.null{background:var(--null-bg);color:var(--null)}
p{margin:0 0 16px;max-width:var(--measure)}
.lede{font-size:17.5px;color:var(--ink-2)}
strong{font-weight:700;color:var(--ink)}
code{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:.85em;
  background:var(--panel-2);padding:1px 5px}
.tscroll{overflow-x:auto;margin:0 0 20px;border:1px solid var(--rule-soft);
  background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:14.5px}
caption{caption-side:top;text-align:left;padding:12px 16px 10px;
  font-family:"JetBrains Mono",ui-monospace,monospace;font-size:10.5px;
  letter-spacing:.11em;text-transform:uppercase;color:var(--ink-3);
  border-bottom:1px solid var(--rule-soft)}
th,td{padding:9px 16px;text-align:right;font-variant-numeric:tabular-nums;
  white-space:nowrap}
th:first-child,td:first-child{text-align:left;font-variant-numeric:normal}
thead th{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:11px;
  font-weight:400;letter-spacing:.05em;color:var(--ink-3);
  border-bottom:1px solid var(--rule)}
tbody tr+tr td{border-top:1px solid var(--rule-soft)}
tbody td{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:13.5px}
tbody td:first-child{font-family:"Public Sans",sans-serif;font-size:14.5px;
  color:var(--ink-2)}
tr.win td{background:var(--signal-bg)}
tr.win td:first-child{color:var(--ink);font-weight:700}
tr.base td:first-child{color:var(--ink-3)}
.note{font-size:14px;color:var(--ink-3);max-width:var(--measure);margin:-6px 0 18px}
.pull{border-left:3px solid var(--signal);padding:6px 0 6px 22px;margin:26px 0;
  font-family:Spectral,Georgia,serif;font-size:1.22rem;line-height:1.45;
  color:var(--ink);max-width:56ch}
.stair{display:grid;grid-template-columns:auto repeat(4,1fr);gap:2px;
  background:var(--rule-soft);border:1px solid var(--rule-soft);margin:0 0 12px;
  font-family:"JetBrains Mono",ui-monospace,monospace;font-size:12.5px}
.stair>div{background:var(--panel);padding:9px 12px;text-align:right}
.stair .rh{text-align:left;color:var(--ink-3)}
.stair .hd{color:var(--ink-3);font-size:11px;letter-spacing:.05em}
.stair .hot{background:var(--breach-bg);color:var(--breach);font-weight:700}
.steps{list-style:none;padding:0;margin:0;display:grid;gap:1px;
  background:var(--rule-soft);border:1px solid var(--rule-soft)}
.steps li{background:var(--panel);padding:16px 20px;display:grid;gap:5px}
.steps b{font-family:"Public Sans",sans-serif;font-size:15.5px}
.steps span{font-size:14.5px;color:var(--ink-2)}
.fig{display:block;max-width:100%;height:auto}
figure{margin:0 0 24px;border:1px solid var(--rule-soft);background:var(--panel);
  overflow-x:auto}
figcaption{font-size:13.5px;color:var(--ink-3);padding:10px 16px;
  border-top:1px solid var(--rule-soft)}
.neg{color:var(--breach);font-weight:700}
.kv{display:grid;grid-template-columns:auto 1fr;gap:6px 18px;margin:0 0 18px;
  font-family:"JetBrains Mono",ui-monospace,monospace;font-size:13.5px}
.kv dt{color:var(--ink-3)}
.kv dd{margin:0;color:var(--ink);font-variant-numeric:tabular-nums}
footer{border-top:1px solid var(--rule);padding-top:22px;margin-top:12px;
  font-family:"JetBrains Mono",ui-monospace,monospace;font-size:11.5px;
  color:var(--ink-3)}
@media (max-width:640px){body{font-size:16px}.wrap{padding:0 18px 64px}
  .stair{font-size:11px}.stair>div{padding:7px 6px}}
</style>"""


def build():
    parts = [HEAD, '<div class="wrap">', """
<header class="mast">
  <div class="kicker">Research note &middot; QKD key supply for BFT consensus</div>
  <h1>Pre-Arming the Ledger</h1>
  <p class="standfirst">Twelve results from building out the predictive eBPF key-supply design, now with a working kernel enforcer and 21,900 simulated rounds behind it. The forecaster works far better than proposed &mdash; and for a reason that changes the optimisation, the kernel model, and the threat model along with it.</p>
  <div class="byline">
    <span>V. Sanjai &middot; 23BEC1306</span>
    <span>Guide: Prof. Dhanalakshmi R</span>
    <span>Linux 6.8 &middot; n=16 validators &middot; 21,900 rounds</span>
  </div>
</header>

<div class="alert">
  <h2>Read this before submitting</h2>
  <p>EWMA-driven predictive key pre-positioning for QKD networks is <strong>already published</strong>. Stan, Verchere, Vegas Olmos, Tafur Monroy and Rommel, <cite>&ldquo;Dynamic-threshold-based pre-relaying for enhanced key allocation in quantum-secured networks,&rdquo;</cite> JOCN 17(3), March 2025, updates key-pool thresholds by EWMA of next-step demand and pre-relays into virtual key pools ahead of requests. That is Eq. (1) plus the pre-arming idea. Separately, US 11,652,620 B2 (evolutionQ, priority 2021) claims proactive buffering of QKD key material with forecast-driven relay routing.</p>
  <p>Neither is cited, and the JOCN paper is the first hit on the obvious search. The prediction half is taken; the <strong>enforcement half is wide open</strong> &mdash; nothing was found on eBPF or XDP applied to QKD key management at all.</p>
</div>
"""]

    parts.append("""
<section>
  <div class="fhead"><span class="fnum">01</span>
    <h2 class="ftitle">Consensus demand is protocol-determined, not statistical</h2>
    <span class="chip new">New result</span></div>
  <p class="lede">Which validator pairs need key next view is a function of the leader schedule. Under rotation the hot set moves every view <em>by construction</em>, so a smoother puts its mass on the pairs that were hot last view &mdash; exactly the ones now cold.</p>
  <div class="tscroll"><table>
    <caption>Coverage of next view's demand by the top-48 predicted pairs</caption>
    <thead><tr><th>Forecaster</th><th>Round-robin</th><th>+2 Byzantine</th><th>VRF, lookahead 4</th></tr></thead>
    <tbody>
      <tr class="base"><td>EWMA, alpha tuned</td><td>0.593</td><td>0.521</td><td>0.694</td></tr>
      <tr class="base"><td>Holt, level + trend</td><td>0.626</td><td>0.554</td><td>0.686</td></tr>
      <tr class="win"><td>Structural</td><td>0.993</td><td>0.920</td><td>0.993</td></tr>
      <tr><td>Structural, schedule ablated</td><td>0.400</td><td>0.397</td><td>0.400</td></tr>
    </tbody></table></div>
  <p class="note">The ablation is the control. Strip the leader schedule out and it drops below both baselines &mdash; the gain is the protocol model, not the estimator.</p>
</section>

<section>
  <div class="fhead"><span class="fnum">02</span>
    <h2 class="ftitle">Latency is a quorum order statistic, so the objective is not additive</h2>
    <span class="chip over">Overturns Eq. (3)</span></div>
  <p class="lede">A view completes when 2f+1 participants complete, not when all n do. Covering 90% of a star buys nothing if the uncovered pairs push the q-th order statistic onto the slow path.</p>
  <p>And <strong>any</strong> quorum will do, so the control plane may pick which one. Accelerating the topologically cheapest 2f pairs hands back a third of the map entries at no latency cost.</p>
  <div class="tscroll"><table>
    <caption>End to end &middot; M_max = 192 entries &middot; U_max = 24 updates per view</caption>
    <thead><tr><th>Policy</th><th>Hit rate</th><th>p50 latency</th><th>Map churn</th></tr></thead>
    <tbody>
      <tr class="base"><td>Reactive, no pre-arming</td><td>&mdash;</td><td>7.50 ms</td><td>0.0</td></tr>
      <tr class="base"><td>Density-greedy, as proposed</td><td>0.172</td><td>6.00 ms</td><td>24.0</td></tr>
      <tr><td>Hysteretic swap</td><td>0.430</td><td>4.50 ms</td><td>24.0</td></tr>
      <tr class="win"><td>Quorum coverage</td><td>0.529</td><td>0.050 ms</td><td>22.7</td></tr>
    </tbody></table></div>
</section>

<section>
  <div class="fhead"><span class="fnum">03</span>
    <h2 class="ftitle">The binding kernel constraint is update bandwidth, not instructions</h2>
    <span class="chip over">Overturns Eq. (4)</span></div>
  <p class="lede">The constraint <code>&Sigma; c_v &le; I_max</code> has no referent in the verifier, which bounds the program statically at load time.</p>
  <p>An XDP fast path doing one hash lookup costs the same instructions whether the map holds one entry or a million. Measured across a 16,384&times; range: <strong>244 instructions, unchanged</strong>.</p>
  <div class="pull">What binds is the number of <code>bpf_map_update_elem</code> calls needed to <em>change</em> the set each view. A pair that stays pre-armed is free &mdash; which makes this round's decision depend on last round's.</div>
  <p>That turns a sequence of independent knapsacks into an <strong>online knapsack with switching costs</strong>. The design rule is that the update budget must cover 2f+1 pairs, not n&sup2;.</p>
</section>

<section>
  <div class="fhead"><span class="fnum">04</span>
    <h2 class="ftitle">The two-dimensional knapsack is not where the theory is</h2>
    <span class="chip null">Negative result</span></div>
  <p class="lede">The proposal names the greedy-versus-optimal gap as its core theoretical result. It is not there.</p>
  <div class="tscroll"><table>
    <caption>Density-greedy as a fraction of the exact optimum, 120 rounds</caption>
    <thead><tr><th>Map capacity</th><th>16</th><th>32</th><th>64</th><th>128</th><th>192</th><th>256</th></tr></thead>
    <tbody><tr><td>greedy / optimum</td><td>1.00000</td><td>1.00000</td><td>0.99986</td><td>0.99991</td><td>0.99996</td><td>1.00000</td></tr></tbody>
  </table></div>
  <p>Theorem 5 explains why: <code>G &ge; (1 &minus; w_max/C)&middot;OPT</code>, and relay-hop weights are two or three against a map of hundreds, so the instance is nearly fractional. Verified with 0 violations over 4,000 random instances.</p>
</section>

<section>
  <div class="fhead"><span class="fnum">05</span>
    <h2 class="ftitle">Reserved key is not free</h2>
    <span class="chip new">New result</span></div>
  <p class="lede">An h-hop reservation locks h times its size for the whole lease. A benefit-only objective has no way to decline a confident-but-wrong pre-arm.</p>
  <div class="tscroll"><table>
    <caption>Hoarding penalty &gamma; per bit-hop held and unused, in units of &lambda;</caption>
    <thead><tr><th>&gamma; / &lambda;</th><th>0.0</th><th>0.1</th><th>0.5</th><th>1.0</th><th>2.0</th><th>5.0</th></tr></thead>
    <tbody>
      <tr><td>Hit rate</td><td>0.374</td><td>0.536</td><td>0.592</td><td>0.588</td><td>0.530</td><td>0.271</td></tr>
      <tr><td>p50 (ms)</td><td>6.00</td><td>0.050</td><td>0.050</td><td>0.050</td><td>0.050</td><td>7.50</td></tr>
      <tr><td>Map entries</td><td>57.9</td><td>35.2</td><td>29.9</td><td>29.1</td><td>25.9</td><td>12.9</td></tr>
    </tbody></table></div>
  <p>Around &gamma; &asymp; &lambda; the risk-sensitive objective dominates on every axis at once. Declining bad pre-arms is what frees the budget for good ones.</p>
</section>

<section>
  <div class="fhead"><span class="fnum">06</span>
    <h2 class="ftitle">Pre-arming leaks the leader schedule, one view per view of lead time</h2>
    <span class="chip new">New attack</span></div>
  <p class="lede">A pre-armed pair is served in 14 &micro;s, a miss in milliseconds. That gap is the whole point of the optimisation and it is trivially observable.</p>
  <div class="tscroll"><table>
    <caption>Leader inference from response timing &middot; baseline top-1 = 0.062</caption>
    <thead><tr><th>Configuration</th><th>top-1</th><th>top-2</th><th>MI (bits)</th></tr></thead>
    <tbody>
      <tr class="base"><td>EWMA + greedy</td><td>0.071</td><td>0.142</td><td>0.306</td></tr>
      <tr><td>Structural + greedy</td><td>0.508</td><td>0.921</td><td>1.552</td></tr>
      <tr class="win"><td>Structural + quorum</td><td>0.534</td><td>0.984</td><td>1.703</td></tr>
    </tbody></table></div>
  <p>Consensus traffic already names the current leader. The new part is <em>advance</em> warning &mdash; and the leak horizon tracks the forecast horizon exactly:</p>
  <div class="stair">
    <div class="rh hd">horizon</div><div class="hd">leak@1</div><div class="hd">leak@2</div><div class="hd">leak@3</div><div class="hd">leak@4</div>
    <div class="rh">H = 1</div><div class="hot">0.197</div><div>0.050</div><div>0.058</div><div>0.087</div>
    <div class="rh">H = 2</div><div class="hot">0.182</div><div class="hot">0.184</div><div>0.050</div><div>0.055</div>
    <div class="rh">H = 3</div><div class="hot">0.239</div><div class="hot">0.203</div><div class="hot">0.192</div><div>0.066</div>
    <div class="rh">H = 4</div><div class="hot">0.224</div><div class="hot">0.216</div><div class="hot">0.176</div><div class="hot">0.205</div>
  </div>
  <p class="note">Baseline 0.062. For offsets of two or more there is no traffic that could have carried that information.</p>
  <div class="pull">Lead time is the quantity the predictive design is trying to maximise. It is also, view for view, the quantity being handed to the adversary.</div>
  <p><strong>Decoy pre-arming does not defend against this.</strong> The observable is generated by <em>real</em> traffic &mdash; a pair nobody sends to is never timed &mdash; so padding the map buys entries and held key and exactly zero privacy.</p>
</section>
""")

    parts.append(f"""
<section>
  <div class="fhead"><span class="fnum">07</span>
    <h2 class="ftitle">The blindspot has a closed form, and its ceiling is one half</h2>
    <span class="chip conf">Proved</span></div>
  <p class="lede">The EWMA's failure under leader rotation is not noise. It has an exact steady state, and a hard ceiling that explains the measured 0.520 to within four hundredths.</p>
  <p>For a period-n impulse train the smoother settles to <code>&acirc;(&phi;) = &alpha;B&middot;q^(&phi;&minus;1)/(1&minus;q^n)</code>, giving <code>Cov = (B&sup2;/n)[&alpha;&middot;q^(n&minus;1)/(1&minus;q^n) &minus; 1/n]</code>. That is <strong>negative for every &alpha; once n &ge; 2</strong>: the predictor's peak lands one view after the impulse, and the next impulse is n&minus;1 views away.</p>
  <p>On real star-structured demand the sharp statement is better. Define <em>support persistence</em> as the share of a view's demand carried by pairs already hot last view. Then EWMA coverage &le; persistence, <strong>with equality for all &alpha; &ge; &frac12;</strong>:</p>
  <div class="tscroll"><table>
    <caption>Coverage at the two-star budget, verified to 1e-9</caption>
    <thead><tr><th>n</th><th>persistence &pi;</th><th>&alpha;=0.1</th><th>&alpha;=0.3</th><th>&alpha;=0.5</th><th>&alpha;=0.9</th><th>structural</th></tr></thead>
    <tbody>
      <tr><td>8</td><td>0.6429</td><td>0.3571</td><td>0.4286</td><td>0.6429</td><td>0.6429</td><td>1.0000</td></tr>
      <tr class="win"><td>16</td><td>0.5667</td><td>0.1667</td><td>0.2333</td><td>0.5667</td><td>0.5667</td><td>1.0000</td></tr>
      <tr><td>32</td><td>0.5323</td><td>0.0968</td><td>0.1290</td><td>0.5323</td><td>0.5323</td><td>1.0000</td></tr>
    </tbody></table></div>
  <div class="pull">In chained HotStuff the vote star of view t&minus;1 <em>is</em> the proposal star of view t. Exactly one of the two stars carries over. A smoother gets that one free and cannot reach the other at any &alpha;.</div>
  <p>And no tuning escapes: burst tracking error falls monotonically in &alpha; while rotation covariance also falls monotonically in &alpha;. <strong>The burst-optimal &alpha; is the rotation-worst &alpha;.</strong></p>
</section>

<section>
  <div class="fhead"><span class="fnum">08</span>
    <h2 class="ftitle">The enforcer is real, and these numbers are from the kernel</h2>
    <span class="chip conf">Measured</span></div>
  <p class="lede">Sliding-window leases, per-validator token buckets, amortised garbage collection with a verifier-bounded loop. It loads on Linux 6.8 and answers packets.</p>
  <dl class="kv">
    <dt>verified instructions</dt><dd>2,851 &nbsp;<span style="color:var(--ink-3)">(0.29% of the ceiling, invariant in map size)</span></dd>
    <dt>in-kernel service time</dt><dd>548 ns per hit &nbsp;<span style="color:var(--ink-3)">(program's own counters)</span></dd>
    <dt>end-to-end fast path</dt><dd>14.2 &micro;s p50, 20.9 &micro;s p99, over 3,000 requests</dd>
    <dt>commit cost</dt><dd>2.98 &micro;s/entry serial, 1.16 &micro;s/entry batched</dd>
    <dt>U_max at a 250 ms view</dt><dd>~800 entries serial, ~2,000 batched, at 1% of the view</dd>
  </dl>
  <p>The lease mechanism validates cleanly: 40 pairs armed and left silent were all 40 reclaimed once packets flowed, handing back <strong>80 starvation credits</strong> &mdash; two per pair &mdash; so the daemon re-prioritises what it mis-forecast instead of skipping it again. Under live traffic, 3,100 hits produced 3,100 renewals and zero mid-round evictions.</p>
  <p>One property documented rather than hidden: the sweep is amortised over packets, so a fully idle interface never reclaims. The daemon's TTL is the backstop.</p>
</section>

<section>
  <div class="fhead"><span class="fnum">09</span>
    <h2 class="ftitle">Pre-arming makes starvation worse &mdash; and the obvious fix fails</h2>
    <span class="chip over">Reverses expectation</span></div>
  <p class="lede">The expected result was that pre-positioning key reduces starvation. Across 21,900 rounds it does the opposite, by up to 33% relative.</p>
  <figure>{svg('b_hoarding.svg')}
    <figcaption>A reservation holds key on every hop for the whole lease. During a flash crowd that is exactly the key the burst needs and cannot have.</figcaption>
  </figure>
  <p><strong>Charging a hoarding penalty does nothing</strong> &mdash; identical starvation to three decimals. It changes <em>which</em> pairs are chosen, and under a quorum objective the block value dominates the per-pair term.</p>
  <p><strong>Halving the lease fixes it completely.</strong> One view instead of two returns starvation to the reactive baseline (0.2408 against 0.2409) while keeping the fast path. The cost of holding key is a <em>duration</em> problem, not a selection problem &mdash; which is why the enforcer's lease is a short window the data plane renews on actual use.</p>
</section>

<section>
  <div class="fhead"><span class="fnum">10</span>
    <h2 class="ftitle">Hit rate is a misleading metric, and greedy hides behind it</h2>
    <span class="chip new">New result</span></div>
  <p class="lede">Round latency is a quorum order statistic, so a pre-armed pair that does not complete a block changes nothing at all.</p>
  <figure>{svg('c_drift_latency.svg')}
    <figcaption>The cliff between M=96 and M=64 is the quorum threshold. Below it no policy can complete a block.</figcaption>
  </figure>
  <figure>{svg('c_drift_armed.svg')}
    <figcaption>Entries held are key withheld. Density-greedy holds the most and gains the least.</figcaption>
  </figure>
  <p>At M=192 density-greedy holds <strong>60 entries and delivers nothing</strong> &mdash; p50 stays at the reactive 6.00 ms while a third of individual requests hit. The quorum rule holds half as many entries and reaches 0.01 ms. Scored on the corrected objective, greedy goes <span class="neg">negative</span> below the threshold: it destroys value by holding key that buys no latency.</p>
</section>

<section>
  <div class="fhead"><span class="fnum">11</span>
    <h2 class="ftitle">A metaheuristic lost to a rule derived from the protocol</h2>
    <span class="chip null">Negative result</span></div>
  <p class="lede">The hybrid optimiser &mdash; fractional seed plus randomised add/drop/swap repair &mdash; closes 24&ndash;28% of the residual gap over density-greedy on the offline objective. In the live system it still loses.</p>
  <figure>{svg('d_compute.svg')}
    <figcaption>Twenty-five times the search budget bought nothing. The fixed rule reaches 0.014 ms for less compute than the optimiser spends failing to.</figcaption>
  </figure>
  <p>The quorum rule encodes three things the random search must rediscover every view: cover blocks whole, take the topologically cheapest quorum, keep a liveness margin past the threshold. Those are consequences of the protocol, not of the instance &mdash; <strong>paying to search for them each round is paying for something already known.</strong></p>
</section>

<section>
  <div class="fhead"><span class="fnum">12</span>
    <h2 class="ftitle">Four hypotheses that were wrong</h2>
    <span class="chip conf">Corrections</span></div>
  <p class="lede">Each correction changed the design, and in every case the corrected version is the more interesting claim.</p>
  <div class="tscroll"><table>
    <caption>What I expected, what the data said, what changed</caption>
    <thead><tr><th>Hypothesis</th><th>What the data said</th><th>Consequence</th></tr></thead>
    <tbody>
      <tr><td>EWMA is anti-correlated with real star demand</td><td>Positive for large &alpha;; correlation is the wrong statistic</td><td>The ceiling is support persistence, = &frac12;</td></tr>
      <tr><td>Faster smoothing overshoots more on bursts</td><td>Burst error falls monotonically in &alpha;</td><td>Burst-optimal &alpha; is rotation-worst &alpha;</td></tr>
      <tr><td>A hoarding penalty fixes the starvation regression</td><td>Identical to three decimals</td><td>Holding is a duration problem: shorten the lease</td></tr>
      <tr><td>Quorum blocks can be scored independently</td><td>The optimiser over-armed, hedging an uncoverable event</td><td>Scenario correlation + explicit hold cost</td></tr>
    </tbody></table></div>
</section>

<section>
  <div class="fhead"><span class="fnum">13</span>
    <h2 class="ftitle">What is missing before this is submittable</h2>
    <span class="chip conf">Plan</span></div>
  <ul class="steps">
    <li><b>The slow-path constant is still a parameter</b><span>14.2 &micro;s fast path is measured; the 3 ms it is compared against is a literature figure for an ETSI GS QKD 014 round trip, not a measurement against a real key management entity.</span></li>
    <li><b>A second consensus protocol</b><span>One protocol makes the structural forecaster look like a special case. PBFT's O(n&sup3;) view change, or a DAG protocol like Narwhal, would show the method transfers.</span></li>
    <li><b>A competitive-ratio result for the switching-cost formulation</b><span>Or an honest statement that the paper is empirical. The algorithms literature treats online knapsack with switching costs as understudied.</span></li>
    <li><b>An adaptive adversary</b><span>The current attacker passively observes. One that reacts to the pre-arm set, plus a queueing-noise model, would establish how much the attack tolerates.</span></li>
    <li><b>A venue decision</b><span>Side channel as headline gives a security paper with a QKD setting. Quorum coverage and the enforcement plane as headline gives a networking paper with a security section. Being both in one is the failure mode.</span></li>
  </ul>
</section>

<footer>
  <p>Kernel figures measured on Linux 6.8.0-138 with the XDP enforcer loaded; consensus and QKD layers simulated. Chained HotStuff, n = 16, decoy-BB84 link rates, 21,900 rounds over an event-driven substrate. All figures produced by the code in this repository; <code>research/verify_theory.py</code> checks 16/16 formal claims numerically.</p>
</footer>
""")
    parts.append("</div>")
    return "\n".join(parts)


if __name__ == "__main__":
    out = os.path.join(ROOT, "docs", "report.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(build())
    print(f"wrote {out} ({os.path.getsize(out)/1024:.1f} KB)")
