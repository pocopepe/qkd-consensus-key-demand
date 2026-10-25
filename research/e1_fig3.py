#!/usr/bin/env python3
"""Figure 3: per-view communication graphs, ideal model vs real implementations."""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research.e1_analyze import D_CORE, build_views

FIG = "research/results/e1/figures"


def graph_svg(n, edges, title, sub, hubs=()):
    R, cx, cy = 52, 78, 88
    pos = {i: (cx + R * math.cos(2 * math.pi * i / n - math.pi / 2),
               cy + R * math.sin(2 * math.pi * i / n - math.pi / 2))
           for i in range(n)}
    o = [f'<g>']
    o.append(f'<text class="gt" x="{cx}" y="16" text-anchor="middle">{title}</text>')
    o.append(f'<text class="gs" x="{cx}" y="30" text-anchor="middle">{sub}</text>')
    for (a, b) in sorted(edges):
        x1, y1 = pos[a]; x2, y2 = pos[b]
        o.append(f'<line class="ge" x1="{x1:.1f}" y1="{y1:.1f}" '
                 f'x2="{x2:.1f}" y2="{y2:.1f}"/>')
    for i in range(n):
        x, y = pos[i]
        cls = "gh" if i in hubs else "gn"
        o.append(f'<circle class="{cls}" cx="{x:.1f}" cy="{y:.1f}" r="5"/>')
    o.append('</g>')
    return "\n".join(o)


def main():
    os.makedirs(FIG, exist_ok=True)
    n = 4
    panels = []

    # ideal chained rotation (from the theoretical model): two hubs, one survives
    ideal = {(min(0, j), max(0, j)) for j in range(n) if j != 0} | \
            {(min(1, j), max(1, j)) for j in range(n) if j != 1}
    panels.append(("ideal chained rotation", "model: m=2, k=1", ideal, {0, 1}))

    for fn, label in (("research/results/e1/raw/hotstuff_stable_run1.json", "libhotstuff"),
                      ("research/results/e1/raw/comet_n4_run1.json", "CometBFT")):
        if not os.path.exists(fn):
            continue
        d = json.load(open(fn))
        recs = [tuple(r) for r in d["records"]]
        views = build_views(recs, D_CORE)
        mid = list(views.keys())[len(views) // 2]
        S = set(views[mid])
        deg = {}
        for (a, b) in S:
            deg[a] = deg.get(a, 0) + 1
            deg[b] = deg.get(b, 0) + 1
        mx = max(deg.values()) if deg else 0
        hubs = {v for v, dd in deg.items() if dd == mx}
        panels.append((label, f"measured: {len(S)} edges, view {mid}", S, hubs))

    W, H = 170 * len(panels), 180
    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" '
             f'xmlns="http://www.w3.org/2000/svg" class="viz">']
    parts.append('<style>'
      '.viz{--surface-1:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--edge:#8a8a86;'
      '--hub:#2a78d6;--node:#c9d3de;'
      'font-family:ui-sans-serif,system-ui,sans-serif}'
      '@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .viz{'
      '--surface-1:#1a1a19;--ink:#f5f5f2;--ink2:#c3c2b7;--edge:#5a5a56;'
      '--hub:#3987e5;--node:#3b4654;}}'
      ':root[data-theme="dark"] .viz{--surface-1:#1a1a19;--ink:#f5f5f2;'
      '--ink2:#c3c2b7;--edge:#5a5a56;--hub:#3987e5;--node:#3b4654;}'
      '.gt{fill:var(--ink);font-size:12px;font-weight:600}'
      '.gs{fill:var(--ink2);font-size:10px}'
      '.ge{stroke:var(--edge);stroke-width:1.4}'
      '.gn{fill:var(--node);stroke:var(--surface-1);stroke-width:1.5}'
      '.gh{fill:var(--hub);stroke:var(--surface-1);stroke-width:1.5}'
      '</style>')
    parts.append(f'<rect width="{W}" height="{H}" fill="var(--surface-1)"/>')
    for i, (t, s, e, h) in enumerate(panels):
        parts.append(f'<g transform="translate({170*i},0)">{graph_svg(n, e, t, s, h)}</g>')
    parts.append('</svg>')
    out = os.path.join(FIG, "fig3_view_graphs.svg")
    open(out, "w").write("\n".join(parts))
    print(f"wrote {out} ({len(panels)} panels)")
    for t, s, e, h in panels:
        print(f"  {t:<26} {s:<34} hubs={sorted(h)} edges={len(e)}")


if __name__ == "__main__":
    main()
