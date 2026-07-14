"""Dial (numerals / ticks) + analog hands, drawn live over the video every frame.

Angles come from the TimeSource, never the video, so the hands stay correct
regardless of what the background loop is doing. Hour/minute hands are tapered
"spindle" polygons with an additive glow; the second hand is a thin accent stroke
with a counterweight tail -- matching a real clock face rather than plain lines.

The dial (numerals + dots) is expensive to render (fonts), so it is built once per
design into a cached surface and simply blitted each frame.
"""
from __future__ import annotations

import math

import pygame

from ..config import Circle
from ..designs import HandStyle, Theme

_FONT_CACHE: dict[int, pygame.font.Font] = {}
_DIAL_CACHE: dict[tuple, pygame.Surface] = {}


def _font(size: int) -> pygame.font.Font:
    f = _FONT_CACHE.get(size)
    if f is None:
        f = pygame.font.Font(None, size)  # built-in bold sans; portable on the Pi
        _FONT_CACHE[size] = f
    return f


def _endpoint(cx: float, cy: float, angle_deg: float, length: float) -> tuple[float, float]:
    """Point at `length` px from centre, `angle_deg` clockwise from 12 o'clock."""
    a = math.radians(angle_deg)
    return (cx + math.sin(a) * length, cy - math.cos(a) * length)


def _hand_polygon(center: tuple[float, float], angle_deg: float,
                  length: float, base_w: float, scale: float = 1.0) -> list:
    """A tapered spindle: wide belly near the pivot, pointed tip, short tail."""
    a = math.radians(angle_deg)
    sin_a, cos_a = math.sin(a), math.cos(a)
    cx, cy = center
    bw = base_w * scale

    def pt(d, s):  # d = along the hand, s = perpendicular offset
        return (cx + d * sin_a + s * cos_a, cy - d * cos_a + s * sin_a)

    tail = length * 0.16 * scale
    return [
        pt(length, 0),
        pt(length * 0.80, bw * 0.30),
        pt(length * 0.28, bw * 0.50),
        pt(0, bw * 0.42),
        pt(-tail, 0),
        pt(0, -bw * 0.42),
        pt(length * 0.28, -bw * 0.50),
        pt(length * 0.80, -bw * 0.30),
    ]


