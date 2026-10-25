#!/usr/bin/env python3
"""Dependency-free SVG charts, theme-aware and directly labelled.

Colours come from the validated categorical order (blue, orange, aqua, violet),
which clears the CVD and normal-vision floors on the adjacent pairlist in both
modes. Aqua sits below 3:1 on the light surface, so every series carries a
direct label at its right end -- the relief the contrast warning requires, and
what keeps identity off colour alone.
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field

SERIES_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7"]
SERIES_DARK = ["#3987e5", "#d95926", "#199e70", "#9085e9"]


@dataclass
class Series:
    label: str
    xs: list
    ys: list
    dashed: bool = False


def _nice(lo, hi, n=5):
    if hi <= lo:
        hi = lo + 1.0
    span = hi - lo
    raw = span / n
    mag = 10 ** int(__import__("math").floor(__import__("math").log10(raw)))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            step = m * mag
            break
    else:
        step = 10 * mag
    start = step * __import__("math").floor(lo / step)
    ticks = []
    v = start
    while v <= hi + step * 0.5:
        ticks.append(round(v, 10))
        v += step
    return ticks


def line_chart(series, title, xlabel, ylabel, width=760, height=420,
               x_ticks=None, y_fmt="{:.2f}", x_fmt="{:g}", logy=False,
               subtitle=None):
    ml, mr, mt, mb = 64, 132, 54 if not subtitle else 70, 56
    pw, ph = width - ml - mr, height - mt - mb

    xs_all = [x for s in series for x in s.xs]
    ys_all = [y for s in series for y in s.ys]
    x0, x1 = min(xs_all), max(xs_all)
    y0, y1 = min(ys_all), max(ys_all)
    y0 = min(0.0, y0) if y0 >= 0 else y0
    if y1 == y0:
        y1 = y0 + 1.0
    yt = _nice(y0, y1)
    y0, y1 = yt[0], yt[-1]
    xt = x_ticks if x_ticks is not None else sorted(set(xs_all))

    def px(x): return ml + (x - x0) / (x1 - x0 or 1) * pw
    def py(y): return mt + ph - (y - y0) / (y1 - y0 or 1) * ph

    o = []
    a = o.append
    a(f'<svg viewBox="0 0 {width} {height}" width="100%" '
      f'xmlns="http://www.w3.org/2000/svg" role="img" '
      f'aria-label="{html.escape(title)}" class="viz">')
    a('<style>'
      '.viz{--surface-1:#fcfcfb;--text-primary:#0b0b0b;--text-secondary:#52514e;'
      '--muted:#8a8a86;--grid:#e4e4e1;'
      + "".join(f"--s{i+1}:{c};" for i, c in enumerate(SERIES_LIGHT))
      + 'font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}'
      '@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .viz{'
      '--surface-1:#1a1a19;--text-primary:#f5f5f2;--text-secondary:#c3c2b7;'
      '--muted:#8e8e88;--grid:#2e2e2c;'
      + "".join(f"--s{i+1}:{c};" for i, c in enumerate(SERIES_DARK)) + '}}'
      ':root[data-theme="dark"] .viz{'
      '--surface-1:#1a1a19;--text-primary:#f5f5f2;--text-secondary:#c3c2b7;'
      '--muted:#8e8e88;--grid:#2e2e2c;'
      + "".join(f"--s{i+1}:{c};" for i, c in enumerate(SERIES_DARK)) + '}'
      '.viz .ttl{fill:var(--text-primary);font-size:15px;font-weight:600}'
      '.viz .sub{fill:var(--text-secondary);font-size:12px}'
      '.viz .ax{fill:var(--text-secondary);font-size:11px;'
      'font-variant-numeric:tabular-nums}'
      '.viz .axname{fill:var(--muted);font-size:11px;letter-spacing:.04em}'
      '.viz .gl{stroke:var(--grid);stroke-width:1}'
      '.viz .dl{font-size:11.5px;font-weight:600;'
      'font-variant-numeric:tabular-nums}'
      '.viz .ln{fill:none;stroke-width:2;stroke-linejoin:round;'
      'stroke-linecap:round}'
      '.viz .mk{stroke:var(--surface-1);stroke-width:2}'
      '</style>')
    a(f'<rect x="0" y="0" width="{width}" height="{height}" fill="var(--surface-1)"/>')
    a(f'<text class="ttl" x="{ml}" y="24">{html.escape(title)}</text>')
    if subtitle:
        a(f'<text class="sub" x="{ml}" y="42">{html.escape(subtitle)}</text>')

    for v in yt:
        y = py(v)
        a(f'<line class="gl" x1="{ml}" y1="{y:.1f}" x2="{ml+pw}" y2="{y:.1f}"/>')
        a(f'<text class="ax" x="{ml-9}" y="{y+4:.1f}" text-anchor="end">'
          f'{y_fmt.format(v)}</text>')
    for v in xt:
        x = px(v)
        a(f'<text class="ax" x="{x:.1f}" y="{mt+ph+19:.1f}" text-anchor="middle">'
          f'{x_fmt.format(v)}</text>')
    a(f'<text class="axname" x="{ml+pw/2:.0f}" y="{height-10}" '
      f'text-anchor="middle">{html.escape(xlabel)}</text>')
    a(f'<text class="axname" transform="translate(16,{mt+ph/2:.0f}) rotate(-90)" '
      f'text-anchor="middle">{html.escape(ylabel)}</text>')

    for i, s in enumerate(series):
        c = f"var(--s{(i % 4) + 1})"
        d = " ".join(("M" if k == 0 else "L") + f"{px(x):.1f},{py(y):.1f}"
                     for k, (x, y) in enumerate(zip(s.xs, s.ys)))
        dash = ' stroke-dasharray="6 4"' if s.dashed else ""
        a(f'<path class="ln" d="{d}" stroke="{c}"{dash}/>')
        for x, y in zip(s.xs, s.ys):
            a(f'<circle class="mk" cx="{px(x):.1f}" cy="{py(y):.1f}" r="4.5" '
              f'fill="{c}"><title>{html.escape(s.label)}: '
              f'{x_fmt.format(x)}, {y_fmt.format(y)}</title></circle>')
        lx, ly = px(s.xs[-1]) + 10, py(s.ys[-1]) + 4
        a(f'<text class="dl" x="{lx:.1f}" y="{ly:.1f}" fill="{c}">'
          f'{html.escape(s.label)}</text>')

    a('</svg>')
    return "\n".join(o)


def write(path, svg):
    with open(path, "w") as f:
        f.write(svg)
    return path
