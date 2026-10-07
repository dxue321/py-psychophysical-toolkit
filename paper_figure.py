"""
Publication-ready figures for paired-comparison user studies
============================================================
Produces vector PDF (plus PNG preview) figures sized for two-column conference
templates such as CVPR / ICCV / ECCV:

  single column : 3.25 in (8.25 cm) wide  -> \\includegraphics[width=\\linewidth]{...}
  double column : 6.875 in (17.5 cm) wide -> figure* with \\includegraphics[width=\\textwidth]{...}

Figures are drawn at their final printed size, so the font size given with --font-size
(default 8 pt) is exactly the size that appears in the paper (CVPR captions are 9 pt).
Fonts are embedded as TrueType (pdf.fonttype 42), as required by most venues.

Output (in --out, default paper_figures/):
  fig_preference_rate.pdf   single column: how often each method was chosen (95% CI)
  fig_scale.pdf             single column: Thurstone Case V scale (95% bootstrap CI)
  fig_pairwise.pdf          single column: pairwise preference matrix with significance
  fig_ours_vs.pdf           single column: "ours vs. each baseline" stacked bars (needs --ours)
  fig_overview.pdf          double column: (a) preference rate, (b) scale, (c) pairwise matrix
  latex_snippets.tex        ready-to-paste LaTeX for every figure

Usage
-----
python paper_figure.py                                   # all participants in results/
python paper_figure.py --ours Ours --rename Blur="Gaussian blur" JPEG="JPEG (q=12)"
python paper_figure.py --order Ours JPEG Blur Noise --font sans --font-size 9
python paper_figure.py --results-dir data_sim --out paper_figures_sim --ours Ours
"""
import argparse
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from scipy.stats import binomtest

import analysis as A

COLUMN_W = 3.25        # inches, CVPR single column
TEXT_W = 6.875         # inches, CVPR full text width

# Colorblind-safe palette: one accent hue for "ours", neutral gray for the rest,
# orange-gray-blue diverging map for preference proportions (0.5 = neutral)
ACCENT = "#2a78d6"
ACCENT_LIGHT = "#9ec5f4"
BASE = "#a9a8a2"
BASE_DARK = "#6f6e69"
INK = "#1a1a1a"
INK2 = "#4a4945"
GRID = "#e4e3dd"
DIVERGING = LinearSegmentedColormap.from_list("pref", ["#eb6834", "#f0efec", ACCENT])

SERIF = ["Times New Roman", "Times", "Nimbus Roman", "TeX Gyre Termes", "Liberation Serif",
         "STIXGeneral", "DejaVu Serif"]
SANS = ["Arial", "Helvetica", "Liberation Sans", "TeX Gyre Heros", "DejaVu Sans"]
CJK_FALLBACK = ["Microsoft YaHei", "Noto Sans CJK SC", "PingFang SC", "SimHei", "WenQuanYi Micro Hei"]


def set_style(font="serif", size=8.0):
    serif = font == "serif"
    plt.rcParams.update({
        "font.family": "serif" if serif else "sans-serif",
        "font.serif": SERIF + CJK_FALLBACK,
        "font.sans-serif": SANS + CJK_FALLBACK,
        "mathtext.fontset": "stix" if serif else "dejavusans",
        "font.size": size,
        "axes.titlesize": size,
        "axes.labelsize": size,
        "xtick.labelsize": size,
        "ytick.labelsize": size,
        "legend.fontsize": size,
        "axes.titleweight": "normal",
        "axes.linewidth": 0.6,
        "axes.edgecolor": INK2,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": INK2, "ytick.color": INK2,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "xtick.major.size": 2.5, "ytick.major.size": 0,
        "xtick.major.pad": 2, "ytick.major.pad": 3,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.unicode_minus": True,
        "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
        "pdf.fonttype": 42, "ps.fonttype": 42,     # embed TrueType fonts
        "savefig.dpi": 300,
        "legend.frameon": False,
        "legend.handlelength": 1.0, "legend.handletextpad": 0.4, "legend.columnspacing": 1.0,
    })


def new_fig(width, height):
    fig = plt.figure(figsize=(width, height), layout="constrained")
    fig.get_layout_engine().set(w_pad=0.02, h_pad=0.02, wspace=0.04, hspace=0.04)
    return fig


def save(fig, out_dir, name, written):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(out_dir, f"{name}.{ext}"))  # no bbox cropping: keep exact width
    plt.close(fig)
    written.append(name)


def stars(p):
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""


