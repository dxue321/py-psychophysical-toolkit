"""
Multi-method image comparison experiment (2AFC or N-AFC)
==========================================================
Typical use case: the same set of source images is processed by M different methods,
and each method's results are stored in its own folder, with matching file names for
the same scene across folders. Two trial designs are available via --mode:

  --mode pairwise (default): on each trial, one scene and two methods are drawn at
    random, the two results are shown left/right in random order, and the observer
    picks the one that better satisfies the task.
  --mode all: on each trial, one scene is drawn and ALL methods' results are shown at
    once, in random left-to-right order, and the observer picks the single best one.

Optionally, a reference image is also shown: for --mode pairwise it sits between the
two candidates in the same row; for --mode all it is shown centered on its own row,
with every candidate side by side in a row below it.

Folder layout example
---------------------
processed/
    methodA/  001.png 002.png ...
    methodB/  001.png 002.png ...
    methodC/  001.png 002.png ...
reference/    001.png 002.png ...      (optional)

Usage
-----
python experiment.py --root processed --question "Which image has better quality?"
python experiment.py --root processed --reference reference --fullscreen
python experiment.py --methods processed/methodA processed/methodC --repeats 2
python experiment.py --root processed --mode all --mouse     # show all methods at once
python experiment.py --config config.json                  # parameters from a config file

Session flow: participant name entry -> instructions -> light adaptation (gray-screen
countdown) -> trials (fixation -> images -> response) -> end screen.
Keys: --mode pairwise: Left / F = choose left, Right / J = choose right.
      --mode all: digit keys 1-9 = choose the image under that number (candidate count
      is capped at 9 unless --mouse is also given).
ESC quits at any time (completed trials are saved). With --mouse, observers can also
click on an image to respond, in either mode.

Results
-------
Each participant's results are saved as one file, results/<name>.csv (the folder is
created automatically). If no name is entered, an ID such as P001 is assigned. If the
name already has a result file, the new session is saved as <name>_2, <name>_3, ...,
so earlier results are never overwritten. Session metadata (all settings) goes to
results/session_info/<name>.json. --mode pairwise and --mode all write different CSV
schemas (see analysis.py), but both may be analyzed together from the same results/
folder. analysis.py analyzes every CSV in results/ by default.
"""
import argparse
import csv
import itertools
import json
import os
import random
import re
import sys
import time
from collections import defaultdict
from datetime import datetime

# Windows HiDPI: opt out of system DPI scaling; otherwise Windows upsamples the window
# and the interpolation would affect image-quality judgements.
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame

IMG_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif")
LEFT_KEYS = (pygame.K_LEFT, pygame.K_f)
RIGHT_KEYS = (pygame.K_RIGHT, pygame.K_j)
SHOWN_SEP = ";"                      # separator for the 'shown' CSV column in --mode all
MAX_DIGIT_CHOICES = 9                # digit keys can only address up to 9 on-screen positions
# digit / numpad keys -> 0-based candidate position, for --mode all responses
NUM_KEYS = {k: d - 1 for d in range(1, MAX_DIGIT_CHOICES + 1)
            for k in (getattr(pygame, f"K_{d}"), getattr(pygame, f"K_KP{d}"))}

DEFAULT_INSTRUCTIONS = """Instructions

Welcome, and thank you for taking part. On each trial you will see two images{ref_sentence}.
Following the instruction below, choose the image that better meets the requirement:

        {question}

- The left/right position of the images is random and says nothing about which is better.
- There are no right or wrong answers; respond according to your own impression. Do not deliberate too long, but do not answer at random either.
- Press LEFT or F to choose the left image, RIGHT or J to choose the right image.{mouse_sentence}
- There are {n_trials} judgements in total, with a short break about every {break_every} trials.
- Please keep your viewing distance and posture roughly constant throughout.

If you have any questions, please ask the experimenter now."""

DEFAULT_INSTRUCTIONS_ALL = """Instructions

Welcome, and thank you for taking part. On each trial you will see {n_methods} images at once{ref_sentence}.
Following the instruction below, choose the image that best meets the requirement:

        {question}

- The left-to-right order of the images is random and says nothing about which is better.
- There are no right or wrong answers; respond according to your own impression. Do not deliberate too long, but do not answer at random either.
- Press the number key (1-{n_methods}) shown under the image you judge best.{mouse_sentence}
- There are {n_trials} judgements in total, with a short break about every {break_every} trials.
- Please keep your viewing distance and posture roughly constant throughout.

If you have any questions, please ask the experimenter now."""


# =========================================================================== dataset
def find_images(folder):
    """Return {file stem: path} for all image files in a folder."""
    out = {}
    for f in sorted(os.listdir(folder)):
        stem, ext = os.path.splitext(f)
        if ext.lower() in IMG_EXT and not f.startswith("."):
            out[stem] = os.path.join(folder, f)
    return out


