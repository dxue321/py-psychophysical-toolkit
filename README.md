**English | [中文](README.zh-CN.md) | [Español](README.es.md)**

---

# Python Psychophysical Toolkit

A Python tool for running forced-choice **user studies** that compare image processing methods, with a workflow similar to Psychtoolbox.

- Two trial designs, picked with `mode` in the config: 

**pairwise** (2AFC) shows two randomly-paired method results side by side (left/right randomized), with an optional reference image between them; 

**all** (N-AFC) shows every method's result for a scene at once in a row, and the subject picks the single best one — with an optional reference image centered on its own row above that. It's a blind test — method names are never shown.

- Multiple subjects can run in sequence; each subject's results are saved to their own file and never overwritten.
- Built-in analysis: aggregates all subjects, runs statistical tests, and plots results.
- Can export vector figures sized for two-column conference paper templates, with matching LaTeX snippets.

## Quick start

```bash
pip install -r requirements.txt
python make_demo_data.py                                     # generate demo images
python experiment.py --config config/config_with_reference.json --adapt 60   # pairwise (2AFC)
python experiment.py --config config/config_all_methods.json --adapt 60      # all-at-once (N-AFC)
python analysis.py                                           # results -> analysis/
python paper_figure.py --ours Ours                            # paper figures -> paper_figures/
```

Requires Python 3.9+.

## Files

| File | Purpose |
|---|---|
| `experiment.py` | Runs one subject's session and saves their results |
| `analysis.py` | Aggregates `results/`, outputs stats tables + summary plots |
| `paper_figure.py` | Exports paper-ready vector figures + LaTeX code |
| `make_demo_data.py` | Generates demo images, for trying the tool out |
| `simulate.py` | Simulates subject data, to test the pipeline or estimate sample size |
| `config/config_with_reference.json` / `config/config_without_reference.json` | Example pairwise configs (with / without a reference image) |
| `config/config_all_methods.json` | Example all-at-once (N-AFC) config |

Output folders (auto-created, git-ignored): `results/`, `analysis/`, `paper_figures/`.

## Step 1 — Organize your images

One subfolder per method, same filenames across methods:

```
my_study/
├── methods/              ← "root" in the config
│   ├── Ours/       001.png  002.png  003.png ...
│   ├── BM3D/       001.png  002.png  003.png ...
│   └── DnCNN/      001.png  002.png  003.png ...
└── reference/            ← optional, "reference" in the config
    001.png  002.png  003.png ...
```

Matching ignores the extension (`001.png` = `001.jpg`). A scene missing from any method (or the reference) is skipped, with a warning. Use `exclude` to drop a subfolder, or `methods` to list only the ones you want.

## Step 2 — Write a config file

Copy `config/config_with_reference.json` (shows "candidate | reference | candidate"), `config/config_without_reference.json` (just two candidates, no reference), or `config/config_all_methods.json` (every method at once — see Step 4) and edit it. Any CLI flag overrides the matching config key, e.g. `--adapt 5`.

Most useful keys:

| Key | CLI flag | Default | Meaning |
|---|---|---|---|
| `mode` | `--mode` | pairwise | `pairwise` (2AFC) or `all` (show every method at once, N-AFC) |
| `root` | `--root` | — | Folder containing one subfolder per method |
| `reference` | `--reference` | none | Reference image folder, or `null` for none |
| `question` | `--question` | "Which image has better quality?" | Shown on every trial |
| `adapt` | `--adapt` | 60 | Light-adaptation time (s); 0 to skip |
| `n_trials` | `--n-trials` | all | Randomly sample this many trials (balanced across pairs in pairwise mode) |
| `seed` | `--seed` | random | Fix for reproducible trial order |
| `fullscreen` | `--fullscreen` | false | Turn on for the real experiment |
| `mouse` | `--mouse` | false | Allow clicking images instead of keys (required if `mode: all` has >9 methods) |

<details>
<summary>Full list of config options</summary>