# =========================================================================== panels
def colors_for(methods, ours):
    return [ACCENT if m == ours else BASE for m in methods] if ours else [ACCENT] * len(methods)


def panel_rate(ax, S, labels, ours, size):
    """Horizontal bars: choice rate with Wilson 95% CI, best method on top."""
    k = len(S)
    y = np.arange(k)[::-1]
    r = S["choice_rate"].to_numpy() * 100
    lo, hi = S["rate_ci_low"].to_numpy() * 100, S["rate_ci_high"].to_numpy() * 100
    ax.barh(y, r, height=0.62, color=colors_for(S["method"], ours), zorder=2)
    ax.errorbar(r, y, xerr=[r - lo, hi - r], fmt="none", ecolor=INK, elinewidth=0.7,
                capsize=1.8, capthick=0.7, zorder=3)
    ax.axvline(50, color=INK2, lw=0.6, ls=(0, (3, 2)), zorder=1)
    for yi, (rv, h) in enumerate(zip(r, hi)):
        ax.text(h + 2, y[yi], f"{rv:.1f}", va="center", ha="left", fontsize=size - 0.5, color=INK,
                zorder=4, bbox=dict(boxstyle="square,pad=0.08", fc="white", ec="none"))
    ax.set_yticks(y, labels)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Preference rate (%)")
    ax.set_ylim(-0.6, k - 0.4)
    ax.grid(axis="x", color=GRID, lw=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)


def panel_scale(ax, S, labels, ours, size):
    """Dots with 95% bootstrap CI on the Thurstone Case V scale."""
    k = len(S)
    y = np.arange(k)[::-1]
    s = S["thurstone"].to_numpy()
    lo, hi = S["thurstone_ci_low"].to_numpy(), S["thurstone_ci_high"].to_numpy()
    cols = colors_for(S["method"], ours)
    light = [ACCENT_LIGHT if c == ACCENT else "#cfcec8" for c in cols]
    ax.hlines(y, lo, hi, colors=light, lw=2.2, zorder=2)
    ax.scatter(s, y, s=size * 3.2, c=cols, edgecolors="white", linewidths=0.8, zorder=3)
    ax.set_yticks(y, labels)
    ax.set_ylim(-0.6, k - 0.4)
    span = max(hi.max(), 0.5)
    ax.set_xlim(-0.06 * span, span * 1.06)
    ax.set_xlabel("Thurstone scale value (z units)")
    ax.grid(axis="x", color=GRID, lw=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)


def panel_matrix(fig, ax, items, W, N, S, pairwise, labels, size, colorbar=True):
    """Pairwise preference matrix: cell (row, col) = % of trials where row beat column."""
    order = S["method"].tolist()
    k = len(order)
    idx = [items.index(m) for m in order]
    with np.errstate(invalid="ignore", divide="ignore"):
        P = (W / N)[np.ix_(idx, idx)]
    im = ax.imshow(np.ma.masked_invalid(P), cmap=DIVERGING, vmin=0, vmax=1)
    sig = {}
    for _, row in pairwise.iterrows():
        sig[(row.method_a, row.method_b)] = sig[(row.method_b, row.method_a)] = row.p_holm
    fs = size - 0.5 if k <= 5 else size - 1 if k <= 7 else size - 1.5
    for i in range(k):
        for j in range(k):
            if i == j or np.isnan(P[i, j]):
                continue
            col = "white" if abs(P[i, j] - 0.5) > 0.3 else INK
            # Stars are marked on the winning cell only, as a small line under the number
            st = stars(sig.get((order[i], order[j]), 1.0)) if P[i, j] > 0.5 else ""
            ax.text(j, i - (0.13 if st else 0), f"{P[i, j] * 100:.0f}", ha="center", va="center",
                    fontsize=fs, color=col)
            if st:
                ax.text(j, i + 0.24, st, ha="center", va="center", fontsize=fs - 1, color=col)
    ax.set_xticks(range(k), labels, rotation=35 if max(map(len, labels)) > 4 else 0,
                  ha="right" if max(map(len, labels)) > 4 else "center", rotation_mode="anchor")
    ax.set_yticks(range(k), labels)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    if colorbar:
        cb = fig.colorbar(im, ax=ax, fraction=0.05, pad=0.03, aspect=18)
        cb.set_ticks([0, 0.5, 1], labels=["0", "50", "100"])
        cb.ax.tick_params(length=2, width=0.6, labelsize=size - 0.5)
        cb.outline.set_linewidth(0.5)
        cb.set_label("Row preferred (%)", fontsize=size - 0.5, labelpad=2)
    return im


