"""
Simulated observers: reads the same folder layout as the real experiment and generates
choice data according to a Thurstone model, for either trial design (--mode).
Use it to check the analysis pipeline before the real experiment, or to estimate how
many subjects / repeats are needed to tell the methods apart.

python simulate.py --root demo_images/methods --subjects 8 \
       --truth Ours=2.0 Blur=1.0 JPEG=0.8 Noise=0.0
python simulate.py --root demo_images/methods --mode all --subjects 8 --repeats 6 \
       --truth Ours=2.0 Blur=1.0 JPEG=0.8 Noise=0.0
python analysis.py "data_sim/*.csv" --out results_sim
"""
import argparse
import csv
import os

import numpy as np

from experiment import SHOWN_SEP, build_dataset, build_trials, build_trials_all, collect_methods


def main():
    p = argparse.ArgumentParser(description="Generate simulated comparison data")
    p.add_argument("--root")
    p.add_argument("--methods", nargs="+")
    p.add_argument("--exclude", nargs="*")
    p.add_argument("--reference")
    p.add_argument("--mode", choices=["pairwise", "all"], default="pairwise",
                   help="pairwise: simulate 2AFC trials. all: simulate N-AFC trials "
                        "(pick the best of every method at once)")
    p.add_argument("--truth", nargs="*", default=[],
                   help="True scale value per method, e.g. Ours=2 Blur=1; unspecified methods default to 0")
    p.add_argument("--scene-sd", type=float, default=0.4,
                   help="SD of the scene-specific variation in each method's effect")
    p.add_argument("--subjects", type=int, default=8)
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--n-trials", type=int)
    p.add_argument("--out-dir", default="data_sim")
    a = p.parse_args()

    methods = collect_methods(a)
    scenes, _ = build_dataset(methods, a.reference)
    truth = {m: 0.0 for m in methods}
    truth.update({k: float(v) for k, v in (t.split("=") for t in a.truth)})
    print("True scale values:", truth)

    os.makedirs(a.out_dir, exist_ok=True)
    rng_scene = np.random.default_rng(999)
    scene_eff = {(m, s): rng_scene.normal(0, a.scene_sd) for m in methods for s in scenes}
    for k in range(a.subjects):
        rng = np.random.default_rng(k)
        sub = f"SIM{k+1:02d}"
        path = os.path.join(a.out_dir, f"{sub}_sim.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            if a.mode == "all":
                w.writerow(["subject", "trial", "scene", "shown", "chosen", "position",
                            "rt", "reference", "scale", "timestamp"])
                trials = build_trials_all(scenes, list(methods), a.repeats, a.n_trials, seed=k)
                for t, (s, order) in enumerate(trials, 1):
                    # Internal response per candidate = true value + scene effect + trial
                    # noise; the winner is the argmax (the N-way extension of the pairwise
                    # Case V comparison below).
                    vals = [truth[m] + scene_eff[(m, s)] + rng.normal(0, np.sqrt(0.5)) for m in order]
                    win_idx = int(np.argmax(vals))
                    runner_up = sorted(vals)[-2] if len(vals) > 1 else vals[0]
                    rt = 0.5 + rng.gamma(2, 0.4) / (1 + abs(vals[win_idx] - runner_up))
                    w.writerow([sub, t, s, SHOWN_SEP.join(order), order[win_idx], win_idx + 1,
                                f"{rt:.4f}", int(bool(a.reference)), "1.0", ""])
            else:
                w.writerow(["subject", "trial", "scene", "left", "right", "chosen", "not_chosen",
                            "chosen_side", "rt", "reference", "scale", "timestamp"])
                trials = build_trials(scenes, list(methods), a.repeats, a.n_trials, seed=k)
                for t, (s, L, R) in enumerate(trials, 1):
                    # Internal response = true value + scene effect + trial noise.
                    # Noise SD sqrt(0.5) per image gives SD 1 for the difference (Case V units).
                    vL = truth[L] + scene_eff[(L, s)] + rng.normal(0, np.sqrt(0.5))
                    vR = truth[R] + scene_eff[(R, s)] + rng.normal(0, np.sqrt(0.5))
                    side = "left" if vL > vR else "right"
                    ch, ot = (L, R) if side == "left" else (R, L)
                    rt = 0.5 + rng.gamma(2, 0.4) / (1 + abs(vL - vR))  # harder pairs -> slower
                    w.writerow([sub, t, s, L, R, ch, ot, side, f"{rt:.4f}", int(bool(a.reference)), "1.0", ""])
        print(path)


if __name__ == "__main__":
    main()
