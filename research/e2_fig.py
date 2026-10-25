#!/usr/bin/env python3
"""E2 figure: four consecutive views showing the hub pair rotating."""
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research.e1_analyze import D_CORE, build_views, min_vertex_cover

FIG = "research/results/e2_smoke/figures"


def panel(verts, edges, title, sub, hubs):
    n = len(verts)
    R, cx, cy = 48, 78, 92
    pos = {v: (cx + R * math.cos(2 * math.pi * i / n - math.pi / 2),
               cy + R * math.sin(2 * math.pi * i / n - math.pi / 2))
           for i, v in enumerate(verts)}
    o = ['<g>']
    o.append(f'<text class="gt" x="{cx}" y="16" text-anchor="middle">{title}</text>')
    o.append(f'<text class="gs" x="{cx}" y="30" text-anchor="middle">{sub}</text>')
    for (a, b) in sorted(edges):
        x1, y1 = pos[a]; x2, y2 = pos[b]
        o.append(f'<line class="ge" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
    for v in verts:
        x, y = pos[v]
        o.append(f'<circle class="{"gh" if v in hubs else "gn"}" cx="{x:.1f}" cy="{y:.1f}" r="6"/>')
        o.append(f'<text class="gl" x="{x:.1f}" y="{y+3.5:.1f}" text-anchor="middle">{v}</text>')
    o.append('</g>')
    return "\n".join(o)


def main():
    os.makedirs(FIG, exist_ok=True)
    d = json.load(open("research/results/e2_smoke/raw/smoke_run1.json"))
    n = d["n_validators"]
    recs = [tuple(r) for r in d["records"]]
    props = {int(k): v for k, v in d["proposers"].items()}
    views = build_views(recs, D_CORE)
    verts = sorted({v for dd in views.values() for e in dd for v in e})
    keys = sorted(views)[200:204]
    panels = []
    for vk in keys:
        S = set(views[vk])
        c = min_vertex_cover(n, S, verts)
        panels.append((f"view {vk[0]}",
                       f"L={props.get(vk[0],'?')}, L+1={props.get(vk[0]+1,'?')}  m={len(c)}",
                       S, set(c)))
    W, H = 165 * len(panels), 190
    p = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" class="viz">']
    p.append('<style>'
      '.viz{--surface-1:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--edge:#8a8a86;'
      '--hub:#2a78d6;--node:#c9d3de;--lbl:#0b0b0b;font-family:ui-sans-serif,system-ui,sans-serif}'
      '@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .viz{'
      '--surface-1:#1a1a19;--ink:#f5f5f2;--ink2:#c3c2b7;--edge:#5a5a56;'
      '--hub:#3987e5;--node:#3b4654;--lbl:#f5f5f2;}}'
      ':root[data-theme="dark"] .viz{--surface-1:#1a1a19;--ink:#f5f5f2;--ink2:#c3c2b7;'
      '--edge:#5a5a56;--hub:#3987e5;--node:#3b4654;--lbl:#f5f5f2;}'
      '.gt{fill:var(--ink);font-size:12px;font-weight:600}'
      '.gs{fill:var(--ink2);font-size:10px}'
      '.ge{stroke:var(--edge);stroke-width:1.5}'
      '.gn{fill:var(--node);stroke:var(--surface-1);stroke-width:1.5}'
      '.gh{fill:var(--hub);stroke:var(--surface-1);stroke-width:1.5}'
      '.gl{fill:var(--lbl);font-size:8px;font-weight:700}'
      '</style>')
    p.append(f'<rect width="{W}" height="{H}" fill="var(--surface-1)"/>')
    for i, (t, s, e, h) in enumerate(panels):
        p.append(f'<g transform="translate({165*i},0)">{panel(verts, e, t, s, h)}</g>')
    p.append(f'<text x="{W/2}" y="{H-8}" text-anchor="middle" class="gs">'
             f'Blue = minimum vertex cover (the hubs). One hub carries over each view: k=1 of m=2.</text>')
    p.append('</svg>')
    out = os.path.join(FIG, "fig_e2_view_graphs.svg")
    open(out, "w").write("\n".join(p))
    print(f"wrote {out}")
    for t, s, e, h in panels:
        print(f"  {t}: {s}  cover={sorted(h)}  edges={len(e)}")


if __name__ == "__main__":
    main()
