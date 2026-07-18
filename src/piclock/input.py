"""Input handling: touch (primary) + keyboard (fallback), via an action dispatcher.

Semantic actions ("next_design", "prev_design", "daily_design", "toggle_dim", "quit") are decoupled
from the raw events. The app registers handlers on the dispatcher; touch/keys just
emit actions. This is deliberately structured so an on-screen setup UI can be added
later by registering more actions and hit-regions -- without touching this file's
event plumbing.
"""
from __future__ import annotations

import time
from typing import Callable

import pygame

from .config import Config

SWIPE_THRESHOLD_FRAC = 0.12  # fraction of screen width to count as a swipe
LONG_PRESS_MOVE_FRAC = 0.04


class Dispatcher:
    def __init__(self):
        self._handlers: dict[str, Callable[..., None]] = {}

    def on(self, action: str, handler: Callable[..., None]) -> None:
        self._handlers[action] = handler

    def emit(self, action: str, *args) -> None:
        h = self._handlers.get(action)
        if h:
            h(*args)


class InputRouter:
    def __init__(self, cfg: Config, dispatcher: Dispatcher):
        self.cfg = cfg
        self.d = dispatcher
        self._top_circle = cfg.top
        self._touch_start: tuple[float, float] | None = None
        self._touch_current: tuple[float, float] | None = None
        self._touch_started_at: float | None = None
        self._long_press_fired = False
        self._settings_open = False

    def set_top_circle(self, circle) -> None:
        self._top_circle = circle

    def set_settings_open(self, is_open: bool) -> None:
        self._settings_open = is_open
        self._reset_press()

    def _norm_touch(self, nx: float, ny: float) -> tuple[float, float]:
        """Map a device-normalised finger coord (0..1) to screen pixels, applying the
        independent touch rotation. Tune `touch_rotate` (or a libinput matrix) on-device."""
        r = self.cfg.touch_rotate % 360
        if r == 90:
            nx, ny = ny, 1.0 - nx
        elif r == 180:
            nx, ny = 1.0 - nx, 1.0 - ny
        elif r == 270:
            nx, ny = 1.0 - ny, nx
        return (nx * self.cfg.width, ny * self.cfg.height)

    def _in_top_circle(self, pos: tuple[float, float]) -> bool:
        c = self._top_circle
        dx, dy = pos[0] - c.cx, pos[1] - c.cy
        if c.r <= 0:
            return False
        ry = max(1.0, c.r * self.cfg.circle_y_scale)
        return (dx / c.r) ** 2 + (dy / ry) ** 2 <= 1.0

    def _handle_release(self, start, end) -> None:
        """Tap or swipe on the top circle cycles designs."""
        if start is None:
            return
        if not self._in_top_circle(start):
            return
        dx = end[0] - start[0]
        if abs(dx) >= self.cfg.width * SWIPE_THRESHOLD_FRAC:
            self.d.emit("next_design" if dx < 0 else "prev_design")  # swipe left = next
        else:
            self.d.emit("next_design")  # tap

    def _begin_press(self, pos: tuple[float, float], now: float) -> None:
        self._touch_start = pos
        self._touch_current = pos
        self._touch_started_at = now
        self._long_press_fired = False

    def _move_press(self, pos: tuple[float, float]) -> None:
        if self._touch_start is not None:
            self._touch_current = pos

    def _end_press(self, end: tuple[float, float]) -> None:
        start = self._touch_start
        if start is None:
            return
        if self._long_press_fired:
            self._reset_press()
            return
        if self._settings_open:
            self.d.emit("network_tap", end)
        else:
            self._handle_release(start, end)
        self._reset_press()

    def _reset_press(self) -> None:
        self._touch_start = None
        self._touch_current = None
        self._touch_started_at = None
        self._long_press_fired = False

    def _check_long_press(self, now: float) -> None:
        if (
            self._settings_open
            or not self.cfg.network.enabled
            or self._long_press_fired
            or self._touch_start is None
            or self._touch_current is None
            or self._touch_started_at is None
        ):
            return
        if not self._in_top_circle(self._touch_start):
            return
        dx = abs(self._touch_current[0] - self._touch_start[0])
        dy = abs(self._touch_current[1] - self._touch_start[1])
        movement_limit = self.cfg.width * LONG_PRESS_MOVE_FRAC
        if max(dx, dy) > movement_limit:
            return
        if now - self._touch_started_at >= self.cfg.network.long_press_seconds:
            self._long_press_fired = True
            self.d.emit("open_network_settings")

    def process(self, events, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        for e in events:
            if e.type == pygame.QUIT:
                self.d.emit("quit")

            # --- Keyboard (fallback) ---
            elif e.type == pygame.KEYDOWN:
                if self._settings_open:
                    if e.key in (pygame.K_ESCAPE, pygame.K_q):
                        self.d.emit("close_network_settings")
                    elif e.key == pygame.K_r:
                        self.d.emit("refresh_network_settings")
                elif e.key in (pygame.K_ESCAPE, pygame.K_q):
                    self.d.emit("quit")
                elif e.key == pygame.K_RIGHT:
                    self.d.emit("next_design")
                elif e.key == pygame.K_LEFT:
                    self.d.emit("prev_design")
                elif e.key == pygame.K_d:
                    self.d.emit("daily_design")
                elif e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    self.d.emit("toggle_dim")

            # --- Touch (primary) ---
            elif e.type == pygame.FINGERDOWN:
                self._begin_press(self._norm_touch(e.x, e.y), now)
            elif e.type == pygame.FINGERMOTION:
                self._move_press(self._norm_touch(e.x, e.y))
            elif e.type == pygame.FINGERUP:
                end = self._norm_touch(e.x, e.y)
                self._end_press(end)

            # --- Mouse (so touch UX is testable on the dev Mac) ---
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self._begin_press(e.pos, now)
            elif e.type == pygame.MOUSEMOTION:
                self._move_press(e.pos)
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                self._end_press(e.pos)

        self._check_long_press(now)
