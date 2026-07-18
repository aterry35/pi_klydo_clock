"""Design-folder discovery and theme model.

A "design" is a folder on the SD card. The folder FULLY defines the design --
there are no hardcoded asset paths anywhere in the renderer:

    designs/<name>/
        loop.mp4 | loop.webm     background animation for the top circle
        pendulum.png | .svg       pendulum sprite for the bottom circle
        theme.json                hand style/colour, pendulum physics, dial,
                                  bottom backdrop, ambiance

Anything missing degrades gracefully (a flat accent disc / procedural pendulum),
so a brand-new folder with only a partial theme.json still renders.
"""
from __future__ import annotations

import json
import os
from datetime import date
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence

from .config import (
    DEFAULT_DIAL_DIAMETERS,
    DEFAULT_PENDULUM_DIAMETERS,
    DiameterRange,
)


def _hex(value, default: str) -> tuple[int, int, int]:
    """Parse '#rrggbb' (or '#rgb') into an (r, g, b) tuple, falling back safely."""
    s = str(value or default).lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except (ValueError, IndexError):
        return _hex(default, "000000")


@dataclass
class HandStyle:
    color: tuple[int, int, int]
    width: int
    length: float  # fraction of the clock radius
    glow: bool = True
    visible: bool = True
    shape: str = "spindle"


@dataclass
class Pendulum:
    period_s: float = 2.0
    amplitude_deg: float = 12.0
    pivot: tuple[float, float] = (0.5, 0.06)  # fraction of the bottom circle bbox
    rod_length: float = 0.8


@dataclass
class BottomBackdrop:
    mode: str = "loop"  # "loop" | "solid" | "none"
    color: tuple[int, int, int] = (5, 5, 5)
    diameter: int = 300


@dataclass
class Theme:
    name: str
    artist: str
    watermark: str
    watermark_enabled: bool
    watermark_color: tuple[int, int, int]
    watermark_opacity: float
    accent: tuple[int, int, int]
    background: tuple[int, int, int]
    hour: HandStyle
    minute: HandStyle
    second: HandStyle
    dial_color: tuple[int, int, int]
    dial_markings: str  # "ticks" | "none"
    dial_count: int
    dial_diameter: int
    pendulum: Pendulum
    bottom: BottomBackdrop
    day_night: bool
    twinkle: bool
    glow: bool

    @staticmethod
    def from_dict(
        d: dict,
        dial_diameters: DiameterRange = DEFAULT_DIAL_DIAMETERS,
        pendulum_diameters: DiameterRange = DEFAULT_PENDULUM_DIAMETERS,
    ) -> "Theme":
        d = d or {}
        accent = _hex(d.get("accent"), "#d9a24a")
        hands = d.get("hands", {})

        def hand(key, dcolor, dwidth, dlen) -> HandStyle:
            h = hands.get(key, {})
            return HandStyle(
                color=_hex(h.get("color"), dcolor),
                width=int(h.get("width", dwidth)),
                length=float(h.get("length", dlen)),
                glow=bool(h.get("glow", True)),
                visible=bool(h.get("visible", True)),
                shape=str(h.get("shape", "spindle")),
            )

        dial = d.get("dial", {})
        p = d.get("pendulum", {})
        pivot = p.get("pivot", [0.5, 0.06])
        bottom = d.get("bottom", {})
        bottom_mode = str(bottom.get("backdrop", "loop")).strip().lower()
        if bottom_mode not in ("loop", "solid", "none"):
            bottom_mode = "loop"
        amb = d.get("ambiance", {})
        creator = d.get("creator", {})
        artist = str(creator.get("artist", "")).strip()[:60]
        watermark = str(creator.get("watermark", artist)).strip()[:60]
        try:
            watermark_opacity = min(1.0, max(0.25, float(creator.get("watermark_opacity", 0.78))))
        except (TypeError, ValueError):
            watermark_opacity = 0.78
        background = _hex(d.get("background"), "#050505")

        return Theme(
            name=str(d.get("name", "Untitled")),
            artist=artist,
            watermark=watermark,
            watermark_enabled=bool(creator.get("watermark_enabled", False)) and bool(watermark),
            watermark_color=_hex(creator.get("watermark_color"), "#ffffff"),
            watermark_opacity=watermark_opacity,
            accent=accent,
            background=background,
            hour=hand("hour", "#f0c070", 10, 0.52),
            minute=hand("minute", "#f0c070", 6, 0.78),
            second=hand("second", "#e0564a", 2, 0.88),
            dial_color=_hex(dial.get("color"), "#ffffff"),
            dial_markings=str(dial.get("markings", "ticks")),
            dial_count=int(dial.get("count", 12)),
            dial_diameter=dial_diameters.clamp(dial.get("diameter")),
            pendulum=Pendulum(
                period_s=float(p.get("period_s", 2.0)),
                amplitude_deg=float(p.get("amplitude_deg", 12.0)),
                pivot=(float(pivot[0]), float(pivot[1])),
                rod_length=float(p.get("rod_length", 0.8)),
            ),
            bottom=BottomBackdrop(
                mode=bottom_mode,
                color=_hex(bottom.get("color"), "#%02x%02x%02x" % background),
                diameter=pendulum_diameters.clamp(bottom.get("diameter")),
            ),
            day_night=bool(amb.get("day_night", True)),
            twinkle=bool(amb.get("twinkle", False)),
            glow=bool(amb.get("glow", False)),
        )


