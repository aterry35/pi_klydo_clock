#!/usr/bin/env python3
"""Generate the "Paper Bloom" design: layered paper-cut mandala (Klydo-style).

Reference: concentric torn-paper scallop rings in red/teal/cream, red baton
hands, and a white pendulum disc with an offset red circle.

Produces designs/paper-bloom/:
  - loop.mp4       480x480 H.264, slow breathing/rotating paper layers
  - pendulum.png   white paper disc with offset red disc, teal rod
  - theme.json     red rounded hands, no dial markings, plain lower cutout
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

TARGET = 480
FPS = 15
DURATION = 8
SCALE = 2

RED = "#e8492a"
SALMON = "#ef9a80"
CREAM = "#f1e6d0"
WHITE = "#faf6ee"
TEAL = "#2e8f7f"
DEEP_TEAL = "#14675a"
MINT = "#a5d3bf"
NAVY = "#1c3a4b"

# (color, radius fraction of half-size, wobble amplitude, scallop count,
#  phase offset, sway direction)
LAYERS = [
    (CREAM, 1.22, 0.045, 18, 0.6, 1),
    (RED, 1.05, 0.050, 18, 2.1, 1),
    (SALMON, 0.94, 0.050, 16, 4.0, 1),
    (WHITE, 0.84, 0.052, 16, 1.2, 1),
    (TEAL, 0.74, 0.055, 15, 3.3, -1),
    (MINT, 0.64, 0.055, 14, 0.9, -1),
    (NAVY, 0.53, 0.060, 13, 5.1, -1),
    (DEEP_TEAL, 0.43, 0.062, 12, 2.6, 1),
    (RED, 0.30, 0.080, 11, 0.4, 1),
    (WHITE, 0.20, 0.100, 10, 3.8, 1),
    (RED, 0.105, 0.120, 9, 1.5, 1),
]


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def make_theme(folder: str) -> None:
    theme = {
        "name": "Paper Bloom",
        "accent": RED,
        "background": "#0d0d0d",
        "hands": {
            "hour": {"color": RED, "width": 12, "length": 0.40,
                     "glow": False, "shape": "rounded"},
            "minute": {"color": RED, "width": 9, "length": 0.62,
                       "glow": False, "shape": "rounded"},
            "second": {"color": WHITE, "width": 2, "length": 0.80,
                       "glow": False, "visible": False},
        },
        "dial": {"markings": "none", "color": "#ffffff", "count": 12},
        "pendulum": {
            "period_s": 1.7,
            "amplitude_deg": 8,
            "pivot": [0.5, 0.035],
            "rod_length": 0.74,
        },
        "bottom": {"backdrop": "solid", "color": "#000000"},
        "ambiance": {"day_night": False, "twinkle": False, "glow": False},
    }
    with open(os.path.join(folder, "theme.json"), "w", encoding="utf-8") as f:
        json.dump(theme, f, indent=2)
        f.write("\n")


def wavy_points(cx: float, cy: float, radius: float, wobble: float,
                scallops: int, phi: float, phase: float, sway: float,
                count: int = 260) -> list[tuple[float, float]]:
    """Torn-paper scallop ring. `phase` runs 0..tau over the loop so the wobble
    pattern drifts seamlessly; `sway` adds a tiny loop-safe rotation."""
    points = []
    rot = math.sin(phase) * math.radians(2.0) * sway
    for i in range(count):
        a = i / count * math.tau + rot
        r = radius * (1.0
                      + wobble * math.sin(scallops * a + phi + phase)
                      + wobble * 0.38 * math.sin((scallops + 5) * a - phi * 1.7))
        points.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return points


def draw_artwork(phase: float):
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        print("Pillow is required to generate this design.", file=sys.stderr)
        raise

    size = TARGET * SCALE
    half = size / 2
    img = Image.new("RGB", (size, size), hex_rgb(NAVY))
    d = ImageDraw.Draw(img)

    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)

    for color, rf, wobble, scallops, phi, sway in LAYERS:
        pts = wavy_points(half, half, rf * half, wobble, scallops,
                          phi, phase, sway)
        # Soft drop shadow first, offset down, for the paper-cut depth.
        sd.polygon([(x, y + 6 * SCALE) for x, y in pts], fill=(8, 18, 24, 90))
        shadow_blur = shadow.filter(ImageFilter.GaussianBlur(4 * SCALE))
        img = Image.alpha_composite(img.convert("RGBA"), shadow_blur).convert("RGB")
        shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        d = ImageDraw.Draw(img)
        d.polygon(pts, fill=color)

    return img.resize((TARGET, TARGET), Image.Resampling.LANCZOS)


def make_loop(folder: str) -> bool:
    try:
        import av
        import numpy as np
        from PIL import Image  # noqa: F401 - draw_artwork requires Pillow.
    except ImportError:
        print("PyAV, numpy, and Pillow are required to generate loop.mp4.",
              file=sys.stderr)
        return False

    out = os.path.join(folder, "loop.mp4")
    frames = FPS * DURATION
    container = av.open(out, mode="w")
    stream = container.add_stream("libx264", rate=FPS)
    stream.width = TARGET
    stream.height = TARGET
    stream.pix_fmt = "yuv420p"
    stream.options = {"crf": "18", "preset": "medium"}
    for i in range(frames):
        phase = i / frames * math.tau
        arr = np.asarray(draw_artwork(phase))
        frame = av.VideoFrame.from_ndarray(arr, format="rgb24")
        for packet in stream.encode(frame):
            container.mux(packet)
    for packet in stream.encode():
        container.mux(packet)
    container.close()
    return True


def make_pendulum(folder: str) -> bool:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Pillow not installed; skipping pendulum.png.", file=sys.stderr)
        return False

    w, h = 300, 400
    cx = w // 2
    disc_r = 92
    disc_cy = 280
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Teal rod down to the disc.
    d.line([(cx, 0), (cx, disc_cy - disc_r + 16)],
           fill=hex_rgb(TEAL) + (255,), width=8)
    # White paper disc.
    d.ellipse([cx - disc_r, disc_cy - disc_r, cx + disc_r, disc_cy + disc_r],
              fill=hex_rgb(WHITE) + (255,))
    # Offset red disc, like a paper cut-out laid on top.
    red_r = 68
    red_cx = cx + 26
    d.ellipse([red_cx - red_r, disc_cy - red_r, red_cx + red_r, disc_cy + red_r],
              fill=hex_rgb(RED) + (255,))
    img.save(os.path.join(folder, "pendulum.png"))
    return True


def required_outputs_missing(folder: str) -> list[str]:
    missing = []
    for name in ("theme.json", "pendulum.png", "loop.mp4"):
        path = os.path.join(folder, name)
        if not os.path.isfile(path) or os.path.getsize(path) <= 0:
            missing.append(name)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=os.path.join("designs", "paper-bloom"))
    args = parser.parse_args()
    os.makedirs(args.dir, exist_ok=True)
    make_theme(args.dir)
    pendulum_ok = make_pendulum(args.dir)
    loop_ok = make_loop(args.dir)
    missing = required_outputs_missing(args.dir)
    ok = pendulum_ok and loop_ok and not missing
    print("Paper Bloom design written to %s (loop.mp4: %s)" %
          (args.dir, "yes" if loop_ok else "no"))
    if not ok:
        if missing:
            print("ERROR: incomplete design; missing %s." %
                  ", ".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
