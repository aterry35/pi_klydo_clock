#!/usr/bin/env python3
"""Generate the "Vintage Film" design: monochrome old-cartoon look.

Reference: a black-and-white cartoon loop behind white baton hands, and a
pendulum that is a dark disc with a silver ring on a light rod.

The generated loop.mp4 is a public-domain-safe procedural cartoon scene with
film grain, gate flicker, scratches, deck lines, and a ship wheel. If you want
real archival footage instead, replace it with a public-domain clip:

    ffmpeg -i source.mp4 -ss 00:01:00 -t 6 \
      -vf "crop=ih:ih,scale=480:480,fps=15,eq=saturation=0" \
      -an -c:v libx264 -crf 18 -pix_fmt yuv420p designs/vintage-film/loop.mp4

Keep it 4-8 s and near-seamless (pick a shot with little camera motion).

Produces designs/vintage-film/:
  - loop.mp4       480x480 procedural old-cartoon ship-wheel loop
  - pendulum.png   dark bob with silver ring, light rod
  - theme.json     white rounded hands, no dial markings, plain lower cutout
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys

TARGET = 480
FPS = 15
DURATION = 6

WHITE = "#f5f5f0"
SILVER = "#c9c9c3"
DARK = "#0a0a0a"
RING_DARK = "#43433f"


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def make_theme(folder: str) -> None:
    theme = {
        "name": "Vintage Film",
        "accent": WHITE,
        "background": "#151513",
        "hands": {
            "hour": {"color": WHITE, "width": 10, "length": 0.42,
                     "glow": False, "shape": "rounded"},
            "minute": {"color": WHITE, "width": 7, "length": 0.66,
                       "glow": False, "shape": "rounded"},
            "second": {"color": WHITE, "width": 2, "length": 0.82,
                       "glow": False, "visible": False},
        },
        "dial": {"markings": "none", "color": "#ffffff", "count": 12},
        "pendulum": {
            "period_s": 1.6,
            "amplitude_deg": 9,
            "pivot": [0.5, 0.035],
            "rod_length": 0.74,
        },
        "bottom": {"backdrop": "solid", "color": "#000000"},
        "ambiance": {"day_night": False, "twinkle": False, "glow": False},
    }
    with open(os.path.join(folder, "theme.json"), "w", encoding="utf-8") as f:
        json.dump(theme, f, indent=2)
        f.write("\n")


def draw_cartoon_frame(phase: float):
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        print("Pillow is required to generate loop.mp4.", file=sys.stderr)
        raise

    scale = 2
    size = TARGET * scale
    img = Image.new("RGB", (size, size), (166, 166, 166))
    d = ImageDraw.Draw(img)

    def xy(value: float) -> int:
        return int(round(value * scale))

    def pt(x: float, y: float) -> tuple[int, int]:
        return (xy(x), xy(y))

    def line(points, fill=(28, 28, 28), width=3):
        d.line([pt(x, y) for x, y in points], fill=fill, width=xy(width),
               joint="curve")

    # Soft sky/wall and deck, with thick ink lines like early animation cells.
    d.rectangle([0, 0, size, xy(198)], fill=(174, 174, 174))
    d.polygon([pt(0, 206), pt(480, 175), pt(480, 480), pt(0, 480)],
              fill=(137, 137, 137))
    line([(0, 206), (480, 175)], width=4)
    line([(0, 318), (480, 260)], fill=(62, 62, 62), width=2)
    for x in (-95, -20, 58, 136, 214, 292, 370):
        line([(x, 480), (x + 160, 190)], fill=(74, 74, 74), width=2)

    # Distant porthole/window framing and wires add the same dense film-cell feel
    # as the reference without relying on a copyrighted character.
    d.rectangle([xy(36), xy(92), xy(234), xy(196)], outline=(42, 42, 42),
                width=xy(4))
    line([(36, 146), (234, 146)], fill=(76, 76, 76), width=2)
    line([(36, 92), (0, 124)], fill=(54, 54, 54), width=3)
    line([(234, 92), (292, 130)], fill=(54, 54, 54), width=3)
    for off in (0, 28, 56):
        line([(270 + off, 0), (318 + off + 10 * math.sin(phase), 118)],
             fill=(24, 24, 24), width=3)

    # Abstract hills/clouds through the window.
    for i, y in enumerate((128, 148, 166)):
        points = []
        for x in range(42, 230, 18):
            points.append(pt(x, y + 8 * math.sin(x * 0.045 + i + phase)))
        d.line(points, fill=(102, 102, 102), width=xy(3))

    # Large ship wheel, slightly rocking so the loop has real motion.
    cx, cy = 153, 258
    outer_r = 92
    inner_r = 56
    wheel_rot = math.sin(phase) * math.radians(7.0)
    d.ellipse([xy(cx - outer_r), xy(cy - outer_r),
               xy(cx + outer_r), xy(cy + outer_r)],
              fill=(150, 150, 150), outline=(20, 20, 20), width=xy(6))
    d.ellipse([xy(cx - inner_r), xy(cy - inner_r),
               xy(cx + inner_r), xy(cy + inner_r)],
              outline=(32, 32, 32), width=xy(5))
    for i in range(8):
        a = i * math.tau / 8 + wheel_rot
        sx = cx + math.cos(a) * 18
        sy = cy + math.sin(a) * 18
        ex = cx + math.cos(a) * (outer_r + 20)
        ey = cy + math.sin(a) * (outer_r + 20)
        line([(sx, sy), (ex, ey)], width=8)
        hx = cx + math.cos(a) * (outer_r + 24)
        hy = cy + math.sin(a) * (outer_r + 24)
        d.ellipse([xy(hx - 11), xy(hy - 11), xy(hx + 11), xy(hy + 11)],
                  fill=(162, 162, 162), outline=(24, 24, 24), width=xy(3))
    d.ellipse([xy(cx - 26), xy(cy - 26), xy(cx + 26), xy(cy + 26)],
              fill=(32, 32, 32))

    # Simple stylized white glove/arm silhouette in the spirit of the reference,
    # but generic enough to remain original artwork.
    arm_phase = math.sin(phase) * 4
    line([(cx + 15, cy + 10), (282, 258 + arm_phase), (336, 230 + arm_phase)],
         fill=(18, 18, 18), width=13)
    d.ellipse([xy(318), xy(206 + arm_phase), xy(377), xy(256 + arm_phase)],
              fill=(228, 228, 228), outline=(18, 18, 18), width=xy(4))
    for fx in (330, 348, 365):
        line([(fx, 214 + arm_phase), (fx + 16, 194 + arm_phase)],
             fill=(18, 18, 18), width=3)

    # Cell softness before film damage is added.
    img = img.filter(ImageFilter.SMOOTH_MORE)
    return img.resize((TARGET, TARGET), Image.Resampling.LANCZOS)


def make_loop(folder: str) -> bool:
    """Old-cartoon loop: procedural line art + per-frame grain/flicker/scratches."""
    try:
        import av
        import numpy as np
        from PIL import Image  # noqa: F401 - draw_cartoon_frame requires Pillow.
    except ImportError:
        print("PyAV, numpy, and Pillow are required to generate loop.mp4.",
              file=sys.stderr)
        return False

    rng = np.random.default_rng(1928)
    size = TARGET

    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cx, cy = size * 0.46, size * 0.40
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / (size * 0.72)
    vignette = 1.0 - 0.34 * np.clip(dist, 0, 1) ** 1.7

    out = os.path.join(folder, "loop.mp4")
    frames = FPS * DURATION
    container = av.open(out, mode="w")
    stream = container.add_stream("libx264", rate=FPS)
    stream.width = size
    stream.height = size
    stream.pix_fmt = "yuv420p"
    stream.options = {"crf": "18", "preset": "medium"}

    random.seed(1928)
    scratch_frames = {random.randrange(frames): random.randrange(40, size - 40)
                      for _ in range(6)}

    for i in range(frames):
        phase = i / frames * math.tau
        base = np.asarray(draw_cartoon_frame(phase)).astype(np.float32)[:, :, 0]
        flicker = 1.0 + 0.05 * math.sin(phase * 3) + rng.normal(0, 0.015)
        frame_f = base * vignette * flicker
        # Film grain.
        frame_f = frame_f + rng.normal(0, 9, (size, size)).astype(np.float32)
        # Occasional vertical scratch, held for two frames.
        for sf, sx in scratch_frames.items():
            if sf <= i <= sf + 1:
                frame_f[:, sx:sx + 1] += 70
        gray = np.clip(frame_f, 0, 255).astype(np.uint8)
        arr = np.stack([gray, gray, gray], axis=-1)
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
    bob_r = 84
    bob_cy = 288
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Light rod.
    d.line([(cx, 0), (cx, bob_cy - bob_r + 10)],
           fill=hex_rgb(WHITE) + (255,), width=10)
    # Silver ring, thin dark separation, dark bob.
    d.ellipse([cx - bob_r - 14, bob_cy - bob_r - 14,
               cx + bob_r + 14, bob_cy + bob_r + 14],
              fill=hex_rgb(SILVER) + (255,))
    d.ellipse([cx - bob_r - 4, bob_cy - bob_r - 4,
               cx + bob_r + 4, bob_cy + bob_r + 4],
              fill=hex_rgb(RING_DARK) + (255,))
    d.ellipse([cx - bob_r, bob_cy - bob_r, cx + bob_r, bob_cy + bob_r],
              fill=hex_rgb(DARK) + (255,))
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
    parser.add_argument("--dir", default=os.path.join("designs", "vintage-film"))
    args = parser.parse_args()
    os.makedirs(args.dir, exist_ok=True)
    make_theme(args.dir)
    pendulum_ok = make_pendulum(args.dir)
    loop_ok = make_loop(args.dir)
    missing = required_outputs_missing(args.dir)
    ok = pendulum_ok and loop_ok and not missing
    print("Vintage Film design written to %s (loop.mp4: %s)" %
          (args.dir, "yes" if loop_ok else "no"))
    print("NOTE: loop.mp4 is procedural original artwork; you can still drop "
          "in real public-domain b/w footage if desired.")
    if not ok:
        if missing:
            print("ERROR: incomplete design; missing %s." %
                  ", ".join(missing), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
