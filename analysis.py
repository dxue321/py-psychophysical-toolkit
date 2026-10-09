"""
Analysis and plotting for multi-method comparison data
========================================================
Reads the CSV files written by experiment.py (several subjects can be pooled) and
computes, per method:

  * how often each method was chosen / choice rate (Wilson 95% CI)
  * Thurstone Case V scale values (bootstrap 95% CI; resampling by trial / scene / subject)
  * Bradley-Terry scale values (for comparison)
  * pairwise preference proportions with binomial tests (Holm correction for multiple comparisons)
  * choice rates per scene and per subject

Two input formats are accepted, and may be pooled in the same results/ folder:
  * pairwise (--mode pairwise in experiment.py): one row per 2-way trial (chosen/not_chosen).
  * all-at-once (--mode all): one row per N-way "pick 1 of N" trial (shown/chosen). Each such
    trial is expanded here into N-1 pairwise comparisons (the winner beats every other
    candidate it was shown with), which is unbiased for the pairwise preference matrix under
    the Luce/Bradley-Terry choice model, assuming independence of irrelevant alternatives.
  `choice_rate` is always the pairwise-equivalent rate (0.5 = chance, comparable across both
  formats); `selection_rate` is the literal "won this N-way trial" rate (1/n_candidates = chance),
  only meaningful for all-at-once data.

Usage
-----
python analysis.py                          # all participants in results/ -> figures in analysis/
python analysis.py --boot-unit scene        # bootstrap over scenes (generalize to the image set)
python analysis.py "other_folder/*.csv" --out analysis_other   # explicit files instead
"""
import argparse
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm

# ---- Plot style: light surface, recessive grid; single blue hue for magnitudes,
# ---- orange-gray-blue diverging map for preference proportions (0.5 = neutral gray)
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"
BLUE, BLUE_LIGHT, ORANGE, NEUTRAL = "#2a78d6", "#86b6ef", "#eb6834", "#f0efec"
plt.rcParams.update({
    # Latin fonts first; CJK fonts as fallbacks so non-Latin method/scene names still render
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "Microsoft YaHei", "Noto Sans CJK SC",
                        "PingFang SC", "SimHei", "WenQuanYi Micro Hei", "Arial Unicode MS"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK2, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left",
})
DIVERGING = LinearSegmentedColormap.from_list("pc", [ORANGE, NEUTRAL, BLUE])


# =========================================================================== data
PAIR_COLUMNS = {"subject", "chosen", "not_chosen"}   # one pairwise comparison per row
ALL_COLUMNS = {"subject", "chosen", "shown"}          # one N-alternative "pick 1 of N" trial per row
SHOWN_SEP = ";"


def _edges_from_choices(d, fname):
    """Expand "picked 1 of N" rows (shown/chosen) into one 'chosen beat X' row per other
    shown method. Under the Luce/Bradley-Terry choice model E[W_ij]/E[N_ij] = pi_i/(pi_i+pi_j),
    the same quantity a genuine pairwise trial estimates, so the expanded rows feed the
    usual pairwise machinery unchanged."""
    shown = d["shown"].astype(str).str.split(SHOWN_SEP).apply(
        lambda v: [x.strip() for x in v if x.strip()])
    chosen = d["chosen"].astype(str)
    ok = np.array([c in s for c, s in zip(chosen, shown)])
    if not ok.all():
        print(f"[WARNING] {fname}: {(~ok).sum()} row(s) whose 'chosen' is not in 'shown' are skipped")
    d = d[ok].assign(n_shown=shown[ok].apply(len), _other=shown[ok])
    e = d.explode("_other").rename(columns={"_other": "not_chosen"})
    return e[e["not_chosen"].astype(str) != e["chosen"].astype(str)]