| Key (CLI flag) | Default | Description |
|---|---|---|
| `mode` (`--mode`) | pairwise | `pairwise` or `all` (see Step 4) |
| `root` (`--root`) | — | Root folder of methods, one subfolder per method |
| `methods` (`--methods`) | — | List method folders directly, instead of `root` |
| `exclude` (`--exclude`) | none | Subfolders to exclude when using `root` |
| `reference` (`--reference`) | none | Reference image folder, or `null` to disable |
| `question` (`--question`) | see above | The experiment's question |
| `instructions` (`--instructions`) | built-in | Instructions-page text file (UTF-8) |
| `adapt` (`--adapt`) | 60 | Light-adaptation duration (s); 0 skips it |
| `repeats` (`--repeats`) | 1 | Repeats of the full design — scenes × method pairs (pairwise) or scenes only (all) |
| `n_trials` (`--n-trials`) | all | Sample this many trials, balanced across pairs (pairwise) or scenes (all) |
| `seed` (`--seed`) | random | Fix for reproducible trial order |
| `fixation` / `iti` | 0.5 / 0.3 | Fixation duration, inter-trial interval (s) |
| `duration` (`--duration`) | 0 | Image display time (s); 0 = until response |
| `break_every` (`--break-every`) | 50 | Trials between breaks; 0 disables breaks |
| `show_progress` | false | Show progress bottom-right |
| `mouse` (`--mouse`) | false | Allow mouse-click responses |
| `fullscreen` (`--fullscreen`) | false | Recommended for the real experiment |
| `window` (`--window W H`) | 1600 900 | Window size when not fullscreen |
| `bg` / `fg` | [128,128,128] / [230,230,230] | Background / text color (RGB) |
| `gap` (`--gap`) | 0.02 | Gap between images, fraction of screen width |
| `upscale` (`--upscale`) | false | Allow upscaling images to fill the screen |
| `out_dir` (`--out-dir`) | results | Results folder |
| `--subject` (CLI only) | screen entry | Set subject code directly, skip name entry |
| `--dry-run` (CLI only) | — | Check folders / count trials, don't run |

The instructions text supports placeholders: `{question}`, `{n_trials}`, `{break_every}`, `{ref_sentence}`, `{ref_hint}`, `{mouse_sentence}`, `{n_methods}` — all filled in automatically. With `mode: all` and no custom `--instructions`, a built-in template describing the digit-key responses is used instead of the pairwise one.
</details>

## Step 3 — Dry run

```bash
python experiment.py --config config/config_with_reference.json --dry-run     # check folders & trial count, no window
python experiment.py --config config/config_with_reference.json --adapt 5 --n-trials 10   # try it yourself
```

The trial count printed depends on `mode`: pairwise is `scenes × M(M−1)/2 × repeats`, all is just `scenes × repeats` (see Design tips). Dry-run output also lands in `results/` — delete it before the real experiment.

## Step 4 — Run the real experiment

Run once per subject:

```bash
python experiment.py --config config/config_with_reference.json
```

Flow: enter name → confirm save code → instructions (space to continue) → light adaptation → trials (fixation → images → response) → done.

With `mode: all` and a reference image, the layout is two rows: the reference centered on its own row, with every candidate side by side in a row below it. Example trial screens (using the demo images), showing the difference between the two designs:

| `mode: pairwise` | `mode: all` |
|---|---|
| ![Pairwise trial: two candidates with the reference in the middle](assets/screenshot_pairwise.png) | ![All-at-once trial: the reference centered above every candidate](assets/screenshot_all.png) |
| two candidates per trial, reference between them | every candidate at once, reference on its own row above |

**Keys (`mode: pairwise`):** `←`/`F` = left, `→`/`J` = right, `ESC` = quit anytime.
**Keys (`mode: all`):** `1`–`9` = pick the image under that number, `ESC` = quit anytime. More than 9 methods requires `--mouse` (digits can only address 9 positions); either way, with `mouse: true` you can also click any image to choose it.

Each subject's results go to `results/<name>.csv` (duplicates auto-renamed `<name>_2`, etc. — never overwritten). Progress is saved after every trial, so nothing is lost if a subject quits early.

## Step 5 — Analyze

```bash
python analysis.py
```

Reads everything in `results/` and writes to `analysis/` (both trial designs can be mixed in the same folder — see Statistics below):

- **`results.png`/`.pdf`** — choice rate, Thurstone scale, pairwise preference matrix, per-scene breakdown
- **`per_subject.png`** — consistency check across subjects
- **`method_summary.csv`, `pairwise_tests.csv`, `preference_matrix.csv`, `per_scene.csv`, `per_subject.csv`**

Rerun anytime a subject is added — it always re-reads all of `results/`. Useful flags: `--boot-unit scene` (more conservative resampling), `--question "..."` (print the question on the figures).

## Step 6 — Paper figures

```bash
python paper_figure.py --ours Ours
python paper_figure.py --ours Ours --rename Blur="Gaussian blur" --order Ours BM3D DnCNN
```

