#!/usr/bin/env python3
"""Render reproducible documentation screenshots from installed clock designs."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from piclock.config import load_clock_config


def render_previews(designs_dir: Path, output_dir: Path, config_paths: list[str]) -> list[Path]:
    import pygame

    from piclock.app import ClockApp

    cfg = load_clock_config(config_paths)
    cfg.windowed = True
    cfg.rotate = 0
    cfg.designs_dir = str(designs_dir)
    cfg.user_design_dirs = []
    cfg.state_path = ""
    cfg.design_mode = "daily"

    output_dir.mkdir(parents=True, exist_ok=True)
    app = ClockApp(cfg)
    rendered = []
    try:
        for index, design in enumerate(app.designs.designs):
            app.designs.index = index
            app._load_current()
            app._render(
                t=1.0,
                hms=(10 + 10 / 60, 10, 30),
                hour24=10 + 10 / 60,
            )
            slug = Path(design.path).name.lower()
            output_path = output_dir / f"{slug}.png"
            pygame.image.save(app.canvas, output_path)
            rendered.append(output_path)
    finally:
        if app.video is not None:
            app.video.close()
        pygame.quit()
    return rendered


def build_gallery(previews: list[Path], output_path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    tile_width, tile_height = 360, 600
    gap, label_height = 28, 54
    canvas = Image.new("RGB", (tile_width * len(previews) + gap * (len(previews) + 1),
                               tile_height + label_height + gap * 2), "#111214")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default(size=22)
    for index, preview_path in enumerate(previews):
        image = Image.open(preview_path).convert("RGB")
        image.thumbnail((tile_width, tile_height), Image.Resampling.LANCZOS)
        left = gap + index * (tile_width + gap) + (tile_width - image.width) // 2
        top = gap
        canvas.paste(image, (left, top))
        label = preview_path.stem.replace("-", " ").title()
        bounds = draw.textbbox((0, 0), label, font=font)
        label_x = gap + index * (tile_width + gap) + (tile_width - (bounds[2] - bounds[0])) // 2
        draw.text((label_x, tile_height + gap + 14), label, fill="#f1f1ef", font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--designs", type=Path, default=ROOT / "designs")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "images" / "designs")
    parser.add_argument("--config", action="append", default=[])
    args = parser.parse_args()

    previews = render_previews(args.designs.resolve(), args.output.resolve(), args.config)
    if not previews:
        print(f"No designs found in {args.designs}", file=sys.stderr)
        return 1
    gallery = args.output.resolve().parent / "design-gallery.png"
    build_gallery(previews, gallery)
    for path in [*previews, gallery]:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