def load(patterns):
    files = sorted({f for p in patterns for f in glob.glob(p)})
    files = [f for f in files if f.lower().endswith(".csv")]
    if not files:
        raise SystemExit("[ERROR] No CSV result files found")
    frames, n_all_files, uid = [], 0, 0
    for f in files:
        try:
            d = pd.read_csv(f)
        except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
            print(f"[WARNING] Skipping unreadable file {f}: {e}")
            continue
        is_all = "shown" in d.columns and "not_chosen" not in d.columns
        if not (ALL_COLUMNS if is_all else PAIR_COLUMNS) <= set(d.columns):
            print(f"[WARNING] Skipping {f}: not a result file (missing columns)")
            continue
        if d.empty:
            print(f"[WARNING] Skipping {f}: contains no trials")
            continue
        d["source_file"] = os.path.basename(f)
        d["trial_uid"] = uid + np.arange(len(d))   # one id per ORIGINAL trial, before any explode
        uid += len(d)
        if is_all:
            d = _edges_from_choices(d, os.path.basename(f))
            n_all_files += 1
        else:
            d["n_shown"] = 2
        frames.append(d)
    if not frames:
        raise SystemExit("[ERROR] None of the CSV files contain usable results")
    df = pd.concat(frames, ignore_index=True)
    if "scene" not in df:
        df["scene"] = "all"
    df["subject"] = df["subject"].astype(str)
    df["scene"] = df["scene"].astype(str)
    # Both formats must agree on dtype: splitting 'shown' always yields strings, so a
    # purely numeric method folder name would otherwise read as int64 from one format and
    # str from the other, silently splitting it into two different "items".
    df["chosen"] = df["chosen"].astype(str)
    df["not_chosen"] = df["not_chosen"].astype(str)
    n_tr = df["trial_uid"].nunique()
    print(f"Loaded {len(frames)} result file(s): {df['subject'].nunique()} participant(s), "
          f"{df['scene'].nunique()} scene(s), {n_tr} trials")
    if len(df) != n_tr:
        print(f"[NOTE] {n_tr} trials expanded into {len(df)} pairwise comparisons for analysis "
              f"(an N-alternative trial contributes one comparison per losing candidate)")
    if 0 < n_all_files < len(frames):
        print("[NOTE] Pooling N-alternative and pairwise result files assumes independence of "
              "irrelevant alternatives (IIA)")
    counts = df.drop_duplicates("trial_uid").groupby("subject").size()
    print("Participants: " + ", ".join(f"{s} ({n})" for s, n in counts.items()))
    return df


def count_matrices(df, items):
    """W[i, j] = number of times i was chosen over j; N = W + W.T = number of comparisons."""
    idx = {k: i for i, k in enumerate(items)}
    W = np.zeros((len(items), len(items)))
    np.add.at(W, (df["chosen"].map(idx).to_numpy(), df["not_chosen"].map(idx).to_numpy()), 1)
    return W, W + W.T


def trial_counts(df, items):
    """Counts each ORIGINAL trial once (not once per expanded comparison): how often a
    method was shown / chosen, and the mean number of candidates it competed against.
    For pairwise-only data this equals (wins, comparisons, 2) exactly."""
    tr = df.drop_duplicates("trial_uid")
    shown = pd.concat([
        tr[["trial_uid", "chosen", "n_shown"]].rename(columns={"chosen": "method"}),
        df[["trial_uid", "not_chosen", "n_shown"]].rename(columns={"not_chosen": "method"}),
    ]).drop_duplicates(["trial_uid", "method"])
    g = shown.groupby("method")
    t_chosen = tr["chosen"].value_counts().reindex(items, fill_value=0).to_numpy()
    t_shown = g.size().reindex(items, fill_value=0).to_numpy()
    n_cand = g["n_shown"].mean().reindex(items).to_numpy()
    return t_chosen, t_shown, n_cand


# =========================================================================== models
def thurstone_case_v(W, N):
    """Thurstone Case V: P(i > j) = Phi(s_i - s_j).
    Proportions are corrected as (w + 0.5) / (n + 1) to avoid infinite z-scores for 0/1
    proportions, then solved by least squares with sum(s) = 0, which also handles
    incomplete designs. The result is shifted so that the lowest value is 0."""
    k = len(W)
    rows, z = [], []
    for i in range(k):
        for j in range(i + 1, k):
            if N[i, j] > 0:
                r = np.zeros(k); r[i], r[j] = 1, -1
                rows.append(r)
                z.append(norm.ppf((W[i, j] + 0.5) / (N[i, j] + 1)))
    s, *_ = np.linalg.lstsq(np.vstack(rows + [np.ones(k)]), np.array(z + [0.0]), rcond=None)
    return s - s.min()