Writes vector PDFs (+ PNG previews) sized for two-column conference templates, plus `latex_snippets.tex` with ready-to-paste `\includegraphics` blocks and captions:

| File | Size | Content |
|---|---|---|
| `fig_preference_rate.pdf` | single column | Choice rate per method |
| `fig_scale.pdf` | single column | Thurstone scale values |
| `fig_pairwise.pdf` | single column | Pairwise preference matrix |
| `fig_ours_vs.pdf` | single column | Your method vs. each baseline |
| `fig_overview.pdf` | full width | All three panels combined |

Example `fig_overview` (PNG preview), from `simulate.py` demo data:

![Example fig_overview: preference rate, perceptual scale, and pairwise preference panels](assets/paper_figure_example.png)

Key flags: `--ours NAME` (highlight + generate `fig_ours_vs`), `--rename folder=label`, `--order A B C`, `--font serif|sans`, `--font-size N`.

In LaTeX, size with `\linewidth` / `\textwidth` — the figures are already drawn at that exact size, so they won't be rescaled.

## Data format

One row per trial, one CSV per subject. The schema depends on `mode`:

**`mode: pairwise`**

| Column | Meaning |
|---|---|
| `subject`, `trial`, `scene` | Subject code, trial index, scene name |
| `left` / `right` | Methods shown on each side |
| `chosen` / `not_chosen` | Which was picked |
| `chosen_side`, `rt`, `reference`, `scale`, `timestamp` | Side picked, response time, had-reference flag, display scale, time |

**`mode: all`**

| Column | Meaning |
|---|---|
| `subject`, `trial`, `scene` | Subject code, trial index, scene name |
| `shown` | All candidate methods, `;`-joined, in left-to-right display order |
| `chosen` | The winning method |
| `position`, `rt`, `reference`, `scale`, `timestamp` | 1-based rank of `chosen` in `shown`, response time, had-reference flag, display scale, time |

Any tool that produces either set of columns (e.g. PsychoPy) works with `analysis.py` / `paper_figure.py`, which detect the format per file — minimum required is `subject`, `chosen`, and either `not_chosen` or `shown`. Files of both kinds may sit in the same `results/` folder; `analysis.py` expands each all-mode trial into one pairwise comparison per losing candidate before analyzing it (valid under independence of irrelevant alternatives, IIA). If the two designs belong to two separate studies rather than one study comparing both, use a different `out_dir` for each — split by study, not by `mode` — so unrelated data never gets pooled into the same analysis by accident.

## Statistics, briefly

- **Choice rate** — wins ÷ appearances, as a pairwise comparison (for `mode: all` data, each trial counts as the winner beating every other candidate shown with it). Wilson confidence interval. 50% = average, comparable across both modes.
- **Selection rate** (`mode: all` only) — literally how often a method won the N-way trials it appeared in; chance level is `1/n_candidates`, not 50%.
- **Thurstone scale** — perceptual scale derived from all pairwise comparisons (z-score units, worst method = 0).
- **Bradley–Terry** — alternative pairwise model, reported for comparison; usually agrees closely with Thurstone.
- **Pairwise tests** — two-sided binomial test vs. 50%, Holm-corrected. `*` p<.05, `**` p<.01, `***` p<.001.
- **`--boot-unit`** — what bootstrap resamples over: `trial` (default — a whole N-way trial moves as one unit, not each derived comparison separately), `scene` (to generalize across image types), or `subject` (needs 5+ subjects).

## Design tips

- **Trial count**: pairwise = scenes × M(M−1)/2 × repeats (M = # methods); all = scenes × repeats. Use `n_trials` to subsample if that's too many.
- **Choosing a design** — `all` gives a direct "best of M" judgement in far fewer trials, but each trial yields fewer independent pairwise observations and the images are smaller on screen; it's most practical up to about 5–6 methods (hard cap: 9 without `--mouse`).
- **Subjects** — aim for 15–30+. Use `simulate.py` beforehand to estimate how many you need (it supports `--mode all` too).
- **Display** — use fullscreen, fixed brightness/color temperature/viewing distance. For quality evaluation, display at 100% (watch for the "shown at xx%" warning) — crop images or drop the reference if they don't fit.
- **Non-English UI** — just write `question` / the instructions text in your language; the program picks a matching font automatically.
- **Timing** — pygame isn't frame-synced; for frame-accurate timing, collect data in PsychoPy instead and reuse this project's `analysis.py` / `paper_figure.py` on the output.
