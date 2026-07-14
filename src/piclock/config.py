"""Load clock-wide display, enclosure, and design-discovery configuration."""
from __future__ import annotations

import copy
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


DEFAULT_USER_DESIGN_DIRS = (
    "/boot/firmware/piclock-designs",
    "/boot/piclock-designs",
    "~/piclock-designs",
)


@dataclass(frozen=True)
class Circle:
    """A circular layer region, in portrait canvas coordinates."""

    cx: int
    cy: int
    r: int

    @property
    def diameter(self) -> int:
        return self.r * 2

    @property
    def topleft(self) -> tuple[int, int]:
        return (self.cx - self.r, self.cy - self.r)


@dataclass(frozen=True)
class DiameterRange:
    minimum: int
    default: int
    maximum: int

    def clamp(self, value) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = self.default
        return max(self.minimum, min(self.maximum, parsed))


@dataclass(frozen=True)
class Aperture:
    left_mm: float
    top_mm: float
    diameter_mm: float


@dataclass(frozen=True)
class Enclosure:
    width_mm: float
    height_mm: float
    dial: Aperture
    pendulum: Aperture


@dataclass(frozen=True)
class DesignAssets:
    dial_canvas: tuple[int, int]
    pendulum_canvas: tuple[int, int]
    video_min_fps: float
    video_preferred_fps: float
    video_max_fps: float
    video_min_duration_s: float
    video_preferred_duration_s: tuple[float, float]
    video_max_duration_s: float


DEFAULT_DIAL_DIAMETERS = DiameterRange(400, 400, 500)
DEFAULT_PENDULUM_DIAMETERS = DiameterRange(260, 300, 340)
DEFAULT_ENCLOSURE = Enclosure(
    102.0,
    165.0,
    Aperture(14.9954, 16.4983, 76.0),
    Aperture(29.0742, 107.4681, 48.5),
)
DEFAULT_DESIGN_ASSETS = DesignAssets(
    dial_canvas=(480, 480),
    pendulum_canvas=(300, 400),
    video_min_fps=10.0,
    video_preferred_fps=15.0,
    video_max_fps=30.0,
    video_min_duration_s=2.0,
    video_preferred_duration_s=(4.0, 10.0),
    video_max_duration_s=12.0,
)