def bradley_terry(W, N, iters=2000, prior=0.1):
    """Bradley-Terry: P(i > j) = pi_i / (pi_i + pi_j), fitted with the MM algorithm
    (Hunter, 2004). A small pseudo-count per compared pair keeps estimates finite when
    an item always wins or always loses. Returns log(pi), shifted so the minimum is 0."""
    Wp = W + prior * (N > 0)
    Np = Wp + Wp.T
    wins = Wp.sum(1)
    pi = np.ones(len(W))
    for _ in range(iters):
        new = wins / (Np / (pi[:, None] + pi[None, :])).sum(1)
        new /= np.exp(np.log(new).mean())
        if np.max(np.abs(new - pi)) < 1e-10:
            break
        pi = new
    ls = np.log(pi)
    return ls - ls.min()


def bootstrap_ci(df, items, n_boot, unit="trial", seed=0):
    """Percentile bootstrap CI of the Thurstone scale. Resampling is always done over
    whole units: unit='trial' resamples whole trials (an N-alternative trial and every
    pairwise comparison derived from it move together, avoiding pseudo-replication),
    'scene' / 'subject' resample whole scenes / subjects."""
    rng = np.random.default_rng(seed)
    idx = {k: i for i, k in enumerate(items)}
    ci = df["chosen"].map(idx).to_numpy()
    cj = df["not_chosen"].map(idx).to_numpy()
    key = df["trial_uid"] if unit == "trial" else df[unit]
    codes, _ = pd.factorize(key, sort=True)
    sizes = np.bincount(codes)
    groups = np.split(np.argsort(codes, kind="stable"), np.cumsum(sizes)[:-1])
    one_row = bool((sizes == 1).all())   # pairwise-only data: every unit is a single row
    out = np.empty((n_boot, len(items)))
    for b in range(n_boot):
        pick = rng.integers(0, len(groups), len(groups))
        rows = pick if one_row else np.concatenate([groups[i] for i in pick])
        W = np.zeros((len(items), len(items)))
        np.add.at(W, (ci[rows], cj[rows]), 1)
        out[b] = thurstone_case_v(W, W + W.T)
    return np.percentile(out, [2.5, 97.5], axis=0)


def wilson(k, n, z=1.96):
    """Wilson score interval for a binomial proportion."""
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def pair_rate(p, n):
    """Selection rate out of n alternatives -> equivalent pairwise preference rate.
    An N-alternative trial expands into n-1 comparisons, giving (n-1)p / (1+(n-2)p);
    identity for n = 2, and 0.5 at chance (p = 1/n) for every n."""
    return (n - 1) * p / (1 + (n - 2) * p)


def holm(pvals):
    """Holm-Bonferroni adjusted p-values."""
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (len(p) - rank) * p[i])
        adj[i] = min(1.0, running)
    return adj