def panel_ours_vs(ax, items, W, N, S, ours, labels_map, size):
    """'Ours vs. X' stacked 100% bars, the classic user-study plot."""
    baselines = [m for m in S["method"] if m != ours]
    o = items.index(ours)
    rows = []
    for m in baselines:
        j = items.index(m)
        n = int(N[o, j])
        if n == 0:
            continue
        rows.append((m, W[o, j] / n, n, binomtest(int(W[o, j]), n, 0.5).pvalue))
    if not rows:
        raise SystemExit(f"[ERROR] '{ours}' was never compared with another method")
    p_adj = A.holm([r[3] for r in rows])
    k = len(rows)
    y = np.arange(k)[::-1]
    win = np.array([r[1] for r in rows]) * 100
    ax.barh(y, win, height=0.6, color=ACCENT, label=labels_map.get(ours, ours), zorder=2)
    ax.barh(y, 100 - win, left=win, height=0.6, color=BASE, label="Baseline", zorder=2)
    ax.axvline(50, color="white", lw=0.8, ls=(0, (2, 1.5)), zorder=3)
    ax.set_xlim(0, 100)
    labels_drawn = []
    for yi, w, p in zip(y, win, p_adj):
        labels_drawn.append((ax.text(2, yi, f"{w:.1f}%", va="center", ha="left", color="white",
                                     fontsize=size - 0.5, zorder=4), w))
        labels_drawn.append((ax.text(98, yi, f"{100 - w:.1f}%", va="center", ha="right", color=INK,
                                     fontsize=size - 0.5, zorder=4), 100 - w))
        if stars(p):
            ax.text(101.5, yi, stars(p), va="center", ha="left", fontsize=size - 0.5, color=INK)
    ax.set_yticks(y, [f"vs. {labels_map.get(r[0], r[0])}" for r in rows])
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Preference (%)")
    ax.set_ylim(-0.6, k - 0.4)
    ax.spines["left"].set_visible(False)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, borderaxespad=0.2)
    ax.segment_labels = labels_drawn
    return k


def drop_labels_that_do_not_fit(fig, ax, margin=3.0):
    """Remove percentage labels wider than their bar segment (measured after layout)."""
    fig.canvas.draw()  # runs the layout engine so text and axes sizes are final
    renderer = fig.canvas.get_renderer()
    px_per_unit = ax.bbox.width / 100.0
    for txt, seg in getattr(ax, "segment_labels", []):
        width = txt.get_window_extent(renderer).width / px_per_unit
        if width + margin > seg:
            txt.remove()


