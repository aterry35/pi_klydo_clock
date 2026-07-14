#!/usr/bin/env python3
"""Validate a Pi Clock community design folder.

Usage:
    python scripts/validate_design.py designs/my-design
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from piclock.config import DesignAssets, DiameterRange, load_clock_config


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def check_theme(
    folder: str,
    errors: list[str],
    warnings: list[str],
    dial_diameters: DiameterRange,
    pendulum_diameters: DiameterRange,
) -> None:
    path = os.path.join(folder, "theme.json")
    if not os.path.isfile(path):
        fail(errors, "missing theme.json")
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        fail(errors, "theme.json is not valid JSON: %s" % exc)
        return
    if not isinstance(data, dict):
        fail(errors, "theme.json must contain a JSON object")
        return
    if not data.get("name"):
        warnings.append("theme.json has no name; folder name will be shown")
    for section in ("hands", "pendulum"):
        if section not in data:
            warnings.append("theme.json has no %s section; defaults will be used" % section)
    bottom = data.get("bottom", {})
    if isinstance(bottom, dict):
        mode = str(bottom.get("backdrop", "loop")).strip().lower()
        if mode not in ("loop", "solid", "none"):
            fail(errors, "bottom.backdrop must be loop, solid, or none")
        check_optional_range(
            bottom,
            "diameter",
            pendulum_diameters.minimum,
            pendulum_diameters.maximum,
            "bottom.diameter",
            errors,
        )
    dial = data.get("dial", {})
    if isinstance(dial, dict):
        check_optional_range(
            dial,
            "diameter",
            dial_diameters.minimum,
            dial_diameters.maximum,
            "dial.diameter",
            errors,
        )


def check_optional_range(section: dict, key: str, minimum: int, maximum: int,
                         label: str, errors: list[str]) -> None:
    if key not in section:
        return
    value = section[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        fail(errors, "%s must be a number" % label)
    elif not minimum <= value <= maximum:
        fail(errors, "%s must be between %s and %s" % (label, minimum, maximum))


def check_video(
    folder: str,
    errors: list[str],
    warnings: list[str],
    assets: DesignAssets,
) -> None:
    candidates = ["loop.mp4", "loop.webm", "loop.mkv"]
    path = next((os.path.join(folder, name) for name in candidates
                 if os.path.isfile(os.path.join(folder, name))), None)
    if path is None:
        fail(errors, "missing loop.mp4, loop.webm, or loop.mkv")
        return
    try:
        import av
    except ImportError:
        warnings.append("PyAV is not installed; skipped video metadata check")
        return
    try:
        container = av.open(path)
        stream = container.streams.video[0]
        width, height = stream.width, stream.height
        rate = float(stream.average_rate or stream.base_rate or 0)
        duration = float(stream.duration * stream.time_base) if stream.duration else 0.0
        codec = str(stream.codec_context.name or "")
        decoded_frames = sum(1 for _ in container.decode(video=0))
        container.close()
    except Exception as exc:
        fail(errors, "video cannot be opened by PyAV: %s" % exc)
        return
    if (width, height) != assets.dial_canvas:
        fail(
            errors,
            "video must be %sx%s; got %sx%s"
            % (*assets.dial_canvas, width, height),
        )
    if path.lower().endswith(".mp4") and codec != "h264":
        fail(errors, "loop.mp4 must use H.264; got %s" % (codec or "unknown codec"))
    if rate and rate < assets.video_min_fps:
        fail(
            errors,
            "video frame rate is %.1f fps; at least %.1f fps is required"
            % (rate, assets.video_min_fps),
        )
    elif rate and rate > assets.video_max_fps:
        warnings.append(
            "video frame rate is %.1f fps; %.1f fps is preferred on Pi 3"
            % (rate, assets.video_preferred_fps)
        )
    elif rate and abs(rate - assets.video_preferred_fps) > 0.2:
        warnings.append(
            "video frame rate is %.1f fps; %.1f fps is preferred on Pi 3"
            % (rate, assets.video_preferred_fps)
        )
    if decoded_frames < 40:
        fail(errors, "video contains only %s decoded frames" % decoded_frames)
    preferred_min, preferred_max = assets.video_preferred_duration_s
    if duration and duration < assets.video_min_duration_s:
        fail(
            errors,
            "video is %.1fs; at least %.1fs is required"
            % (duration, assets.video_min_duration_s),
        )
    if duration and duration > assets.video_max_duration_s:
        warnings.append(
            "video is %.1fs; %.1f-%.1fs loops are preferred"
            % (duration, preferred_min, preferred_max)
        )
    elif duration and not preferred_min <= duration <= preferred_max:
        warnings.append(
            "video is %.1fs; %.1f-%.1fs loops are preferred"
            % (duration, preferred_min, preferred_max)
        )


def check_pendulum(
    folder: str,
    errors: list[str],
    warnings: list[str],
    assets: DesignAssets,
) -> None:
    candidates = ["pendulum.png", "pendulum.svg"]
    path = next((os.path.join(folder, name) for name in candidates
                 if os.path.isfile(os.path.join(folder, name))), None)
    if path is None:
        fail(errors, "missing pendulum.png or pendulum.svg")
        return
    if path.lower().endswith(".svg"):
        return
    try:
        from PIL import Image
    except ImportError:
        warnings.append("Pillow is not installed; skipped pendulum PNG metadata check")
        return
    try:
        img = Image.open(path)
    except OSError as exc:
        fail(errors, "pendulum.png cannot be opened: %s" % exc)
        return
    if img.mode not in ("RGBA", "LA"):
        warnings.append("pendulum.png should include alpha transparency; mode is %s" % img.mode)
    if img.size != assets.pendulum_canvas:
        warnings.append(
            "pendulum.png is %sx%s; %sx%s is recommended"
            % (*img.size, *assets.pendulum_canvas)
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Pi Clock design folder")
    parser.add_argument("folder")
    parser.add_argument(
        "--config", action="append", default=[],
        help="Additional clock JSON file. Can be repeated; the last value wins."
    )
    args = parser.parse_args()
    cfg = load_clock_config(args.config)

    folder = os.path.abspath(args.folder)
    errors: list[str] = []
    warnings: list[str] = []
    if not os.path.isdir(folder):
        fail(errors, "%s is not a directory" % folder)
    else:
        check_theme(
            folder,
            errors,
            warnings,
            cfg.dial_diameters,
            cfg.pendulum_diameters,
        )
        check_video(folder, errors, warnings, cfg.design_assets)
        check_pendulum(folder, errors, warnings, cfg.design_assets)

    for warning in warnings:
        print("WARNING: %s" % warning)
    if errors:
        for error in errors:
            print("ERROR: %s" % error, file=sys.stderr)
        return 1
    print("OK: %s is a valid Pi Clock design folder" % folder)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