@dataclass
class Config:
    width: int = 480
    height: int = 800
    fps: int = 30
    rotate: int = 0
    touch_rotate: int = 0
    windowed: bool = True
    circle_y_scale: float = 1.0

    designs_dir: str = "designs"
    user_design_dirs: list[str] = field(
        default_factory=lambda: list(DEFAULT_USER_DESIGN_DIRS)
    )
    state_path: str = ".piclock-state.json"
    design_mode: str = "daily"

    top: Circle = field(default_factory=lambda: Circle(cx=240, cy=250, r=200))
    bottom: Circle = field(default_factory=lambda: Circle(cx=240, cy=640, r=150))
    fixture_border_px: int = 0
    dial_diameters: DiameterRange = DEFAULT_DIAL_DIAMETERS
    pendulum_diameters: DiameterRange = DEFAULT_PENDULUM_DIAMETERS
    design_assets: DesignAssets = DEFAULT_DESIGN_ASSETS
    enclosure: Enclosure = DEFAULT_ENCLOSURE
    config_paths: tuple[str, ...] = ()

    dim: bool = False

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)

    @property
    def design_dirs(self) -> list[str]:
        return [self.designs_dir, *self.user_design_dirs]

    @staticmethod
    def from_dict(data: dict) -> "Config":
        if not isinstance(data, dict):
            raise ValueError("clock configuration must contain a JSON object")
        version = data.get("schema_version", 1)
        if version != 1:
            raise ValueError("schema_version must be 1")

        display = _section(data, "display")
        layout = _section(data, "layout")
        designs = _section(data, "designs")
        assets_data = _section(designs, "assets")
        enclosure_data = _section(data, "enclosure")

        width = _integer(display, "width", 480, 100, 4096)
        height = _integer(display, "height", 800, 100, 4096)
        display_mode = str(display.get("mode", "windowed")).strip().lower()
        if display_mode not in ("windowed", "kms"):
            raise ValueError("display.mode must be windowed or kms")
        rotate = _integer(display, "rotate", 0, 0, 270)
        touch_rotate = _integer(display, "touch_rotate", 0, 0, 270)
        if rotate not in (0, 90, 180, 270):
            raise ValueError("display.rotate must be 0, 90, 180, or 270")
        if touch_rotate not in (0, 90, 180, 270):
            raise ValueError("display.touch_rotate must be 0, 90, 180, or 270")

        dial_data = _section(layout, "dial")
        pendulum_data = _section(layout, "pendulum")
        dial_sizes = _diameter_range(dial_data, DEFAULT_DIAL_DIAMETERS, "layout.dial")
        pendulum_sizes = _diameter_range(
            pendulum_data, DEFAULT_PENDULUM_DIAMETERS, "layout.pendulum"
        )
        dial_center = _center(dial_data, "center", (240, 250), width, height)
        pendulum_center = _center(
            pendulum_data, "center", (240, 640), width, height
        )

        panel_mm = _pair(enclosure_data, "panel_mm", (102.0, 165.0), positive=True)
        enclosure = Enclosure(
            width_mm=panel_mm[0],
            height_mm=panel_mm[1],
            dial=_aperture(enclosure_data, "dial_aperture", DEFAULT_ENCLOSURE.dial),
            pendulum=_aperture(
                enclosure_data, "pendulum_aperture", DEFAULT_ENCLOSURE.pendulum
            ),
        )

        user_dirs = designs.get("user_directories", list(DEFAULT_USER_DESIGN_DIRS))
        if not isinstance(user_dirs, list) or not all(isinstance(path, str) for path in user_dirs):
            raise ValueError("designs.user_directories must be a JSON string array")
        design_mode = str(designs.get("startup_mode", "daily")).strip().lower()
        if design_mode not in ("daily", "manual"):
            raise ValueError("designs.startup_mode must be daily or manual")

        dial_canvas = _int_pair(
            assets_data, "dial_canvas", DEFAULT_DESIGN_ASSETS.dial_canvas, positive=True
        )
        pendulum_canvas = _int_pair(
            assets_data,
            "pendulum_canvas",
            DEFAULT_DESIGN_ASSETS.pendulum_canvas,
            positive=True,
        )
        if dial_canvas[0] != dial_canvas[1]:
            raise ValueError("designs.assets.dial_canvas must be square")
        preferred_duration = _pair(
            assets_data,
            "video_preferred_duration_s",
            DEFAULT_DESIGN_ASSETS.video_preferred_duration_s,
            positive=True,
        )
        assets = DesignAssets(
            dial_canvas=dial_canvas,
            pendulum_canvas=pendulum_canvas,
            video_min_fps=_number(
                assets_data, "video_min_fps", DEFAULT_DESIGN_ASSETS.video_min_fps, 1, 240
            ),
            video_preferred_fps=_number(
                assets_data,
                "video_preferred_fps",
                DEFAULT_DESIGN_ASSETS.video_preferred_fps,
                1,
                240,
            ),
            video_max_fps=_number(
                assets_data, "video_max_fps", DEFAULT_DESIGN_ASSETS.video_max_fps, 1, 240
            ),
            video_min_duration_s=_number(
                assets_data,
                "video_min_duration_s",
                DEFAULT_DESIGN_ASSETS.video_min_duration_s,
                0.1,
                3600,
            ),
            video_preferred_duration_s=preferred_duration,
            video_max_duration_s=_number(
                assets_data,
                "video_max_duration_s",
                DEFAULT_DESIGN_ASSETS.video_max_duration_s,
                0.1,
                3600,
            ),
        )
        if not assets.video_min_fps <= assets.video_preferred_fps <= assets.video_max_fps:
            raise ValueError("design video FPS values must be ordered min <= preferred <= max")
        if not (
            assets.video_min_duration_s
            <= assets.video_preferred_duration_s[0]
            <= assets.video_preferred_duration_s[1]
            <= assets.video_max_duration_s
        ):
            raise ValueError("design video duration values must be ordered")

        return Config(
            width=width,
            height=height,
            fps=_integer(display, "fps", 30, 1, 120),
            rotate=rotate,
            touch_rotate=touch_rotate,
            windowed=display_mode != "kms",
            circle_y_scale=_number(display, "circle_y_scale", 1.0, 0.5, 1.5),
            designs_dir=_string(designs, "system_directory", "designs"),
            user_design_dirs=list(user_dirs),
            state_path=_string(designs, "state_path", ".piclock-state.json"),
            design_mode=design_mode,
            top=Circle(dial_center[0], dial_center[1], dial_sizes.default // 2),
            bottom=Circle(
                pendulum_center[0], pendulum_center[1], pendulum_sizes.default // 2
            ),
            fixture_border_px=_integer(layout, "fixture_border_px", 0, 0, 100),
            dial_diameters=dial_sizes,
            pendulum_diameters=pendulum_sizes,
            design_assets=assets,
            enclosure=enclosure,
        )


def bundled_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "clock.json"


def standard_config_paths() -> list[Path]:
    return [
        bundled_config_path(),
        Path("/etc/piclock/clock.json"),
        Path("/boot/piclock-config.json"),
        Path("/boot/firmware/piclock-config.json"),
    ]


def load_config_files(paths: Iterable[str | Path]) -> Config:
    merged: dict = {}
    loaded: list[str] = []
    seen: set[Path] = set()
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        try:
            candidate_data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(candidate_data, dict):
                raise ValueError("top level must be a JSON object")
            candidate = _deep_merge(merged, candidate_data)
            Config.from_dict(candidate)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            print(f"WARNING: ignoring invalid clock config {path}: {exc}", file=sys.stderr)
            continue
        merged = candidate
        loaded.append(str(path))

    config = Config.from_dict(merged)
    config.config_paths = tuple(loaded)
    return config


def load_clock_config(extra_paths: Iterable[str | Path] = ()) -> Config:
    return load_config_files([*standard_config_paths(), *extra_paths])


def _deep_merge(base: dict, overlay: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _section(data: dict, key: str) -> dict:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a JSON object")
    return value


def _number(data: dict, key: str, default, minimum, maximum) -> float:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number")
    if not minimum <= value <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return float(value)


def _integer(data: dict, key: str, default: int, minimum: int, maximum: int) -> int:
    value = _number(data, key, default, minimum, maximum)
    if not value.is_integer():
        raise ValueError(f"{key} must be an integer")
    return int(value)


def _string(data: dict, key: str, default: str) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _pair(data: dict, key: str, default, *, positive: bool = False) -> tuple[float, float]:
    value = data.get(key, default)
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value)
    ):
        raise ValueError(f"{key} must be a two-number JSON array")
    pair = (float(value[0]), float(value[1]))
    if positive and (pair[0] <= 0 or pair[1] <= 0):
        raise ValueError(f"{key} values must be positive")
    return pair