# =========================================================================== tables
def summarize(df, n_boot, boot_unit):
    items = sorted(set(df["chosen"]) | set(df["not_chosen"]))
    W, N = count_matrices(df, items)
    s_th = thurstone_case_v(W, N)
    s_bt = bradley_terry(W, N)
    ci = bootstrap_ci(df, items, n_boot, boot_unit)
    wins, comps = W.sum(1), N.sum(1)
    t_chosen, t_shown, n_cand = trial_counts(df, items)
    p = t_chosen / t_shown                        # N-way selection rate (chance = 1/n_candidates)
    p_lo, p_hi = wilson(t_chosen, t_shown)         # CI from independent TRIALS, not expanded edges
    lo, hi = pair_rate(p_lo, n_cand), pair_rate(p_hi, n_cand)   # monotone map -> still a valid CI
    summary = pd.DataFrame({
        "method": items, "times_chosen": wins.astype(int), "times_shown": comps.astype(int),
        "choice_rate": wins / comps, "rate_ci_low": lo, "rate_ci_high": hi,
        "thurstone": s_th, "thurstone_ci_low": ci[0], "thurstone_ci_high": ci[1],
        "bradley_terry_log": s_bt,
        "trials_chosen": t_chosen.astype(int), "trials_shown": t_shown.astype(int),
        "selection_rate": p, "n_candidates": n_cand,
    }).sort_values("thurstone", ascending=False, ignore_index=True)
    summary.insert(0, "rank", np.arange(1, len(items) + 1))

    # Two-sided binomial test per method pair against chance (0.5)
    rows = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            n = int(N[i, j])
            if n == 0:
                continue
            p = binomtest(int(W[i, j]), n, 0.5).pvalue
            rows.append({"method_a": items[i], "method_b": items[j], "a_chosen": int(W[i, j]),
                         "b_chosen": int(W[j, i]), "n": n, "p_a_over_b": W[i, j] / n, "p_value": p})
    pairwise = pd.DataFrame(rows)
    pairwise["p_holm"] = holm(pairwise["p_value"]) if len(pairwise) else []
    pairwise["significant"] = pairwise["p_holm"] < 0.05

    def rate_by(col):
        """Choice rate of each method within each level of `col` (scene or subject)."""
        a = df.groupby([col, "chosen"]).size().rename("chosen_n")
        b = pd.concat([df[[col, "chosen"]].rename(columns={"chosen": "method"}),
                       df[[col, "not_chosen"]].rename(columns={"not_chosen": "method"})]
                      ).groupby([col, "method"]).size().rename("shown_n")
        a.index.names = [col, "method"]
        t = pd.concat([a, b], axis=1).fillna(0)
        t["rate"] = t["chosen_n"] / t["shown_n"]
        return t.reset_index()

    return items, W, N, summary, pairwise, rate_by("scene"), rate_by("subject")


# =========================================================================== plots
def _clean(ax):
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)


