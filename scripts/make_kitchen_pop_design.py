#!/usr/bin/env python3
"""Generate a Klydo-inspired flat abstract sample design.

Produces designs/kitchen-pop/:
  - loop.mp4       480x480 H.264, seamless-ish abstract blob loop
  - pendulum.png   simple matching yellow/teal pendulum sprite
  - theme.json     no dial markings, minimal dark hands, hidden second hand
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

TARGET = 480
FPS = 15
DURATION = 6
SCALE = 3

TEAL = "#00857a"
DEEP_TEAL = "#063d3a"
ORANGE = "#ff8200"
YELLOW = "#ffb70f"
CREAM = "#f4d88f"


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def make_theme(folder: str) -> None:
    theme = {
        "name": "Kitchen Pop",
        "accent": YELLOW,
        "background": "#050505",
        "hands": {
            "hour": {
                "color": DEEP_TEAL,
                "width": 11,
                "length": 0.42,
                "glow": False,
                "shape": "rounded",
            },
            "minute": {
                "color": DEEP_TEAL,
                "width": 9,
                "length": 0.66,
                "glow": False,
                "shape": "rounded",
            },
            "second": {
                "color": YELLOW,
                "width": 2,
                "length": 0.85,
                "glow": False,
                "visible": False,
            },
        },
        "dial": {"markings": "none", "color": "#ffffff", "count": 12},
        "pendulum": {
            "period_s": 1.6,
            "amplitude_deg": 9,
            "pivot": [0.5, 0.035],
            "rod_length": 0.74,
        },
        "ambiance": {"day_night": False, "twinkle": False, "glow": False},
    }
    with open(os.path.join(folder, "theme.json"), "w", encoding="utf-8") as f:
        json.dump(theme, f, indent=2)
        f.write("\n")


def blob_points(cx: float, cy: float, rx: float, ry: float, phase: float,
                wobble: float = 0.18, count: int = 96) -> list[tuple[float, float]]:
    points = []
    for i in range(count):
        a = i / count * math.tau
        r = 1.0 + wobble * math.sin(a * 3.0 + phase) + wobble * 0.55 * math.cos(a * 5.0 - phase)
        points.append((cx + math.cos(a) * rx * r, cy + math.sin(a) * ry * r))
    return points


def draw_artwork(phase: float):
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        print("Pillow is required to generate this design.", file=sys.stderr)
        raise

    size = TARGET * SCALE
    img = Image.new("RGB", (size, size), hex_rgb(TEAL))
    d = ImageDraw.Draw(img)

    def spt(points):
        return [(x * SCALE, y * SCALE) for x, y in points]

    # Big, cropped blobs. The composition is intentionally off-centre like the
    # reference: the hands sit over artwork, not over a formal dial.
    blobs = [
        (ORANGE, 72, 82, 78, 58, phase + 0.2),
        (YELLOW, 156, 331, 98, 64, phase + 1.0),
        (ORANGE, 339, 66, 74, 60, phase + 2.4),
        (CREAM, 360, 292, 88, 46, phase + 3.1),
        (ORANGE, 40, 298, 82, 108, phase + 4.0),
        (CREAM, 250, 158, 38, 58, phase + 0.8),
        (YELLOW, 273, 292, 86, 82, phase + 2.1),
        (CREAM, 470, 406, 70, 52, phase + 4.7),
    ]
    for color, cx, cy, rx, ry, ph in blobs:
        # Small drift keeps the loop alive without becoming visually noisy.
        drift_x = math.sin(phase * 0.7 + ph) * 6
        drift_y = math.cos(phase * 0.6 + ph) * 5
        pts = blob_points(cx + drift_x, cy + drift_y, rx, ry, ph)
        d.polygon(spt(pts), fill=color)

    # Subtle inner vignette so the black fixture ring reads cleanly.
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for i in range(42):
        alpha = int(i * 1.1)
        od.ellipse((i * SCALE, i * SCALE, size - i * SCALE, size - i * SCALE),
                   outline=(0, 0, 0, alpha), width=SCALE)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    img = img.filter(ImageFilter.SMOOTH_MORE)
    return img.resize((TARGET, TARGET), Image.Resampling.LANCZOS)


def make_loop(folder: str) -> bool:
    try:
        import av
        import numpy as np
    except ImportError:
        print("PyAV and numpy are required to generate loop.mp4.", file=sys.stderr)
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


def make_pendulum(folder: str) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Pillow not installed; skipping pendulum.png.", file=sys.stderr)
        return

    w, h = 300, 400
    cx = w // 2
    rod_bottom = 246
    bob_r = 76
    bob_cy = 284
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(cx, 0), (cx, rod_bottom)], fill=hex_rgb(YELLOW) + (255,), width=8)
    d.ellipse([cx - bob_r - 12, bob_cy - bob_r - 12,
               cx + bob_r + 12, bob_cy + bob_r + 12], fill=hex_rgb(TEAL) + (255,))
    d.ellipse([cx - bob_r, bob_cy - bob_r, cx + bob_r, bob_cy + bob_r],
              fill=hex_rgb(YELLOW) + (255,))
    d.ellipse([cx - bob_r, bob_cy - bob_r, cx + bob_r, bob_cy + bob_r],
              outline=hex_rgb(DEEP_TEAL) + (255,), width=4)
    img.save(os.path.join(folder, "pendulum.png"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=os.path.join("designs", "kitchen-pop"))
    args = parser.parse_args()
    os.makedirs(args.dir, exist_ok=True)
    make_theme(args.dir)
    make_pendulum(args.dir)
    ok = make_loop(args.dir)
    print("Kitchen Pop design written to %s (loop.mp4: %s)" %
          (args.dir, "yes" if ok else "no"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
