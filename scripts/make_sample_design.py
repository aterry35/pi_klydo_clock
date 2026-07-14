#!/usr/bin/env python3
"""Generate a self-contained sample design so the pipeline is verifiable without
any of the user's real assets.

Produces examples/testcard/:
  - loop.mp4       480x480 H.264, ~6s, an animated test pattern (needs ffmpeg)
  - pendulum.png   themed rod+bob sprite (Pillow)
  - theme.json     drives hands, dial, pendulum physics, and live ambiance

The theme deliberately turns on day_night + twinkle and a swinging pendulum so the
rich, real-time layers are demonstrated, not just the video.

Usage:  python scripts/make_sample_design.py [--dir examples/testcard]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

TARGET = 480
DURATION = 6
FPS = 15


def make_theme(folder: str) -> None:
    theme = {
        "name": "Test Card",
        "accent": "#d9a24a",
        "background": "#050505",
        "hands": {
            "hour":   {"color": "#f0c070", "width": 12, "length": 0.52, "glow": True},
            "minute": {"color": "#f7e1d3", "width": 7,  "length": 0.78, "glow": True},
            "second": {"color": "#e0564a", "width": 3,  "length": 0.90, "glow": True},
        },
        "dial": {"markings": "ticks", "color": "#ffffff", "count": 12},
        "pendulum": {"period_s": 2.0, "amplitude_deg": 13, "pivot": [0.5, 0.05],
                     "rod_length": 0.82},
        "ambiance": {"day_night": True, "twinkle": True, "glow": True},
    }
    with open(os.path.join(folder, "theme.json"), "w", encoding="utf-8") as f:
        json.dump(theme, f, indent=2)


def make_pendulum(folder: str) -> None:
    """Draw a themed rod+bob sprite with the pivot at the top-centre."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Pillow not installed; skipping pendulum.png (renderer will draw a "
              "procedural fallback).", file=sys.stderr)
        return
    rod_len, bob_r = 250, 60
    w, h = bob_r * 2 + 16, rod_len + bob_r * 2 + 16
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = w // 2
    # Rod (pivot at top-centre = (cx, 4)).
    d.line([(cx, 4), (cx, rod_len)], fill=(210, 210, 220, 255), width=5)
    # Bob: accent ring, warm centre, highlight.
    by = rod_len + bob_r
    d.ellipse([cx - bob_r, by - bob_r, cx + bob_r, by + bob_r], fill=(217, 162, 74, 255))
    d.ellipse([cx - int(bob_r * 0.72), by - int(bob_r * 0.72),
               cx + int(bob_r * 0.72), by + int(bob_r * 0.72)], fill=(245, 240, 220, 255))
    d.ellipse([cx - bob_r, by - bob_r, cx + bob_r, by + bob_r],
              outline=(180, 130, 50, 255), width=4)
    d.ellipse([cx - int(bob_r * 0.4), by - int(bob_r * 0.5),
               cx - int(bob_r * 0.05), by - int(bob_r * 0.15)], fill=(255, 255, 250, 180))
    img.save(os.path.join(folder, "pendulum.png"))


def _frames():
    """Yield a seamlessly-looping animated test pattern as rgb24 ndarrays.

    A rotating bright wedge + moving concentric rings over a radial blue gradient --
    deliberately obvious motion, so the fact that the clock hands run on their own
    independent timeline is visible at a glance.
    """
    import numpy as np

    n = DURATION * FPS
    yy, xx = np.mgrid[0:TARGET, 0:TARGET].astype("float32")
    cx = cy = TARGET / 2.0
    dx, dy = xx - cx, yy - cy
    r = np.sqrt(dx * dx + dy * dy)
    ang = np.arctan2(dy, dx)
    g = np.clip(1.0 - r / (TARGET * 0.62), 0.0, 1.0)  # radial falloff
    for i in range(n):
        ph = i / n * 2 * np.pi  # phase completes exactly one turn -> seamless loop
        wedge = 0.5 + 0.5 * np.cos(ang - ph)
        rings = 0.5 + 0.5 * np.sin(r / 13.0 - ph * 2)
        red = 24 + 150 * wedge * g
        grn = 55 + 90 * rings * g
        blu = 90 + 130 * g
        frame = np.stack([red, grn, blu], axis=-1)
        yield np.clip(frame, 0, 255).astype("uint8")


def make_loop(folder: str) -> bool:
    """Encode the test-pattern loop to H.264 via PyAV (no system ffmpeg needed)."""
    out = os.path.join(folder, "loop.mp4")
    try:
        import av
    except ImportError:
        print("PyAV not installed; skipping loop.mp4 (renderer shows a flat accent "
              "disc).", file=sys.stderr)
        return False
    try:
        container = av.open(out, mode="w")
        stream = container.add_stream("libx264", rate=FPS)
        stream.width = TARGET
        stream.height = TARGET
        stream.pix_fmt = "yuv420p"
        stream.options = {"crf": "20", "preset": "medium"}
        for arr in _frames():
            frame = av.VideoFrame.from_ndarray(arr, format="rgb24")
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():  # flush
            container.mux(packet)
        container.close()
        return True
    except Exception as e:  # pragma: no cover
        print("PyAV encode failed: %s" % e, file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join("examples", "testcard"))
    args = ap.parse_args()
    os.makedirs(args.dir, exist_ok=True)
    make_theme(args.dir)
    make_pendulum(args.dir)
    ok = make_loop(args.dir)
    print("Sample design written to %s (loop.mp4: %s)" % (args.dir, "yes" if ok else "no"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