@dataclass
class Design:
    name: str
    path: str
    theme: Theme
    loop_path: Optional[str]
    pendulum_path: Optional[str]


def _find(folder: str, names: list[str]) -> Optional[str]:
    for n in names:
        p = os.path.join(folder, n)
        if os.path.isfile(p):
            return p
    return None


def load_design(
    folder: str,
    dial_diameters: DiameterRange = DEFAULT_DIAL_DIAMETERS,
    pendulum_diameters: DiameterRange = DEFAULT_PENDULUM_DIAMETERS,
) -> Optional[Design]:
    if not os.path.isdir(folder):
        return None
    theme_path = os.path.join(folder, "theme.json")
    data = {}
    if os.path.isfile(theme_path):
        try:
            with open(theme_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
    theme = Theme.from_dict(data, dial_diameters, pendulum_diameters)
    return Design(
        name=theme.name if data.get("name") else os.path.basename(folder.rstrip("/")),
        path=folder,
        theme=theme,
        loop_path=_find(folder, ["loop.mp4", "loop.webm", "loop.mkv"]),
        pendulum_path=_find(folder, ["pendulum.png", "pendulum.svg"]),
    )


def _design_roots(designs_dirs: str | Sequence[str]) -> list[str]:
    if isinstance(designs_dirs, str):
        raw_dirs = [designs_dirs]
    else:
        raw_dirs = list(designs_dirs)
    roots = []
    seen = set()
    for root in raw_dirs:
        expanded = os.path.abspath(os.path.expanduser(str(root)))
        if expanded in seen:
            continue
        seen.add(expanded)
        roots.append(expanded)
    return roots


@dataclass
class DesignSet:
    """Ordered, cyclable collection of designs discovered on disk."""

    designs: list[Design] = field(default_factory=list)
    index: int = 0
    state_path: Optional[str] = None
    mode: str = "daily"

    @staticmethod
    def scan(
        designs_dir: str | Sequence[str],
        state_path: Optional[str] = None,
        default_mode: str = "daily",
        dial_diameters: DiameterRange = DEFAULT_DIAL_DIAMETERS,
        pendulum_diameters: DiameterRange = DEFAULT_PENDULUM_DIAMETERS,
    ) -> "DesignSet":
        found = []
        slug_indexes = {}
        for root in _design_roots(designs_dir):
            if not os.path.isdir(root):
                continue
            for name in sorted(os.listdir(root)):
                folder = os.path.join(root, name)
                if not os.path.isdir(folder):
                    continue
                slug = name.casefold()
                d = load_design(folder, dial_diameters, pendulum_diameters)
                if d is not None:
                    if slug in slug_indexes:
                        # Roots are ordered from lowest to highest priority, so
                        # SD-card/SCP designs can replace bundled designs safely.
                        found[slug_indexes[slug]] = d
                    else:
                        slug_indexes[slug] = len(found)
                        found.append(d)
        ds = DesignSet(designs=found, state_path=state_path,
                       mode=default_mode if default_mode in ("daily", "manual") else "daily")
        ds._restore_or_select()
        return ds

    @property
    def current(self) -> Optional[Design]:
        if not self.designs:
            return None
        return self.designs[self.index % len(self.designs)]

    def next(self) -> Optional[Design]:
        if self.designs:
            self.mode = "manual"
            self.index = (self.index + 1) % len(self.designs)
            self._save()
        return self.current

    def prev(self) -> Optional[Design]:
        if self.designs:
            self.mode = "manual"
            self.index = (self.index - 1) % len(self.designs)
            self._save()
        return self.current

    def daily(self) -> Optional[Design]:
        """Return to Klydo-style daily rotation."""
        self.mode = "daily"
        self._select_daily()
        self._save()
        return self.current

    def _select_daily(self) -> None:
        if self.designs:
            self.index = date.today().toordinal() % len(self.designs)

    def _find_index(self, name: str) -> Optional[int]:
        for i, design in enumerate(self.designs):
            if design.name == name or os.path.basename(design.path.rstrip("/")) == name:
                return i
        return None

    def _restore_or_select(self) -> None:
        if not self.designs:
            self.index = 0
            return
        state = self._read_state()
        mode = str(state.get("mode") or self.mode)
        if mode == "manual":
            selected = state.get("selected")
            idx = self._find_index(str(selected)) if selected else None
            if idx is not None:
                self.mode = "manual"
                self.index = idx
                return
        self.mode = "daily"
        self._select_daily()

    def _read_state(self) -> dict:
        if not self.state_path:
            return {}
        try:
            with open(os.path.expanduser(self.state_path), "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self) -> None:
        if not self.state_path or not self.current:
            return
        path = Path(os.path.expanduser(self.state_path))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8") as f:
                json.dump({
                    "mode": self.mode,
                    "selected": self.current.name,
                    "folder": os.path.basename(self.current.path.rstrip("/")),
                }, f, indent=2)
                f.write("\n")
        except OSError:
            pass