def _int_pair(data: dict, key: str, default, *, positive: bool = False) -> tuple[int, int]:
    pair = _pair(data, key, default, positive=positive)
    if not pair[0].is_integer() or not pair[1].is_integer():
        raise ValueError(f"{key} values must be integers")
    return (int(pair[0]), int(pair[1]))


def _center(data: dict, key: str, default, width: int, height: int) -> tuple[int, int]:
    pair = _pair(data, key, list(default))
    if not pair[0].is_integer() or not pair[1].is_integer():
        raise ValueError(f"{key} values must be integers")
    if not -width <= pair[0] <= width * 2 or not -height <= pair[1] <= height * 2:
        raise ValueError(f"{key} is outside the supported canvas registration range")
    return (int(pair[0]), int(pair[1]))


def _diameter_range(data: dict, default: DiameterRange, label: str) -> DiameterRange:
    result = DiameterRange(
        minimum=_integer(data, "minimum_diameter", default.minimum, 1, 4096),
        default=_integer(data, "default_diameter", default.default, 1, 4096),
        maximum=_integer(data, "maximum_diameter", default.maximum, 1, 4096),
    )
    if not result.minimum <= result.default <= result.maximum:
        raise ValueError(
            f"{label} diameters must satisfy minimum <= default <= maximum"
        )
    return result


def _aperture(data: dict, key: str, default: Aperture) -> Aperture:
    section = _section(data, key)
    return Aperture(
        left_mm=_number(section, "left_mm", default.left_mm, -1000, 1000),
        top_mm=_number(section, "top_mm", default.top_mm, -1000, 1000),
        diameter_mm=_number(section, "diameter_mm", default.diameter_mm, 0.1, 1000),
    )