# =========================================================================== main
def main():
    p = argparse.ArgumentParser(description="Publication-ready user-study figures (CVPR two-column sizes)")
    p.add_argument("files", nargs="*", help="Result CSV files (default: every CSV in --results-dir)")
    p.add_argument("--results-dir", default="results")
    p.add_argument("--out", default="paper_figures")
    p.add_argument("--ours", help="Name of your method (highlighted; enables fig_ours_vs). "
                                  "Default: a method folder named 'ours' if there is one")
    p.add_argument("--rename", nargs="*", default=[], metavar="FOLDER=LABEL",
                   help='Display names, e.g. Blur="Gaussian blur" JPEG="JPEG (q=12)"')
    p.add_argument("--order", nargs="*", help="Method order top to bottom (default: by scale value)")
    p.add_argument("--font", choices=["serif", "sans"], default="serif",
                   help="serif matches the Times body text of CVPR papers")
    p.add_argument("--font-size", type=float, default=8.0, help="Font size in pt at printed size")
    p.add_argument("--boot", type=int, default=2000, help="Bootstrap samples for the scale CI")
    p.add_argument("--boot-unit", choices=["trial", "scene", "subject"], default="trial")
    a = p.parse_args()

    set_style(a.font, a.font_size)
    fs = a.font_size
    df = A.load(a.files or [os.path.join(a.results_dir, "*.csv")])
    if a.boot_unit != "trial" and df[a.boot_unit].nunique() < 5:
        print(f"[NOTE] Fewer than 5 levels of '{a.boot_unit}'; using trial resampling")
        a.boot_unit = "trial"
    items, W, N, S, pairwise, _, _ = A.summarize(df, a.boot, a.boot_unit)

    if a.order:
        missing = [m for m in a.order if m not in items]
        if missing:
            raise SystemExit(f"[ERROR] --order names unknown methods: {missing}; available: {items}")
        S = S.set_index("method").loc[a.order + [m for m in S["method"] if m not in a.order]].reset_index()
    names = {k: v for k, v in (r.split("=", 1) for r in a.rename)}
    ours = a.ours or next((m for m in items if m.lower() == "ours"), None)
    if ours and ours not in items:
        raise SystemExit(f"[ERROR] --ours '{ours}' is not one of the methods: {items}")
    labels = [names.get(m, m) for m in S["method"]]
    k = len(S)
    os.makedirs(a.out, exist_ok=True)
    written = []

    # Height grows with the number of methods; 0.17 in per row is comfortable at 8 pt
    row_h = 0.17 * fs / 8
    h_bars = 0.55 + row_h * k

    fig = new_fig(COLUMN_W, h_bars)
    panel_rate(fig.add_subplot(), S, labels, ours, fs)
    save(fig, a.out, "fig_preference_rate", written)

    fig = new_fig(COLUMN_W, h_bars)
    panel_scale(fig.add_subplot(), S, labels, ours, fs)
    save(fig, a.out, "fig_scale", written)

    fig = new_fig(COLUMN_W, min(3.4, 1.0 + 0.36 * k * fs / 8))
    panel_matrix(fig, fig.add_subplot(), items, W, N, S, pairwise, labels, fs)
    save(fig, a.out, "fig_pairwise", written)

    if ours:
        n_base = k - 1
        fig = new_fig(COLUMN_W, 0.75 + row_h * 1.15 * n_base)
        ax = fig.add_subplot()
        panel_ours_vs(ax, items, W, N, S, ours, names, fs)
        drop_labels_that_do_not_fit(fig, ax)
        save(fig, a.out, "fig_ours_vs", written)

    # Double-column overview: (a) rate, (b) scale, (c) matrix
    h = max(2.05, 0.85 + row_h * k * 1.3)
    fig = new_fig(TEXT_W, h)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.0, 0.85, 1.15])
    ax1, ax2, ax3 = fig.add_subplot(gs[0]), fig.add_subplot(gs[1]), fig.add_subplot(gs[2])
    panel_rate(ax1, S, labels, ours, fs)
    panel_scale(ax2, S, labels, ours, fs)
    ax2.set_yticklabels([])
    panel_matrix(fig, ax3, items, W, N, S, pairwise, labels, fs)
    for ax, t in zip((ax1, ax2, ax3), ("(a) Preference rate", "(b) Perceptual scale", "(c) Pairwise preference")):
        ax.set_title(t, loc="center", pad=4)
    save(fig, a.out, "fig_overview", written)

    n_sub = df["subject"].nunique()
    n_cmp = int(N.sum() / 2)
    snippet = [
        "% ---- generated by paper_figure.py ----",
        f"% {n_sub} participants, {n_cmp} pairwise comparisons, methods: {', '.join(labels)}",
        "% Single-column figures",
    ]
    for name in written:
        if name == "fig_overview":
            continue
        snippet += [r"\begin{figure}[t]", r"  \centering",
                    rf"  \includegraphics[width=\linewidth]{{{name}.pdf}}",
                    rf"  \caption{{User study ({n_sub} participants, {n_cmp} pairwise comparisons). TODO}}",
                    rf"  \label{{{name.replace('_', ':', 1)}}}", r"\end{figure}", ""]
    snippet += ["% Double-column figure", r"\begin{figure*}[t]", r"  \centering",
                r"  \includegraphics[width=\textwidth]{fig_overview.pdf}",
                rf"  \caption{{User study with {n_sub} participants and {n_cmp} pairwise comparisons. "
                r"(a) Preference rate with 95\% Wilson confidence intervals. "
                r"(b) Thurstone Case~V scale values with 95\% bootstrap confidence intervals. "
                r"(c) Percentage of trials in which the row method was preferred over the column method; "
                r"$^{*}p<.05$, $^{**}p<.01$, $^{***}p<.001$ (two-sided binomial test, Holm-corrected).}",
                r"  \label{fig:user_study}", r"\end{figure*}"]
    with open(os.path.join(a.out, "latex_snippets.tex"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(snippet) + "\n")

    print(f"\nFont: {a.font}, {fs:g} pt at printed size; single column {COLUMN_W} in, double column {TEXT_W} in")
    print(f"Highlighted method: {ours or '(none; use --ours)'}")
    print(f"Written to {a.out}/: " + ", ".join(f"{n}.pdf" for n in written) + ", latex_snippets.tex (+ PNG previews)")


if __name__ == "__main__":
    main()
