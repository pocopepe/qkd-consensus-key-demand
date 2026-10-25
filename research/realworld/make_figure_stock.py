#!/usr/bin/env python3
# Writes paper/figures/fig-stock.tex from the three result files in stock/.
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, "..", "..", "paper", "figures", "fig-stock.tex")

S = json.load(open(os.path.join(HERE, "stock", "STOCK_RESULTS.json")))
F = json.load(open(os.path.join(HERE, "stock", "FORECAST_RESULTS.json")))
Rt = json.load(open(os.path.join(HERE, "stock", "RETAIN_RESULTS.json")))["cells"]
C = {(c["delta"], c["rule"], c["param"]): c for c in S["cells"].values()}
SHOW = ((1, "spec!55!black"), (5, "spec"), (50, "spec!75"))


def late(c):
    return max(1 - c["fill"], 1e-5)


def series(delta, rule):
    cells = [c for (d, r, _), c in C.items() if d == delta and r == rule]
    cells.sort(key=lambda c: c["stock_per_pair"])
    return " ".join(f"({c['stock_per_pair']:.3f},{late(c):.6f})" for c in cells)


def build():
    out = [r"""\documentclass[border=0pt]{standalone}
\usepackage{mathptmx}
\usepackage{amsmath,amssymb}
\usepackage{pgfplots}\pgfplotsset{compat=1.17}
\input{identity}
\newlength\colw\setlength\colw{238pt}% just under the IEEE Access column width
\begin{document}
\begin{tikzpicture}
\begin{axis}[name=a,width=\colw,height=5.6cm,xmode=log,ymode=log,
  xmin=0.06,xmax=24,ymin=0.00003,ymax=1.3,
  xtick={0.1,0.3,1,3,10},xticklabels={0.1,0.3,1,3,10},
  ytick={1,0.1,0.01,0.001,0.0001},yticklabels={$1$,$10^{-1}$,$10^{-2}$,$10^{-3}$,$10^{-4}$},
  xlabel={(a) Standing key, tags per pair},ylabel={Share of tags served late},
  grid=major,grid style={gray!20},
  tick label style={font=\scriptsize},label style={font=\scriptsize},
  legend columns=2,legend style={font=\scriptsize,draw=none,fill=none,at={(0.5,-0.28)},anchor=north,
    /tikz/every even column/.append style={column sep=5pt}}]"""]
    for delta, col in SHOW:
        out.append(f"\\addplot[thick,{col},mark=*,mark size=1.1pt] coordinates {{{series(delta, 'uniform')}}};")
        out.append(f"\\addlegendentry{{uniform, $\\delta={delta}$}}")
        out.append(f"\\addplot[thick,{col},dashed,mark=o,mark size=1.1pt] coordinates {{{series(delta, 'stake')}}};")
        out.append(f"\\addlegendentry{{by stake, $\\delta={delta}$}}")
    f0 = F["cells"]["0"]
    f1 = F["cells"]["1"]
    out.append(f"\\addplot[only marks,ref!70!black,mark=square*,mark size=2pt] coordinates {{({f0['armed_per_pair']:.3f},{1 - f0['fill']:.4f})}};")
    out.append("\\addlegendentry{carry-forward, $\\delta=0$}")
    out.append(f"\\addplot[only marks,ref!70!black,thick,mark=square,mark size=2pt] coordinates {{({f1['armed_per_pair']:.3f},{1 - f1['fill']:.4f})}};")
    out.append("\\addlegendentry{carry-forward, $\\delta\\ge1$}")
    kept = " ".join(f"({Rt[str(d)]['standing_per_pair']:.3f},{1 - Rt[str(d)]['fill']:.4f})" for d, _ in SHOW)
    out.append(f"\\addplot[only marks,ref!70!black,thick,mark=o,mark size=2pt] coordinates {{{kept}}};")
    out.append("\\addlegendentry{follow and keep}")
    out.append(r"""\addplot[densely dotted,thick,domain=0.06:24] {0.01};
\node[anchor=south west,font=\scriptsize] at (axis cs:0.065,0.01) {$99\%$ on time};
\end{axis}
\begin{axis}[name=b,at={(a.below south west)},anchor=above north west,yshift=-1.45cm,width=\colw,height=4.2cm,xmode=log,
  xmin=0.8,xmax=62,ymin=0,ymax=18,xtick={1,2,5,10,20,50},xticklabels={1,2,5,10,20,50},
  xlabel={(b) Relay time $\delta$, views},ylabel={Depth, tags per pair},
  grid=major,grid style={gray!20},
  tick label style={font=\scriptsize},label style={font=\scriptsize},
  legend columns=3,legend style={font=\scriptsize,draw=none,fill=none,at={(0.5,-0.42)},anchor=north,
    /tikz/every even column/.append style={column sep=5pt}}]""")
    deltas = sorted({c["delta"] for c in S["cells"].values()})
    for target, style, label in ((0.99, "", "99\\%"), (0.999, "dashed,", "99.9\\%")):
        for rule, col, mark in (("uniform", "spec", "*"), ("stake", "spec!55", "o")):
            pts = " ".join(f"({d},{S['need'][f'{d}|{target}|{rule}']['stock_per_pair']:.2f})" for d in deltas)
            out.append(f"\\addplot[thick,{col},{style}mark={mark},mark size=1.3pt] coordinates {{{pts}}};")
            out.append(f"\\addlegendentry{{{'uniform' if rule == 'uniform' else 'by stake'}, {label}}}")
    rr = " ".join(f"({d},{S['need'][f'{d}|rr']})" for d in deltas)
    out.append(f"\\addplot[thick,ref,mark=square*,mark size=1.3pt] coordinates {{{rr}}};")
    out.append("\\addlegendentry{round-robin, all}")
    out.append(r"""\end{axis}
\end{tikzpicture}
\end{document}""")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    open(P, "w").write(build())
    print("wrote", os.path.relpath(P))
