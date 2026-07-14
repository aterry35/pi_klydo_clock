"""Themed swinging pendulum in the bottom circle.

The swing is a real-time simple-harmonic motion driven by the theme's period and
amplitude, so the pendulum reads as a physical clock rather than a fixed CSS loop.
The sprite (pendulum.png or pendulum.svg) is rotated about its pivot; if no sprite
exists a rod+bob is drawn procedurally so any design still shows a pendulum.
"""
from __future__ import annotations

import io
import math
from typing import Optional

import pygame

try:
    import cairosvg
    _HAVE_CAIROSVG = True
except Exception:  # pragma: no cover - optional dependency guard
    cairosvg = None
    _HAVE_CAIROSVG = False

from ..config import Circle
from ..designs import Theme


def _rotate_about_pivot(surface: pygame.Surface, image: pygame.Surface,
                        pivot_on_screen: tuple[float, float],
                        pivot_in_image: tuple[float, float], angle_deg: float) -> None:
    """Blit `image` rotated by `angle_deg` (CCW) so its pivot stays on the screen point."""
    rect = image.get_rect(topleft=(pivot_on_screen[0] - pivot_in_image[0],
                                   pivot_on_screen[1] - pivot_in_image[1]))
    offset = pygame.math.Vector2(pivot_on_screen) - rect.center
    rotated_offset = offset.rotate(-angle_deg)
    new_center = (pivot_on_screen[0] - rotated_offset.x,
                  pivot_on_screen[1] - rotated_offset.y)
    rotated = pygame.transform.rotozoom(image, angle_deg, 1.0)
    surface.blit(rotated, rotated.get_rect(center=new_center))


class PendulumLayer:
    def __init__(self, sprite_path: Optional[str], circle: Circle, theme: Theme):
        self.circle = circle
        self.theme = theme
        self.pend = theme.pendulum
        # Pivot is expressed as a fraction of the bottom circle's bounding box.
        px = circle.cx - circle.r + self.pend.pivot[0] * circle.diameter
        py = circle.cy - circle.r + self.pend.pivot[1] * circle.diameter
        self.pivot_screen = (px, py)
        self.rod_len = self.pend.rod_length * circle.diameter * 0.5
        self.sprite = self._load_or_build(sprite_path)
        # The sprite's pivot is its top-centre.
        self.pivot_in_image = (self.sprite.get_width() / 2, 0)

    def _load_or_build(self, path: Optional[str]) -> pygame.Surface:
        if path and path.lower().endswith(".png"):
            try:
                sprite = pygame.image.load(path).convert_alpha()
                return self._fit_to_circle(sprite)
            except Exception:
                pass
        if path and path.lower().endswith(".svg"):
            sprite = self._load_svg(path)
            if sprite is not None:
                return self._fit_to_circle(sprite)
        return self._build_procedural()

    def _load_svg(self, path: str) -> Optional[pygame.Surface]:
        if not _HAVE_CAIROSVG:
            return None
        try:
            png = cairosvg.svg2png(url=path)
            return pygame.image.load(io.BytesIO(png), "pendulum.png").convert_alpha()
        except Exception:
            return None

    def _fit_to_circle(self, sprite: pygame.Surface) -> pygame.Surface:
        """Scale a sprite (pivot at top-centre) so the whole pendulum hangs inside
        the bottom circle regardless of the source PNG's native size."""
        avail_h = (self.circle.cy + self.circle.r) - self.pivot_screen[1]
        target_h = max(1.0, avail_h * 0.94)
        w, h = sprite.get_size()
        if h <= 0:
            return sprite
        scale = target_h / h
        # Also cap width so the bob cannot exceed the circle horizontally.
        if w * scale > self.circle.diameter * 0.9:
            scale = (self.circle.diameter * 0.9) / w
        return pygame.transform.smoothscale(sprite, (max(1, int(w * scale)),
                                                     max(1, int(h * scale))))

    def _build_procedural(self) -> pygame.Surface:
        rod_len = int(self.rod_len)
        bob_r = max(10, int(self.circle.r * 0.16))
        w = bob_r * 2 + 8
        h = rod_len + bob_r * 2 + 8
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        cx = w // 2
        # Rod.
        pygame.draw.line(surf, (200, 200, 210), (cx, 2), (cx, rod_len), 4)
        # Bob with a themed accent ring + a highlight.
        bob_c = (cx, rod_len + bob_r)
        pygame.draw.circle(surf, self.theme.accent, bob_c, bob_r)
        pygame.draw.circle(surf, (245, 240, 220), bob_c, int(bob_r * 0.7))
        pygame.draw.circle(surf, self.theme.accent, bob_c, bob_r, 3)
        return surf

    def draw(self, surface: pygame.Surface, t: float) -> None:
        # Simple harmonic motion: angle = A * sin(2*pi*t / period).
        period = max(0.2, self.pend.period_s)
        angle = self.pend.amplitude_deg * math.sin(2 * math.pi * t / period)
        # Pivot cap.
        pygame.draw.circle(surface, self.theme.accent,
                           (int(self.pivot_screen[0]), int(self.pivot_screen[1])), 6)
        _rotate_about_pivot(surface, self.sprite, self.pivot_screen,
                            self.pivot_in_image, angle)
