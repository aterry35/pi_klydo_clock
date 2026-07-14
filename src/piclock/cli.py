"""Command-line entry point.

Clock-wide settings come from config/clock.json and optional device override
files. Command-line options remain available as temporary diagnostic overrides.
"""
from __future__ import annotations

import argparse
import os
import sys


def build_config(argv=None):
    parser = argparse.ArgumentParser(prog="piclock", description="Pi Klydo Clock renderer")
    parser.add_argument(
        "--config", action="append", default=[],
        help="Additional clock JSON file. Can be repeated; the last value wins."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--windowed", dest="windowed", action="store_true",
                      help="Override JSON and open a desktop window.")
    mode.add_argument("--kms", dest="windowed", action="store_false",
                      help="Override JSON and use fullscreen SDL kmsdrm.")
    mode.set_defaults(windowed=None)
    parser.add_argument("--designs",
                        help="Override the system designs folder.")
    parser.add_argument("--user-designs", action="append", default=[],
                        help="Extra user/community design folder to scan. Can be repeated.")
    parser.add_argument("--no-default-user-designs", action="store_true",
                        help="Ignore all JSON-configured user design folders.")
    parser.add_argument("--state", help="Override the persistent state file.")
    parser.add_argument("--design-mode", choices=["daily", "manual"],
                        help="Override the startup design selection mode.")
    parser.add_argument("--fps", type=int, help="Override target frame rate.")
    parser.add_argument("--rotate", type=int, choices=[0, 90, 180, 270],
                        help="Override in-app display rotation.")
    parser.add_argument("--touch-rotate", type=int, choices=[0, 90, 180, 270],
                        help="Override touch input rotation.")
    parser.add_argument("--circle-y-scale", type=float,
                        help="Override correction for non-square display pixels.")
    parser.add_argument("--circle-offset-x", type=int, default=0,
                        help="Move both circles horizontally for enclosure registration.")
    parser.add_argument("--dial-offset-y", type=int, default=0,
                        help="Move the dial vertically for enclosure registration.")
    parser.add_argument("--pendulum-offset-y", type=int, default=0,
                        help="Move the pendulum circle vertically for enclosure registration.")
    parser.add_argument("--width", type=int, help="Override canvas width.")
    parser.add_argument("--height", type=int, help="Override canvas height.")
    args = parser.parse_args(argv)
    if args.circle_y_scale is not None and not 0.5 <= args.circle_y_scale <= 1.5:
        parser.error("--circle-y-scale must be between 0.5 and 1.5")

    from .config import Circle, load_clock_config

    cfg = load_clock_config(args.config)
    for attr, value in (
        ("width", args.width),
        ("height", args.height),
        ("fps", args.fps),
        ("rotate", args.rotate),
        ("touch_rotate", args.touch_rotate),
        ("windowed", args.windowed),
        ("circle_y_scale", args.circle_y_scale),
        ("designs_dir", args.designs),
        ("state_path", args.state),
        ("design_mode", args.design_mode),
    ):
        if value is not None:
            setattr(cfg, attr, value)

    if args.no_default_user_designs:
        cfg.user_design_dirs = []
    cfg.user_design_dirs.extend(args.user_designs)
    cfg.top = Circle(
        cfg.top.cx + args.circle_offset_x,
        cfg.top.cy + args.dial_offset_y,
        cfg.top.r,
    )
    cfg.bottom = Circle(
        cfg.bottom.cx + args.circle_offset_x,
        cfg.bottom.cy + args.pendulum_offset_y,
        cfg.bottom.r,
    )

    # Select the SDL backend before pygame is imported by the app module.
    if not cfg.windowed:
        os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    return cfg


def main() -> int:
    cfg = build_config()
    from .app import run
    run(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
