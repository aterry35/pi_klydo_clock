"""Live, time-driven ambiance used as a subtle overlay inside the cutouts.

This is the piece of genuine real-time logic worth keeping from the original app:
the background colour tracks the real hour (a warm daytime wash easing into a deep
night blue), and optional twinkling stars fade in at night. Because it is driven by
the clock -- not the video -- it stays in sync with actual local time.
"""
from __future__ import annotations

import math

import pygame

from ..designs import Theme


def _lerp(a, b, t):
    return a + (b - a) * t


def _mix(c1, c2, t):
    return tuple(int(_lerp(c1[i], c2[i], t)) for i in range(3))


# Anchor colours across the day (hour -> background wash).
_DAY = (18, 26, 42)      # bright-ish blue-grey midday
_DUSK = (40, 22, 30)     # warm dusk
_NIGHT = (5, 7, 16)      # deep night


def _nightness(hour_float: float) -> float:
    """0.0 at midday, 1.0 deep at night -- a smooth cosine over 24h."""
    # Peak brightness ~13:00, darkest ~01:00.
    phase = (hour_float - 13.0) / 24.0 * 2 * math.pi
    return (1 - math.cos(phase)) / 2  # 0 at 13:00, 1 at 01:00


class Ambiance:
    def __init__(self, size: tuple[int, int], theme: Theme, seed: int = 7):
        self.size = size
        self.theme = theme
        # Fixed normalised star field shared with the browser preview.
        self.stars = [
            (0.5 + math.cos(i * 2.399963) * math.sqrt(((i * 137) % 100) / 100) * 0.455,
             0.5 + math.sin(i * 2.399963) * math.sqrt(((i * 137) % 100) / 100) * 0.455,
             0.6 + ((i * 53) % 100) / 100,
             (i * 0.61) % (2 * math.pi))
            for i in range(60)
        ]

    def background_color(self, hour_float: float) -> tuple[int, int, int]:
        if not self.theme.day_night:
            return self.theme.background
        n = _nightness(hour_float)
        # Day -> dusk in the first half, dusk -> night in the second.
        if n < 0.5:
            base = _mix(_DAY, _DUSK, n / 0.5)
        else:
            base = _mix(_DUSK, _NIGHT, (n - 0.5) / 0.5)
        return base

    def draw(self, surface: pygame.Surface, hour_float: float, t: float) -> None:
        surface.fill(self.background_color(hour_float))
        if not self.theme.twinkle:
            return
        n = _nightness(hour_float)
        if n < 0.2:
            return  # stars only show once it is dark enough
        layer = pygame.Surface(self.size, pygame.SRCALPHA)
        for nx, ny, size, phase in self.stars:
            twinkle = 0.5 + 0.5 * math.sin(t * 2.0 + phase)
            alpha = int(200 * n * twinkle)
            if alpha <= 0:
                continue
            x = int(nx * self.size[0])
            y = int(ny * self.size[1] / 3)
            pygame.draw.circle(layer, (235, 240, 255, alpha), (x, y), max(1, int(size)))
        surface.blit(layer, (0, 0))

    def draw_circle_overlay(self, surface: pygame.Surface, circle,
                            hour_float: float, t: float, strength: float = 1.0) -> None:
        """Apply the live time ambiance inside a circular cutout only.

        The fixture area outside the cutouts stays black. The video remains the
        primary artwork; this is only a subtle real-time tint/twinkle layer.
        """
        n = _nightness(hour_float)
        if not self.theme.day_night and not self.theme.twinkle and not self.theme.glow:
            return

        diameter = circle.diameter
        radius = circle.r
        layer = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        if self.theme.day_night:
            tint_alpha = int((18 + 42 * n) * max(0.0, strength))
            pygame.draw.circle(layer, (*self.background_color(hour_float), tint_alpha),
                               (radius, radius), radius)

        if self.theme.glow:
            # Soft concentric accent wash. The browser creator uses the same
            # center-weighted falloff in its deployment preview.
            for step in range(8, 0, -1):
                glow_r = max(1, int(radius * step / 8))
                alpha = int(5 * (9 - step) * max(0.0, strength))
                pygame.draw.circle(layer, (*self.theme.accent, alpha),
                                   (radius, radius), glow_r)

        if self.theme.twinkle and n >= 0.2:
            for nx, ny, size, phase in self.stars:
                x = int(nx * diameter)
                y = int(ny * diameter)
                if (x - radius) ** 2 + (y - radius) ** 2 > radius ** 2:
                    continue
                twinkle = 0.5 + 0.5 * math.sin(t * 2.0 + phase)
                alpha = int(190 * n * twinkle * max(0.0, strength))
                if alpha > 0:
                    pygame.draw.circle(layer, (235, 240, 255, alpha),
                                       (x, y), max(1, int(size)))
        surface.blit(layer, circle.topleft)