def plot_main(items, W, N, summary, pairwise, per_scene, out_png, question=None, n_trials=None):
    order = summary["method"].tolist()          # best to worst
    k = len(order)
    y = np.arange(k)[::-1]

    fig, axes = plt.subplots(2, 2, figsize=(13, 10))
    fig.subplots_adjust(hspace=0.42, wspace=0.38, left=0.1, right=0.95, top=0.9, bottom=0.1)
    fig.suptitle("Paired comparison of methods", x=0.1, y=0.975, ha="left",
                 fontsize=16, fontweight="bold")
    n_cmp = int(N.sum() / 2)
    count_text = (f"{n_trials} trials, {n_cmp} derived pairwise comparisons"
                  if n_trials is not None and n_trials != n_cmp else f"{n_cmp} comparisons")
    fig.text(0.1, 0.935, (f"Task: {question}    " if question else "") + count_text,
             color=INK2, fontsize=10)

    # A: choice rate --------------------------------------------------------
    ax = axes[0, 0]
    r = summary["choice_rate"].to_numpy()
    lo, hi = summary["rate_ci_low"].to_numpy(), summary["rate_ci_high"].to_numpy()
    ax.barh(y, r, height=0.6, color=BLUE)
    ax.errorbar(r, y, xerr=[r - lo, hi - r], fmt="none", ecolor=INK2, elinewidth=1.2, capsize=3)
    ax.axvline(0.5, color=MUTED, lw=1, ls="--")
    for yi, (rv, h, c, n) in enumerate(zip(r, hi, summary["times_chosen"], summary["times_shown"])):
        ax.text(h + 0.02, y[yi], f"{rv:.0%}  ({c}/{n})", va="center", fontsize=9, color=INK2)
    ax.set_yticks(y, order)
    ax.set_xlim(0, 1.18)
    ax.set_xticks(np.linspace(0, 1, 6), [f"{v:.0%}" for v in np.linspace(0, 1, 6)])
    ax.set_xlabel("Choice rate (times chosen / times shown); error bars = Wilson 95% CI")
    ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
    ax.set_title("A  How often each method was chosen")

    # B: Thurstone scale -----------------------------------------------------
    ax = axes[0, 1]
    s = summary["thurstone"].to_numpy()
    ax.hlines(y, summary["thurstone_ci_low"], summary["thurstone_ci_high"], color=BLUE_LIGHT, lw=3)
    ax.plot(s, y, "o", color=BLUE, ms=9, mec=SURFACE, mew=2, zorder=3)
    for yi, v in zip(y, s):
        ax.text(v, yi + 0.28, f"{v:.2f}", ha="center", fontsize=9, color=INK2)
    ax.set_yticks(y, order)
    ax.set_ylim(-0.6, k - 0.25)
    ax.set_xlabel("Thurstone Case V scale value (z units; worst method = 0)")
    ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
    ax.set_title("B  Perceptual scale (95% bootstrap CI)")

    # C: pairwise preference matrix -----------------------------------------
    ax = axes[1, 0]
    idx = [items.index(m) for m in order]
    with np.errstate(invalid="ignore", divide="ignore"):
        P = (W / N)[np.ix_(idx, idx)]
    im = ax.imshow(np.ma.masked_invalid(P), cmap=DIVERGING, vmin=0, vmax=1)
    sig = {}
    for _, row in pairwise.iterrows():
        sig[(row.method_a, row.method_b)] = sig[(row.method_b, row.method_a)] = row.p_holm
    if k <= 12:  # annotate cells only when the matrix is small enough to stay legible
        for i in range(k):
            for j in range(k):
                if i == j or np.isnan(P[i, j]):
                    continue
                p = sig.get((order[i], order[j]), 1)
                star = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
                ax.text(j, i, f"{P[i, j]:.2f}{chr(10) + star if star else ''}", ha="center",
                        va="center", fontsize=8 if k > 6 else 9, linespacing=0.9,
                        color="white" if abs(P[i, j] - 0.5) > 0.3 else INK)
    ax.set_xticks(range(k), order, rotation=40, ha="right")
    ax.set_yticks(range(k), order)
    _clean(ax)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Proportion: row method preferred over column", color=INK2)
    cb.outline.set_visible(False)
    ax.set_title("C  Pairwise preference (* Holm-corrected p < .05)")

    # D: choice rate per scene ----------------------------------------------
    ax = axes[1, 1]
    piv = per_scene.pivot(index="method", columns="scene", values="rate").reindex(order)
    scenes = list(piv.columns)
    im2 = ax.imshow(np.ma.masked_invalid(piv[scenes].to_numpy(float)), cmap=DIVERGING,
                    vmin=0, vmax=1, aspect="auto", interpolation="nearest")
    ax.set_yticks(range(k), order)
    if len(scenes) <= 30:
        ax.set_xticks(range(len(scenes)), scenes, rotation=60, ha="right", fontsize=8)
    else:
        ax.set_xticks([])
    ax.set_xlabel(f"Scene ({len(scenes)} in total)")
    _clean(ax)
    cb = fig.colorbar(im2, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Choice rate within scene", color=INK2)
    cb.outline.set_visible(False)
    ax.set_title("D  Choice rate per scene")

    fig.savefig(out_png, dpi=200)
    fig.savefig(os.path.splitext(out_png)[0] + ".pdf")
    plt.close(fig)


def plot_subjects(summary, per_subject, out_png):
    """Per-subject choice rates (gray dots) with the across-subject mean (blue diamond)."""
    order = summary["method"].tolist()
    k = len(order)
    y = np.arange(k)[::-1]
    subs = sorted(per_subject["subject"].unique())
    fig, ax = plt.subplots(figsize=(8, 0.6 * k + 2))
    fig.subplots_adjust(left=0.18, right=0.95, top=0.86, bottom=0.14)
    rng = np.random.default_rng(1)
    for yi, m in zip(y, order):
        v = per_subject.loc[per_subject["method"] == m, "rate"].to_numpy()
        ax.scatter(v, yi + rng.uniform(-0.15, 0.15, len(v)), s=28, color=MUTED, alpha=0.7,
                   edgecolor=SURFACE, lw=0.8, zorder=2)
    mean_rate = per_subject.groupby("method")["rate"].mean().reindex(order)
    ax.plot(mean_rate.to_numpy(), y, "D", color=BLUE, ms=9, mec=SURFACE, mew=1.5, zorder=3)
    ax.axvline(0.5, color=MUTED, lw=1, ls="--")
    ax.set_yticks(y, order)
    ax.set_xlim(-0.02, 1.02)
    ax.set_xticks(np.linspace(0, 1, 6), [f"{v:.0%}" for v in np.linspace(0, 1, 6)])
    ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
    ax.set_xlabel("Choice rate")
    fig.suptitle("Choice rate per subject", x=0.18, ha="left", fontsize=14, fontweight="bold")
    fig.text(0.18, 0.885, f"Gray dots = individual subjects (n = {len(subs)}); "
             f"blue diamonds = mean across subjects", color=INK2, fontsize=9)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)


