#!/usr/bin/env python3
"""Author the "night" design -- a faithful native recreation of the legacy look:
a deep-navy radial-gradient dial with a soft glowing moon and an in-dial star field,
plus a glowing cream pendulum bob.

The renderer draws the numerals, tapered hands and gold second hand on top; this
script only bakes the background loop + the pendulum sprite + theme.json.

Usage:  python scripts/make_night_design.py [--dir designs/night]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys

TARGET = 480
DURATION = 5
FPS = 12

# Palette (matches the legacy night dial).
CENTER = (34, 74, 116)
EDGE = (9, 22, 44)
MOON = (247, 242, 224)
MOON_XY = (0.42, 0.30)   # fraction of the frame (upper-left, inside the dial)


def _theme(folder: str) -> None:
    theme = {
        "name": "Night",
        "accent": "#d9a24a",
        "background": "#050914",
        "hands": {
            "hour":   {"color": "#f4efe1", "width": 14, "length": 0.50, "glow": True},
            "minute": {"color": "#f4efe1", "width": 9,  "length": 0.82, "glow": True},
            "second": {"color": "#d9a24a", "width": 3,  "length": 0.90, "glow": True},
        },
        "dial": {"markings": "numerals", "color": "#f6f2e8", "count": 12},
        "pendulum": {"period_s": 1.15, "amplitude_deg": 11,
                     "pivot": [0.5, 0.04], "rod_length": 0.9},
        # day_night off: the dial IS the night scene, and the surround stays black.
        "ambiance": {"day_night": False, "twinkle": False, "glow": True},
    }
    with open(os.path.join(folder, "theme.json"), "w", encoding="utf-8") as f:
        json.dump(theme, f, indent=2)


def _pendulum(folder: str) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        print("Pillow missing; skipping pendulum.png (procedural fallback used).",
              file=sys.stderr)
        return
    rod_len, bob_r, glow_r, pad = 200, 56, 42, 30
    halo = bob_r + glow_r
    w = 2 * (halo + pad)
    cx = w // 2
    by = rod_len + bob_r                 # bob centre
    h = by + halo + pad                  # room for the halo below the bob
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # Soft glow halo, blurred well inside the padded border so it fades to fully
    # transparent (no square edge when composited).
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([cx - halo, by - halo, cx + halo, by + halo], fill=(247, 242, 224, 150))
    glow = glow.filter(ImageFilter.GaussianBlur(20))
    img = Image.alpha_composite(img, glow)

    d = ImageDraw.Draw(img)
    d.line([(cx, 6), (cx, rod_len)], fill=(200, 205, 215, 255), width=4)
    d.ellipse([cx - bob_r, by - bob_r, cx + bob_r, by + bob_r], fill=(247, 242, 224, 255))
    d.ellipse([cx - int(bob_r * 0.6), by - int(bob_r * 0.7),
               cx + int(bob_r * 0.15), by - int(bob_r * 0.05)], fill=(255, 255, 250, 150))
    img.save(os.path.join(folder, "pendulum.png"))


def _frames():
    import numpy as np

    n = DURATION * FPS
    yy, xx = np.mgrid[0:TARGET, 0:TARGET].astype("float32")
    cx = cy = TARGET / 2.0
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    g = np.clip(1.0 - r / (TARGET * 0.60), 0.0, 1.0) ** 1.3  # bright centre, dark rim
    base = np.stack([
        EDGE[0] + (CENTER[0] - EDGE[0]) * g,
        EDGE[1] + (CENTER[1] - EDGE[1]) * g,
        EDGE[2] + (CENTER[2] - EDGE[2]) * g,
    ], axis=-1)

    # Moon glow field.
    mx, my = MOON_XY[0] * TARGET, MOON_XY[1] * TARGET
    md = np.sqrt((xx - mx) ** 2 + (yy - my) ** 2)
    moon_core = np.clip(1.0 - md / 34.0, 0.0, 1.0)
    moon_glow = np.exp(-(md ** 2) / (2 * 46.0 ** 2))

    # Fixed star field inside the dial.
    rng = random.Random(11)
    stars = []
    for _ in range(70):
        sx, sy = rng.randint(0, TARGET - 1), rng.randint(0, TARGET - 1)
        if math.hypot(sx - cx, sy - cy) < TARGET * 0.46:
            stars.append((sx, sy, rng.uniform(0.3, 1.0), rng.uniform(0, 6.28)))

    for i in range(n):
        ph = i / n * 2 * math.pi
        pulse = 0.85 + 0.15 * math.sin(ph)  # gentle moon breathing
        frame = base.copy()
        for c in range(3):
            frame[..., c] += moon_glow * (MOON[c] * 0.55 * pulse)
            frame[..., c] = frame[..., c] * (1 - moon_core) + MOON[c] * moon_core
        arr = np.clip(frame, 0, 255)
        for sx, sy, br, phase in stars:
            tw = 0.5 + 0.5 * math.sin(ph * 1.5 + phase)
            arr[sy, sx] = np.clip(arr[sy, sx] + 210 * br * tw, 0, 255)
        yield arr.astype("uint8")


def _loop(folder: str) -> bool:
    out = os.path.join(folder, "loop.mp4")
    try:
        import av
    except ImportError:
        print("PyAV missing; skipping loop.mp4 (flat accent disc fallback).",
              file=sys.stderr)
        return False
    try:
        container = av.open(out, mode="w")
        stream = container.add_stream("libx264", rate=FPS)
        stream.width = TARGET
        stream.height = TARGET
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": "18", "preset": "medium"}
        for arr in _frames():
            frame = av.VideoFrame.from_ndarray(arr, format="rgb24")
            for pkt in stream.encode(frame):
                container.mux(pkt)
        for pkt in stream.encode():
            container.mux(pkt)
        container.close()
        return True
    except Exception as e:  # pragma: no cover
        print("PyAV encode failed: %s" % e, file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join("designs", "night"))
    args = ap.parse_args()
    os.makedirs(args.dir, exist_ok=True)
    _theme(args.dir)
    _pendulum(args.dir)
    ok = _loop(args.dir)
    print("Night design written to %s (loop.mp4: %s)" % (args.dir, "yes" if ok else "no"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