def collect_methods(args):
    """Return {method name: folder}. Methods are given explicitly with --methods,
    or every subfolder of --root is treated as one method."""
    if args.methods:
        dirs = args.methods
    elif args.root:
        ref_abs = os.path.abspath(args.reference) if args.reference else None
        dirs = [os.path.join(args.root, d) for d in sorted(os.listdir(args.root))
                if os.path.isdir(os.path.join(args.root, d)) and not d.startswith(".")
                and d not in (args.exclude or [])
                and os.path.abspath(os.path.join(args.root, d)) != ref_abs]
    else:
        sys.exit("[ERROR] Specify the method folders with --root or --methods")
    methods = {}
    for d in dirs:
        name = os.path.basename(os.path.normpath(d))
        if name in methods:
            sys.exit(f"[ERROR] Duplicate method folder name: {name}")
        methods[name] = d
    if len(methods) < 2:
        sys.exit("[ERROR] At least 2 methods are required")
    return methods


def build_dataset(methods, ref_dir=None):
    """Match images across methods by file name (without extension).
    Returns the list of scenes and a {(method, scene): path} lookup table."""
    maps = {m: find_images(d) for m, d in methods.items()}
    common = set.intersection(*(set(v) for v in maps.values()))
    for m, v in maps.items():
        extra = set(v) - common
        if extra:
            print(f"[WARNING] {len(extra)} image(s) in method '{m}' have no counterpart in the "
                  f"other methods and are ignored: {sorted(extra)[:5]}{' ...' if len(extra) > 5 else ''}")
    ref_map = {}
    if ref_dir:
        ref_map = find_images(ref_dir)
        missing = common - set(ref_map)
        if missing:
            print(f"[WARNING] The reference folder is missing {len(missing)} scene(s); they are "
                  f"excluded: {sorted(missing)[:5]}{' ...' if len(missing) > 5 else ''}")
            common -= missing
    scenes = sorted(common)
    if not scenes:
        sys.exit("[ERROR] The method folders share no common image names")
    paths = {(m, s): maps[m][s] for m in methods for s in scenes}
    for s in scenes:
        if ref_dir:
            paths[("__ref__", s)] = ref_map[s]
    return scenes, paths


# =========================================================================== trials
def build_trials(scenes, methods, repeats=1, n_trials=None, seed=None):
    """Full design = scenes x all method pairs x repeats.
    If n_trials is given, a subset is drawn from the full design while keeping the
    number of trials per method pair as balanced as possible."""
    rng = random.Random(seed)
    pairs = list(itertools.combinations(methods, 2))
    by_pair = {p: [(s, *p) for s in scenes] * repeats for p in pairs}
    for v in by_pair.values():
        rng.shuffle(v)
    full_n = sum(len(v) for v in by_pair.values())
    if n_trials and n_trials > full_n:
        print(f"[NOTE] --n-trials {n_trials} exceeds the full design ({full_n} trials); "
              f"using all trials (increase --repeats if you need more)")
        n_trials = None
    if n_trials:
        # Round-robin over method pairs (in random order each round) until n_trials is reached
        chosen, k = [], 0
        longest = max(len(v) for v in by_pair.values())
        while len(chosen) < n_trials and k < longest:
            order = pairs[:]
            rng.shuffle(order)
            for p in order:
                if len(chosen) < n_trials and k < len(by_pair[p]):
                    chosen.append(by_pair[p][k])
            k += 1
        trials = chosen
    else:
        trials = [t for v in by_pair.values() for t in v]
    rng.shuffle(trials)
    trials = _avoid_same_scene_in_a_row(trials, rng)
    # Randomize left/right position independently on every trial
    return [(s, a, b) if rng.random() < 0.5 else (s, b, a) for s, a, b in trials]


def _avoid_same_scene_in_a_row(trials, rng, tries=2000):
    """Swap trials around so that the same scene rarely appears on consecutive trials."""
    t = trials[:]
    for _ in range(tries):
        bad = [i for i in range(1, len(t)) if t[i][0] == t[i - 1][0]]
        if not bad:
            break
        i = rng.choice(bad)
        j = rng.randrange(len(t))
        t[i], t[j] = t[j], t[i]
    return t


def build_trials_all(scenes, methods, repeats=1, n_trials=None, seed=None):
    """"all" mode design = scenes x repeats; every trial shows every method at once.
    Returns [(scene, (method, ...))], the method tuple being the left-to-right display
    order, reshuffled independently on every trial."""
    rng = random.Random(seed)
    full = scenes * repeats
    rng.shuffle(full)
    full_n = len(full)
    if n_trials and n_trials > full_n:
        print(f"[NOTE] --n-trials {n_trials} exceeds the full design ({full_n} trials); "
              f"using all trials (increase --repeats if you need more)")
        n_trials = None
    if n_trials:
        full = full[:n_trials]
    trials = [(s, tuple(methods)) for s in full]
    trials = _avoid_same_scene_in_a_row(trials, rng)
    return [(s, tuple(rng.sample(ms, len(ms)))) for s, ms in trials]