def build_dial_surface(circle: Circle, theme: Theme) -> pygame.Surface:
    key = (id(theme), circle.cx, circle.cy, circle.r, theme.dial_markings)
    cached = _DIAL_CACHE.get(key)
    if cached is not None:
        return cached

    # Screen-sized transparent layer (the app blits it over the video).
    disp = pygame.display.get_surface()
    size = disp.get_size() if disp else (480, 800)
    surf = pygame.Surface(size, pygame.SRCALPHA)
    cx, cy, r = circle.cx, circle.cy, circle.r
    m = theme.dial_markings

    if m in ("ticks", "both"):
        count = max(1, theme.dial_count)
        for i in range(count):
            angle = i * (360.0 / count)
            major = (i % max(1, count // 12) == 0)
            r_in = r * (0.80 if major else 0.86)
            p1 = _endpoint(cx, cy, angle, r_in)
            p2 = _endpoint(cx, cy, angle, r * 0.92)
            pygame.draw.line(surf, theme.dial_color, p1, p2, 4 if major else 2)

    if m in ("numerals", "both"):
        # Faint minute micro-dots around the rim.
        dot_col = (*theme.dial_color, 55)
        for i in range(60):
            p = _endpoint(cx, cy, i * 6, r * 0.90)
            rad = 3 if i % 5 == 0 else 1
            pygame.draw.circle(surf, dot_col, (int(p[0]), int(p[1])), rad)
        # Big cardinal numerals at 12/3/6/9, dots for the other hours.
        num_font = _font(int(r * 0.34))
        cardinals = {12: "12", 3: "3", 6: "6", 9: "9"}
        for h in range(1, 13):
            angle = (h % 12) * 30
            if h in cardinals:
                txt = num_font.render(cardinals[h], True, theme.dial_color)
                pos = _endpoint(cx, cy, angle, r * 0.74)
                surf.blit(txt, txt.get_rect(center=pos))
            else:
                p = _endpoint(cx, cy, angle, r * 0.80)
                pygame.draw.circle(surf, (*theme.dial_color, 180),
                                   (int(p[0]), int(p[1])), 4)

    _DIAL_CACHE[key] = surf
    return surf


def draw_dial(surface: pygame.Surface, circle: Circle, theme: Theme) -> None:
    if theme.dial_markings == "none":
        return
    surface.blit(build_dial_surface(circle, theme), (0, 0))


def _draw_second(surface: pygame.Surface, center, angle, style: HandStyle, r: float) -> None:
    length = style.length * r
    end = _endpoint(*center, angle, length)
    tail = _endpoint(*center, angle + 180, length * 0.20)
    w = max(2, style.width)
    if style.glow:
        glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.line(glow, (*style.color, 70), tail, end, w + 4)
        surface.blit(glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    pygame.draw.line(surface, style.color, tail, end, w)
    # Counterweight disc behind the pivot.
    cw = _endpoint(*center, angle + 180, length * 0.16)
    pygame.draw.circle(surface, style.color, (int(cw[0]), int(cw[1])), max(4, w + 2))


def _draw_rounded_hand(surface: pygame.Surface, center, angle, style: HandStyle, r: float) -> None:
    """A Klydo-style baton hand with rounded caps instead of a pointed spindle."""
    length = style.length * r
    start = _endpoint(*center, angle + 180, length * 0.08)
    end = _endpoint(*center, angle, length)
    width = max(3, style.width)
    if style.glow:
        glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        pygame.draw.line(glow, (*style.color, 44), start, end, width + 8)
        pygame.draw.circle(glow, (*style.color, 44), (int(end[0]), int(end[1])), (width + 8) // 2)
        pygame.draw.circle(glow, (*style.color, 44), (int(start[0]), int(start[1])), (width + 8) // 2)
        surface.blit(glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
    pygame.draw.line(surface, style.color, start, end, width)
    cap = max(2, width // 2)
    pygame.draw.circle(surface, style.color, (int(end[0]), int(end[1])), cap)
    pygame.draw.circle(surface, style.color, (int(start[0]), int(start[1])), cap)


def draw_hands(surface: pygame.Surface, circle: Circle, theme: Theme,
               hms: tuple[float, float, float]) -> None:
    hour, minute, second = hms
    center = (circle.cx, circle.cy)
    r = circle.r

    specs = [
        (hour * 30.0, theme.hour),
        (minute * 6.0, theme.minute),
    ]
    specs = [(angle, style) for angle, style in specs if style.visible]

    spindle_specs = [(angle, style) for angle, style in specs if style.shape != "rounded"]
    rounded_specs = [(angle, style) for angle, style in specs if style.shape == "rounded"]

    # One shared additive-glow pass for the tapered hands.
    if any(s.glow for _, s in spindle_specs):
        glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        for angle, style in spindle_specs:
            if not style.glow:
                continue
            poly = _hand_polygon(center, angle, style.length * r, style.width, scale=1.4)
            pygame.draw.polygon(glow, (*style.color, 38), poly)
        surface.blit(glow, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    for angle, style in spindle_specs:
        poly = _hand_polygon(center, angle, style.length * r, style.width)
        pygame.draw.polygon(surface, style.color, poly)

    for angle, style in rounded_specs:
        _draw_rounded_hand(surface, center, angle, style, r)

    if theme.second.visible:
        _draw_second(surface, center, second * 6.0, theme.second, r)

    # Centre hub.
    pygame.draw.circle(surface, theme.accent, (int(circle.cx), int(circle.cy)), 8)
    pygame.draw.circle(surface, theme.background, (int(circle.cx), int(circle.cy)), 4)
