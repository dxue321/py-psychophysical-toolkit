"""
Generate a set of demo images with the same folder layout as a real experiment,
for trying out the experiment and analysis pipeline:

demo_images/
    reference/              original images (reference)
    methods/
        Ours/               mild noise only (best quality)
        Blur/               Gaussian blur
        Noise/              strong additive noise
        JPEG/               heavy JPEG compression

python make_demo_data.py
python experiment.py --subject T01 --root demo_images/methods --reference demo_images/reference --adapt 5
"""
import io
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def make_scene(seed, w=480, h=360):
    """Procedural test image: smooth color gradients plus random shapes and stripes."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w] / max(w, h)
    base = np.stack([
        0.5 + 0.4 * np.sin(2 * np.pi * (xx * rng.uniform(0.5, 2) + rng.uniform())),
        0.5 + 0.4 * np.sin(2 * np.pi * (yy * rng.uniform(0.5, 2) + rng.uniform())),
        0.5 + 0.4 * np.cos(2 * np.pi * ((xx + yy) * rng.uniform(0.3, 1.5))),
    ], -1)
    img = Image.fromarray((base * 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for _ in range(12):  # shapes with sharp edges make blur and compression artifacts visible
        x0, y0 = rng.integers(0, w - 60), rng.integers(0, h - 60)
        x1, y1 = x0 + rng.integers(30, 160), y0 + rng.integers(30, 160)
        col = tuple(int(c) for c in rng.integers(0, 256, 3))
        (d.ellipse if rng.random() < 0.5 else d.rectangle)([x0, y0, x1, y1], fill=col)
    for k in range(0, w, 6):  # fine stripe texture
        d.line([(k, h - 40), (k, h)], fill=(30, 30, 30) if (k // 6) % 2 else (230, 230, 230))
    return img


def jpeg(img, q):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=q)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def noisy(img, sigma, seed):
    a = np.asarray(img, float) + np.random.default_rng(seed).normal(0, sigma, (img.height, img.width, 3))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def main(out="demo_images", n_scenes=8):
    methods = {
        "Ours":  lambda im, s: noisy(im, 4, s),
        "Blur":  lambda im, s: im.filter(ImageFilter.GaussianBlur(1.6)),
        "Noise": lambda im, s: noisy(im, 18, s),
        "JPEG":  lambda im, s: jpeg(im, 12),
    }
    os.makedirs(f"{out}/reference", exist_ok=True)
    for m in methods:
        os.makedirs(f"{out}/methods/{m}", exist_ok=True)
    for i in range(n_scenes):
        name = f"scene_{i+1:02d}.png"
        im = make_scene(i)
        im.save(f"{out}/reference/{name}")
        for m, f in methods.items():
            f(im, 100 + i).save(f"{out}/methods/{m}/{name}")
    print(f"Generated {n_scenes} scenes x {len(methods)} methods -> {out}/")


if __name__ == "__main__":
    main()