def make_trials(args, scenes, method_names):
    """Dispatch to the pairwise or "all" trial builder based on --mode."""
    if args.mode == "all":
        return build_trials_all(scenes, method_names, args.repeats, args.n_trials, args.seed)
    return build_trials(scenes, method_names, args.repeats, args.n_trials, args.seed)


# =========================================================================== drawing
class Screen:
    def __init__(self, args):
        _FONT_CACHE.clear()  # fonts from an earlier pygame session are invalid after pygame.quit()
        pygame.init()
        flags = pygame.FULLSCREEN if args.fullscreen else 0
        size = (0, 0) if args.fullscreen else tuple(args.window)
        self.surf = pygame.display.set_mode(size, flags)
        pygame.display.set_caption("Paired Comparison")
        pygame.mouse.set_visible(bool(args.mouse))
        self.W, self.H = self.surf.get_size()
        self.C = (self.W // 2, self.H // 2)
        self.bg = tuple(args.bg)
        self.fg = tuple(args.fg)
        # Low-contrast text color close to the background, used for the adaptation
        # countdown, progress counter, etc., so it does not disturb the observer
        self.dim = tuple(int(b + (f - b) * 0.35) for b, f in zip(self.bg, self.fg))
        base = max(18, self.H // 30)
        self.font = get_font(base)
        self.font_big = get_font(int(base * 1.5))
        self.font_small = get_font(int(base * 0.75))

    def clear(self):
        self.surf.fill(self.bg)

    def flip(self):
        pygame.display.flip()

    def text(self, s, center, font=None, color=None):
        font = font or self.font
        img = font.render(s, True, color or self.fg)
        self.surf.blit(img, img.get_rect(center=center))

    def paragraph(self, text, width_frac=0.75, color=None, align="left", max_h_frac=0.84):
        """Word-wrapped multi-paragraph text, vertically centered. A short first
        paragraph is treated as a title and drawn larger. If the text does not fit,
        the font size is reduced automatically so it is always shown in full."""
        max_w = int(self.W * width_frac)
        max_h = self.H * max_h_frac
        paras = text.strip("\n").split("\n")
        size = max(18, self.H // 30)
        while True:
            body, title = get_font(size), get_font(int(size * 1.5))
            lines = []  # (text, font, is_title)
            for k, para in enumerate(paras):
                is_title = k == 0 and 0 < len(para.strip()) < 30 and len(paras) > 1
                f = title if is_title else body
                if not para.strip():
                    lines.append(("", body, False))
                    continue
                for ln in wrap(para, f, max_w):
                    lines.append((ln, f, is_title))
            total = sum(f.get_linesize() * 1.25 for _, f, _ in lines)
            if total <= max_h or size <= 12:
                break
            size -= 1
        y = self.C[1] - total / 2
        x0 = (self.W - max_w) // 2
        for ln, f, is_title in lines:
            img = f.render(ln, True, color or self.fg)
            if is_title or align == "center":
                self.surf.blit(img, img.get_rect(midtop=(self.C[0], y)))
            else:
                self.surf.blit(img, (x0, y))
            y += f.get_linesize() * 1.25

    def fixation(self, size=12, width=3):
        cx, cy = self.C
        pygame.draw.line(self.surf, self.fg, (cx - size, cy), (cx + size, cy), width)
        pygame.draw.line(self.surf, self.fg, (cx, cy - size), (cx, cy + size), width)


_FONT_CACHE = {}


def get_font(size):
    if size not in _FONT_CACHE:
        _FONT_CACHE[size] = _load_font(size)
    return _FONT_CACHE[size]


def _load_font(size):
    # Prefer fonts with CJK coverage so non-Latin instruction files and folder names
    # render correctly; fall back to pygame's default font otherwise.
    for name in ("microsoftyahei", "notosanscjksc", "notosanscjk", "pingfangsc",
                 "simhei", "heitisc", "wenquanyimicrohei", "sourcehansanscn", "arialunicodems"):
        path = pygame.font.match_font(name)
        if path:
            return pygame.font.Font(path, size)
    return pygame.font.Font(None, size)


def wrap(text, font, max_w):
    """Wrap text to a pixel width. Breaks at spaces for Latin text and between
    characters for CJK text (which has no spaces)."""
    lines, cur = [], ""
    for ch in text:
        if font.size(cur + ch)[0] <= max_w:
            cur += ch
            continue
        cut = cur.rfind(" ")
        if ch != " " and ch.isascii() and cut > 0 and cur[-1:].isascii():
            lines.append(cur[:cut]); cur = cur[cut + 1:] + ch
        else:
            lines.append(cur); cur = ch.lstrip()
    lines.append(cur)
    return lines


def layout_row(scr, imgs, allow_upscale, gap_frac, y0, height):
    """Lay out images side by side within the vertical band [y0, y0+height], with a
    single common scale factor (so their relative sizes are preserved). Returns
    [(surface, rect)] and the scale factor."""
    n = len(imgs)
    gap = int(scr.W * gap_frac)
    avail_w = scr.W - gap * (n + 1)
    w = max(i.get_width() for i in imgs)
    h = max(i.get_height() for i in imgs)
    s = min(avail_w / (n * w), height / h)
    if not allow_upscale:
        s = min(s, 1.0)
    out = []
    sizes = [(round(i.get_width() * s), round(i.get_height() * s)) for i in imgs]
    total = sum(sz[0] for sz in sizes) + gap * (n - 1)
    x = (scr.W - total) // 2
    cy = y0 + height // 2
    for img, sz in zip(imgs, sizes):
        if abs(s - 1.0) > 1e-6:
            img = pygame.transform.smoothscale(img, sz)
        out.append((img, img.get_rect(midleft=(x, cy))))
        x += sz[0] + gap
    return out, s


def layout(scr, imgs, allow_upscale, gap_frac, top_frac=0.12, bottom_frac=0.1):
    """Lay out images side by side in a single row, with a single common scale factor
    (so their relative sizes are preserved). Returns [(surface, rect)] and the scale."""
    y0 = int(scr.H * top_frac)
    height = int(scr.H * (1 - top_frac - bottom_frac))
    return layout_row(scr, imgs, allow_upscale, gap_frac, y0, height)


def layout_two_row(scr, ref_img, cand_imgs, allow_upscale, gap_frac, top_frac=0.12, bottom_frac=0.1,
                    ref_row_frac=0.32, row_gap_frac=0.10):
    """Lay out the reference image centered on its own row, above a second row with
    every candidate side by side (used for --mode all with a reference image). The two
    rows are scaled independently. Returns ((ref_img, ref_rect), [(cand_img, cand_rect),
    ...], scale), where `scale` is the candidates' scale factor (what is being judged)."""
    y0 = int(scr.H * top_frac)
    total_h = int(scr.H * (1 - top_frac - bottom_frac))
    ref_h = int(total_h * ref_row_frac)
    row_gap = int(total_h * row_gap_frac)
    cand_h = total_h - ref_h - row_gap
    [ref_placed], _ = layout_row(scr, [ref_img], allow_upscale, gap_frac, y0, ref_h)
    cand_placed, cand_scale = layout_row(scr, cand_imgs, allow_upscale, gap_frac,
                                          y0 + ref_h + row_gap, cand_h)
    return ref_placed, cand_placed, cand_scale


def trial_slots(trial, mode, use_ref):
    """Turn a trial record into (scene, slots, candidates): `slots` is the ordered list
    of dataset keys to load/display, with "__ref__" at the reference's position if used;
    `candidates` is the choosable methods, in that same left-to-right display order."""
    if mode == "all":
        scene, order = trial
        candidates = list(order)
        if use_ref:
            mid = len(candidates) // 2
            slots = candidates[:mid] + ["__ref__"] + candidates[mid:]
        else:
            slots = candidates
    else:
        scene, mL, mR = trial
        candidates = [mL, mR]
        slots = [mL] + (["__ref__"] if use_ref else []) + [mR]
    return scene, slots, candidates


def slot_labels(mode, slots):
    """Labels aligned to `slots`: pairwise keeps the familiar arrow/key hints; "all"
    mode numbers each candidate by on-screen position (the digit that selects it) and
    never numbers the reference, so it can't be mistaken for a choosable option."""
    if mode == "all":
        labels, n = [], 0
        for k in slots:
            if k == "__ref__":
                labels.append("Reference")
            else:
                n += 1
                labels.append(str(n))
        return labels
    return ["<-  F"] + (["Reference"] if "__ref__" in slots else []) + ["J  ->"]


# =========================================================================== input
class Abort(Exception):
    pass


def poll_quit():
    for ev in pygame.event.get((pygame.QUIT, pygame.KEYDOWN)):
        if ev.type == pygame.QUIT or ev.key == pygame.K_ESCAPE:
            raise Abort


def response_from_event(ev, mode, cand_rects, mouse):
    """Return the 0-based index of the candidate chosen by this event, or None.
    Pairwise: LEFT_KEYS/RIGHT_KEYS, or a click in the first/last candidate rect.
    "all" mode: digit/numpad keys 1..len(cand_rects) by on-screen position, or a click
    in any candidate rect."""
    if ev.type == pygame.KEYDOWN:
        if mode == "all":
            idx = NUM_KEYS.get(ev.key)
            if idx is not None and idx < len(cand_rects):
                return idx
        elif ev.key in LEFT_KEYS + RIGHT_KEYS:
            return 0 if ev.key in LEFT_KEYS else 1
    elif mouse and ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
        for i, r in enumerate(cand_rects):
            if r.collidepoint(ev.pos):
                return i
    return None


def wait_key(keys=None):
    """Block until one of `keys` is pressed (any key if None). ESC aborts."""
    pygame.event.clear()
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                raise Abort
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    raise Abort
                if keys is None or ev.key in keys:
                    return ev.key
        time.sleep(0.002)


def sleep_checking(seconds):
    """Sleep while still reacting to ESC / window close."""
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        poll_quit()
        time.sleep(0.002)


def show_instructions(scr, text):
    scr.clear()
    scr.paragraph(text)
    scr.text("Press SPACE to continue", (scr.C[0], int(scr.H * 0.93)), scr.font_small, scr.dim)
    scr.flip()
    wait_key((pygame.K_SPACE,))


def adaptation(scr, seconds):
    """Light adaptation: show the background color with only a faint countdown.
    It cannot be skipped (ESC still quits the experiment)."""
    if seconds <= 0:
        return
    end = time.perf_counter() + seconds
    last = None
    while True:
        remain = end - time.perf_counter()
        if remain <= 0:
            break
        sec = int(remain) + 1
        if sec != last:
            scr.clear()
            scr.text("Please relax and look at the center of the screen to adapt to the room lighting",
                     (scr.C[0], scr.C[1] - scr.H // 20), scr.font, scr.dim)
            scr.text(f"{sec // 60:d}:{sec % 60:02d}", (scr.C[0], scr.C[1] + scr.H // 30),
                     scr.font_big, scr.dim)
            scr.flip()
            last = sec
        poll_quit()
        time.sleep(0.01)
    scr.clear()
    scr.text("Adaptation complete. Press SPACE when you are ready to start.", scr.C)
    scr.flip()
    wait_key((pygame.K_SPACE,))


# =========================================================================== participant ID
SESSION_INFO_DIR = "session_info"   # per-participant metadata, inside the results folder
AUTO_ID_PREFIX = "P"                # automatic IDs: P001, P002, ...
_WIN_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                 *(f"LPT{i}" for i in range(1, 10))}


def sanitize_id(name):
    """Turn a typed name into a safe file name: drop characters that are invalid in
    file names, replace whitespace with '_', and limit the length. Non-Latin names
    (e.g. Chinese) are kept as they are."""
    s = "".join(ch for ch in (name or "") if ch.isprintable())
    s = re.sub(r'[\\/:*?"<>|]', "", s).strip()
    s = re.sub(r"\s+", "_", s).strip(".")
    if s.upper() in _WIN_RESERVED:
        s += "_"
    return s[:40]


def existing_ids(results_dir):
    """IDs already used in the results folder (lower-case, since file names are
    case-insensitive on Windows and macOS)."""
    if not os.path.isdir(results_dir):
        return set()
    return {os.path.splitext(f)[0].lower() for f in os.listdir(results_dir) if f.lower().endswith(".csv")}


def _candidate_ids(base):
    """Yield IDs to try, in order: base, base_2, base_3, ... or P001, P002, ... if base is empty."""
    if base:
        yield base
        k = 2
        while True:
            yield f"{base}_{k}"
            k += 1
    else:
        k = 1
        while True:
            yield f"{AUTO_ID_PREFIX}{k:03d}"
            k += 1


def reserve_result_file(results_dir, entered):
    """Pick the first unused ID for the typed name and create its result file.
    The file is created in exclusive mode ('x'), so an existing result can never be
    overwritten, even if two sessions start at the same time."""
    taken = existing_ids(results_dir)
    for cand in _candidate_ids(sanitize_id(entered)):
        if cand.lower() in taken:
            continue
        path = os.path.join(results_dir, cand + ".csv")
        try:
            with open(path, "x", encoding="utf-8"):
                pass
            return cand, path
        except FileExistsError:
            taken.add(cand.lower())


def enter_name(scr, max_len=32):
    """On-screen text entry for the participant's name. ENTER confirms (an empty
    entry means an automatic ID will be assigned), ESC quits. Supports IME input,
    so names can be typed in any language."""
    pygame.key.start_text_input()
    text, composing = "", ""
    pygame.event.clear()
    t0 = time.perf_counter()
    box_w, box_h = int(scr.W * 0.4), int(scr.font.get_linesize() * 1.6)
    box = pygame.Rect(0, 0, box_w, box_h)
    box.center = (scr.C[0], scr.C[1] + scr.H // 30)
    try:
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    raise Abort
                if ev.type == pygame.TEXTEDITING:
                    composing = ev.text
                elif ev.type == pygame.TEXTINPUT:
                    text = (text + ev.text)[:max_len]
                    composing = ""
                elif ev.type == pygame.KEYDOWN and not composing:
                    if ev.key == pygame.K_ESCAPE:
                        raise Abort
                    if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        return text.strip()
                    if ev.key == pygame.K_BACKSPACE:
                        text = text[:-1]
            scr.clear()
            scr.text("Participant name", (scr.C[0], scr.C[1] - scr.H // 6), scr.font_big)
            scr.text("Type your name or ID, then press ENTER", (scr.C[0], scr.C[1] - scr.H // 14))
            pygame.draw.rect(scr.surf, scr.fg, box, 2, border_radius=6)
            shown = text + composing
            img = scr.font.render(shown, True, scr.fg)
            pad = box_h // 4
            area = pygame.Rect(max(0, img.get_width() - (box_w - 3 * pad)), 0, box_w - 3 * pad, img.get_height())
            scr.surf.blit(img, (box.x + pad, box.centery - img.get_height() // 2), area)
            if int((time.perf_counter() - t0) * 2) % 2 == 0:  # blinking cursor
                cx = box.x + pad + min(img.get_width(), box_w - 3 * pad) + 2
                pygame.draw.line(scr.surf, scr.fg, (cx, box.centery - box_h // 3), (cx, box.centery + box_h // 3), 2)
            scr.text("Leave empty and press ENTER to be given an automatic ID",
                     (scr.C[0], box.bottom + scr.H // 18), scr.font_small, scr.dim)
            scr.flip()
            time.sleep(0.015)
    finally:
        pygame.key.stop_text_input()


def show_subject_id(scr, subject, entered, renamed):
    """Tell the participant (and experimenter) under which ID the results are saved."""
    if not sanitize_id(entered):
        msg = f"Participant ID\n\nNo name was entered. Your participant ID is:\n\n{subject}"
    elif renamed:
        msg = (f"Participant ID\n\nResults for \"{sanitize_id(entered)}\" already exist, so this "
               f"session will be saved under a new ID:\n\n{subject}")
    else:
        msg = f"Participant ID\n\nYour results will be saved as:\n\n{subject}"
    scr.clear()
    scr.paragraph(msg + "\n\nPress SPACE to continue", align="center")
    scr.flip()
    wait_key((pygame.K_SPACE,))


# =========================================================================== main
def run(args):
    methods = collect_methods(args)
    scenes, paths = build_dataset(methods, args.reference)
    method_names = list(methods)
    if args.mode == "all":
        if any(SHOWN_SEP in m for m in method_names):
            sys.exit(f"[ERROR] Method folder names cannot contain '{SHOWN_SEP}' with --mode all")
        if len(method_names) > MAX_DIGIT_CHOICES and not args.mouse:
            sys.exit(f"[ERROR] --mode all has {len(method_names)} methods, but digit keys only "
                      f"address up to {MAX_DIGIT_CHOICES} positions; add --mouse or use fewer methods")
        if len(method_names) >= 7:
            print(f"[NOTE] {len(method_names)} methods are shown at once in a single row; a smaller "
                  f"--gap or --fullscreen helps keep each image legible")
    trials = make_trials(args, scenes, method_names)
    use_ref = bool(args.reference)

    print(f"Mode: {args.mode}; methods ({len(method_names)}): {method_names}")
    print(f"Scenes: {len(scenes)}; reference: {'yes' if use_ref else 'no'}; trials this session: {len(trials)}")
    if args.mode == "all":
        print(f"  -> {len(trials) * (len(method_names) - 1)} derived pairwise comparisons for analysis")
    if args.dry_run:
        return None

    os.makedirs(args.out_dir, exist_ok=True)
    scr = Screen(args)

    # ---- participant ID: typed on screen unless given with --subject ----
    try:
        entered = args.subject if args.subject is not None else enter_name(scr)
    except Abort:
        pygame.quit()
        print("[NOTE] Experiment aborted before it started; nothing was saved")
        return None
    subject, csv_path = reserve_result_file(args.out_dir, entered)
    renamed = bool(sanitize_id(entered)) and subject != sanitize_id(entered)
    if not sanitize_id(entered):
        print(f"[NOTE] No name entered; assigned ID: {subject}")
    elif renamed:
        print(f"[NOTE] A result for '{sanitize_id(entered)}' already exists; this session is saved as '{subject}'")
    print(f"Participant ID: {subject} -> {csv_path}")

    info_dir = os.path.join(args.out_dir, SESSION_INFO_DIR)
    os.makedirs(info_dir, exist_ok=True)
    info_path = os.path.join(info_dir, f"{subject}.json")
    with open(info_path, "w", encoding="utf-8") as fh:
        json.dump({"subject": subject, "entered_name": entered, "start": datetime.now().isoformat(timespec="seconds"),
                   "methods": methods, "reference": args.reference, "n_scenes": len(scenes),
                   "n_trials": len(trials), "args": vars(args)}, fh, ensure_ascii=False, indent=2)

    instr_text = DEFAULT_INSTRUCTIONS_ALL if args.mode == "all" else DEFAULT_INSTRUCTIONS
    if args.instructions:
        with open(args.instructions, encoding="utf-8") as fh:
            instr_text = fh.read()
    ref_hint_all = " The image in the middle is the original reference; compare every candidate against it."
    ref_hint_pair = " The image in the middle is the original reference; compare both candidates against it."
    fill = defaultdict(str, question=args.question, n_trials=len(trials), n_methods=len(method_names),
                       break_every=args.break_every or len(trials),
                       ref_sentence=", with a reference image in the middle" if use_ref else "",
                       ref_hint=((ref_hint_all if args.mode == "all" else ref_hint_pair) if use_ref else ""),
                       mouse_sentence=" You can also click on an image with the mouse." if args.mouse else "")
    instr_text = instr_text.format_map(fill)

    # The file was already created (exclusively) by reserve_result_file; open it to append
    fh = open(csv_path, "a", newline="", encoding="utf-8")
    wr = csv.writer(fh)
    if args.mode == "all":
        wr.writerow(["subject", "trial", "scene", "shown", "chosen", "position",
                     "rt", "reference", "scale", "timestamp"])
    else:
        wr.writerow(["subject", "trial", "scene", "left", "right", "chosen", "not_chosen",
                     "chosen_side", "rt", "reference", "scale", "timestamp"])
    fh.flush()
    n_done = 0
    warned_scale = False
    try:
        show_subject_id(scr, subject, entered, renamed)
        show_instructions(scr, instr_text)
        adaptation(scr, args.adapt)

        for t, trial in enumerate(trials, 1):
            if args.break_every and t > 1 and (t - 1) % args.break_every == 0:
                scr.clear()
                scr.paragraph(f"Take a short break\n\nCompleted {t-1} / {len(trials)}\n\n"
                              f"Press SPACE when you are ready to continue", align="center")
                scr.flip()
                wait_key((pygame.K_SPACE,))

            scene, slots, candidates = trial_slots(trial, args.mode, use_ref)

            # Fixation; images are loaded during fixation so loading time does not
            # delay stimulus onset
            t0 = time.perf_counter()
            scr.clear(); scr.fixation(); scr.flip()
            imgs = [pygame.image.load(paths[(k, scene)]).convert() for k in slots]
            if args.mode == "all" and use_ref:
                # Reference on its own centered row, candidates side by side in a row below.
                ref_pos = slots.index("__ref__")
                ref_placed, cand_placed, scale = layout_two_row(
                    scr, imgs[ref_pos], imgs[:ref_pos] + imgs[ref_pos + 1:], args.upscale, args.gap)
                placed = cand_placed[:ref_pos] + [ref_placed] + cand_placed[ref_pos:]
            else:
                placed, scale = layout(scr, imgs, args.upscale, args.gap)
            if scale < 0.999 and not warned_scale:
                print(f"[NOTE] Images exceed the available screen area and are shown at {scale:.0%} "
                      f"(keep this in mind for image-quality judgements)")
                warned_scale = True
            sleep_checking(max(0.0, args.fixation - (time.perf_counter() - t0)))

            cand_rects = [r for k, (_, r) in zip(slots, placed) if k != "__ref__"]
            labels = slot_labels(args.mode, slots)

            # Stimulus
            def draw_stim(show_imgs=True):
                scr.clear()
                scr.text(args.question, (scr.C[0], int(scr.H * 0.06)))
                for (img, rect), lab in zip(placed, labels):
                    if show_imgs:
                        scr.surf.blit(img, rect)
                    else:
                        pygame.draw.rect(scr.surf, scr.dim, rect, 1)
                    scr.text(lab, (rect.centerx, rect.bottom + scr.H // 30), scr.font_small, scr.dim)
                if args.show_progress:
                    scr.text(f"{t} / {len(trials)}", (scr.W - scr.W // 20, scr.H - scr.H // 30),
                             scr.font_small, scr.dim)
                scr.flip()

            pygame.event.clear()
            draw_stim()
            onset = time.perf_counter()
            hidden = False
            resp = None
            while resp is None:
                # With a limited --duration, replace the images by empty frames after it elapses
                if args.duration and not hidden and time.perf_counter() - onset >= args.duration:
                    draw_stim(show_imgs=False)
                    hidden = True
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                        raise Abort
                    idx = response_from_event(ev, args.mode, cand_rects, args.mouse)
                    if idx is not None:
                        resp = idx
                if resp is None:
                    time.sleep(0.001)
            rt = time.perf_counter() - onset

            if args.mode == "all":
                chosen = candidates[resp]
                wr.writerow([subject, t, scene, SHOWN_SEP.join(candidates), chosen, resp + 1,
                             f"{rt:.4f}", int(use_ref), f"{scale:.4f}",
                             datetime.now().isoformat(timespec="seconds")])
            else:
                chosen, other = candidates[resp], candidates[1 - resp]
                wr.writerow([subject, t, scene, candidates[0], candidates[1], chosen, other,
                             "left" if resp == 0 else "right", f"{rt:.4f}", int(use_ref),
                             f"{scale:.4f}", datetime.now().isoformat(timespec="seconds")])
            fh.flush()  # write every trial immediately so nothing is lost on abort
            n_done = t

            scr.clear(); scr.flip()
            sleep_checking(args.iti)

        scr.clear()
        scr.paragraph("The experiment is complete\n\nThank you very much for participating!\n\n"
                      "Press any key to exit", align="center")
        scr.flip()
        wait_key()
    except Abort:
        print(f"[NOTE] Experiment aborted after {n_done} / {len(trials)} trials")
    finally:
        fh.close()
        pygame.quit()
    if n_done == 0:
        # Nothing recorded: remove the empty file so the ID is free again and the
        # analysis does not pick up an empty result
        for f in (csv_path, info_path):
            try:
                os.remove(f)
            except OSError:
                pass
        print("[NOTE] No trials were completed; no result file was kept")
        return None
    print(f"Results of '{subject}' saved to: {csv_path}  ({n_done} trials)")
    return csv_path


def build_parser():
    p = argparse.ArgumentParser(description="Multi-method image paired-comparison experiment",
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--config", help="JSON config file; command-line arguments override its values")
    p.add_argument("--subject", help="Participant name/ID; if omitted, it is typed on screen "
                                     "(an empty entry gives an automatic ID such as P001)")
    g = p.add_argument_group("images")
    g.add_argument("--root", help="Root folder; each subfolder is one method")
    g.add_argument("--methods", nargs="+", help="List the method folders directly (instead of --root)")
    g.add_argument("--exclude", nargs="*", help="Subfolder names to skip when using --root")
    g.add_argument("--reference", help="Reference image folder (optional); shown between the two candidates")
    g = p.add_argument_group("trials")
    g.add_argument("--mode", choices=["pairwise", "all"], default="pairwise",
                   help="pairwise: two methods per trial (2AFC). all: every method at once, pick "
                        "one (N-AFC)")
    g.add_argument("--repeats", type=int, default=1,
                   help="Number of repeats of the full design (scenes x method pairs for "
                        "--mode pairwise; scenes only for --mode all)")
    g.add_argument("--n-trials", type=int,
                   help="Draw only this many trials (balanced across method pairs for --mode "
                        "pairwise; sampled scenes for --mode all)")
    g.add_argument("--seed", type=int, help="Random seed")
    g = p.add_argument_group("procedure")
    g.add_argument("--question", default="Which image has better quality?",
                   help="Task instruction shown at the top of the screen")
    g.add_argument("--instructions",
                   help="Instructions text file (UTF-8); may use the placeholders {question} {n_trials} "
                        "{break_every} {ref_sentence} {ref_hint} {mouse_sentence} {n_methods}")
    g.add_argument("--adapt", type=float, default=60, help="Light adaptation duration in seconds, 0 = none")
    g.add_argument("--fixation", type=float, default=0.5, help="Fixation duration (s)")
    g.add_argument("--duration", type=float, default=0, help="Image presentation time (s), 0 = until response")
    g.add_argument("--iti", type=float, default=0.3, help="Inter-trial interval (s)")
    g.add_argument("--break-every", type=int, default=50, help="Break every N trials, 0 = no breaks")
    g.add_argument("--show-progress", action="store_true", help="Show a progress counter in the corner")
    g.add_argument("--mouse", action="store_true", help="Allow responding by clicking on an image")
    g = p.add_argument_group("display")
    g.add_argument("--fullscreen", action="store_true")
    g.add_argument("--window", type=int, nargs=2, default=[1600, 900], metavar=("W", "H"))
    g.add_argument("--bg", type=int, nargs=3, default=[128, 128, 128], help="Background color RGB")
    g.add_argument("--fg", type=int, nargs=3, default=[230, 230, 230], help="Text color RGB")
    g.add_argument("--gap", type=float, default=0.02, help="Gap between images (fraction of screen width)")
    g.add_argument("--upscale", action="store_true",
                   help="Allow enlarging images to fill the screen (by default images are only "
                        "shrunk when they do not fit, to avoid interpolation affecting quality)")
    p.add_argument("--out-dir", default="results",
                   help="Results folder (created automatically); one CSV per participant")
    p.add_argument("--dry-run", action="store_true", help="Only check the folders and count trials; do not run")
    return p


def parse_args(argv=None):
    p = build_parser()
    pre, _ = p.parse_known_args(argv)
    if pre.config:
        with open(pre.config, encoding="utf-8") as fh:
            # keys starting with "_" are comments; '-' and '_' are interchangeable in key names
            cfg = {k.replace("-", "_"): v for k, v in json.load(fh).items() if not k.startswith("_")}
        known = {a.dest for a in p._actions}
        unknown = sorted(set(cfg) - known)
        if unknown:
            print(f"[WARNING] Unknown keys in {pre.config} are ignored (typo?): {unknown}")
        p.set_defaults(**{k: v for k, v in cfg.items() if k in known})
    return p.parse_args(argv)


if __name__ == "__main__":
    run(parse_args())