# =========================================================================== main
def analyze(patterns, out_dir="analysis", n_boot=1000, boot_unit="trial", question=None):
    df = load(patterns)
    if boot_unit != "trial" and df[boot_unit].nunique() < 5:
        print(f"[NOTE] Fewer than 5 levels of '{boot_unit}'; falling back to trial resampling")
        boot_unit = "trial"
    items, W, N, summary, pairwise, per_scene, per_subject = summarize(df, n_boot, boot_unit)

    os.makedirs(out_dir, exist_ok=True)
    summary.to_csv(os.path.join(out_dir, "method_summary.csv"), index=False, float_format="%.4f")
    pairwise.to_csv(os.path.join(out_dir, "pairwise_tests.csv"), index=False, float_format="%.4g")
    per_scene.to_csv(os.path.join(out_dir, "per_scene.csv"), index=False, float_format="%.4f")
    per_subject.to_csv(os.path.join(out_dir, "per_subject.csv"), index=False, float_format="%.4f")
    with np.errstate(invalid="ignore", divide="ignore"):
        pd.DataFrame(W / N, index=items, columns=items).to_csv(
            os.path.join(out_dir, "preference_matrix.csv"), float_format="%.4f")

    n_trials = df["trial_uid"].nunique()
    plot_main(items, W, N, summary, pairwise, per_scene, os.path.join(out_dir, "results.png"),
              question, n_trials)
    figs = ["results.png", "results.pdf"]
    if df["subject"].nunique() > 1:
        plot_subjects(summary, per_subject, os.path.join(out_dir, "per_subject.png"))
        figs.append("per_subject.png")

    pd.set_option("display.width", 200)
    cols = ["rank", "method", "times_chosen", "times_shown", "choice_rate", "thurstone",
            "thurstone_ci_low", "thurstone_ci_high", "bradley_terry_log"]
    if summary["n_candidates"].max() > 2:
        cols += ["trials_chosen", "trials_shown", "selection_rate"]
    print("\n" + summary[cols].to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"\nPairwise tests (Holm-corrected): {int(pairwise['significant'].sum())} / "
          f"{len(pairwise)} pairs differ significantly")
    print(f"Bootstrap resampling unit: {boot_unit}")
    print(f"Output written to {out_dir}/: {', '.join(figs)}, method_summary.csv, pairwise_tests.csv, "
          f"preference_matrix.csv, per_scene.csv, per_subject.csv")
    return summary


def main():
    p = argparse.ArgumentParser(description="Analysis of multi-method paired-comparison data")
    p.add_argument("files", nargs="*",
                   help='CSV files (wildcards allowed). Default: every CSV in --results-dir')
    p.add_argument("--results-dir", default="results",
                   help="Folder with one result CSV per participant (written by experiment.py)")
    p.add_argument("--out", default="analysis", help="Output folder for figures and tables")
    p.add_argument("--boot", type=int, default=1000, help="Number of bootstrap samples")
    p.add_argument("--boot-unit", choices=["trial", "scene", "subject"], default="trial",
                   help="Bootstrap resampling unit ('trial' resamples whole trials, including "
                        "every pairwise comparison derived from an N-alternative trial together)")
    p.add_argument("--question", help="Task description to print on the figure (optional)")
    a = p.parse_args()
    files = a.files or [os.path.join(a.results_dir, "*.csv")]
    analyze(files, a.out, a.boot, a.boot_unit, a.question)


if __name__ == "__main__":
    main()
