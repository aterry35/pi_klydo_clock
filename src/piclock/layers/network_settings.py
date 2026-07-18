"""Circular, touch-first network recovery panel for the upper aperture."""
from __future__ import annotations

import pygame

from ..config import Circle
from ..network import NetworkController


BG = (13, 17, 20)
PANEL = (24, 31, 35)
TEXT = (239, 241, 238)
MUTED = (153, 166, 169)
ACCENT = (224, 171, 80)
ERROR = (231, 111, 98)
SUCCESS = (94, 190, 142)


class NetworkSettingsPanel:
    def __init__(self, circle: Circle, y_scale: float, max_networks: int = 3):
        self.circle = circle
        self.y_scale = y_scale
        self.max_networks = max_networks
        self.confirming_reset = False
        cx, cy = circle.cx, circle.cy
        self.refresh_rect = pygame.Rect(cx - 145, cy + 55, 130, 36)
        self.close_rect = pygame.Rect(cx + 15, cy + 55, 130, 36)
        self.setup_rect = pygame.Rect(cx - 125, cy + 105, 250, 40)
        self.cancel_rect = pygame.Rect(cx - 135, cy + 70, 125, 40)
        self.confirm_rect = pygame.Rect(cx + 10, cy + 70, 125, 40)
        self.title_font = pygame.font.Font(None, 30)
        self.body_font = pygame.font.Font(None, 22)
        self.small_font = pygame.font.Font(None, 18)

    def open(self) -> None:
        self.confirming_reset = False

    def close(self) -> None:
        self.confirming_reset = False

    def handle_tap(self, pos: tuple[float, float], *, busy: bool = False) -> str | None:
        logical = self._logical_pos(pos)
        if self.confirming_reset:
            if self.cancel_rect.collidepoint(logical):
                self.confirming_reset = False
                return None
            if self.confirm_rect.collidepoint(logical) and not busy:
                self.confirming_reset = False
                return "start_hotspot"
            return None
        if self.refresh_rect.collidepoint(logical) and not busy:
            return "refresh"
        if self.close_rect.collidepoint(logical):
            return "close"
        if self.setup_rect.collidepoint(logical) and not busy:
            self.confirming_reset = True
        return None

    def _logical_pos(self, pos: tuple[float, float]) -> tuple[float, float]:
        if abs(self.y_scale - 1.0) < 0.0001:
            return pos
        return (
            pos[0],
            self.circle.cy + (pos[1] - self.circle.cy) / self.y_scale,
        )

    def draw(self, surface: pygame.Surface, controller: NetworkController) -> None:
        controller.poll()
        c = self.circle
        pygame.draw.circle(surface, BG, (c.cx, c.cy), c.r)
        pygame.draw.circle(surface, ACCENT, (c.cx, c.cy), c.r - 2, 2)
        if self.confirming_reset:
            self._draw_confirmation(surface, controller)
        else:
            self._draw_status(surface, controller)

    def _draw_status(self, surface: pygame.Surface, controller: NetworkController) -> None:
        c = self.circle
        snapshot = controller.snapshot
        self._center_text(surface, "NETWORK", self.title_font, TEXT, c.cy - 166)

        state_color = SUCCESS if snapshot.state.upper() in ("CONNECTED", "HOTSPOT") else MUTED
        state = snapshot.state.upper().replace("_", " ")
        if controller.busy:
            state = "UPDATING"
        self._center_text(surface, state or "UNKNOWN", self.body_font, state_color, c.cy - 128)

        if snapshot.hotspot:
            connection = f"Join {snapshot.connection or 'PiClock setup'}"
        else:
            connection = snapshot.connection or "No active connection"
        self._center_text(
            surface,
            _ellipsize(connection, 31),
            self.small_font,
            TEXT,
            c.cy - 103,
        )
        if snapshot.ip_address:
            self._center_text(
                surface,
                f"IP {snapshot.ip_address}",
                self.small_font,
                MUTED,
                c.cy - 82,
            )

        if controller.error:
            self._center_text(
                surface,
                _ellipsize(controller.error, 38),
                self.small_font,
                ERROR,
                c.cy - 56,
            )
        elif controller.message:
            self._center_text(
                surface,
                controller.message,
                self.small_font,
                SUCCESS,
                c.cy - 56,
            )
        else:
            self._left_text(surface, "NEARBY", self.small_font, MUTED, c.cx - 142, c.cy - 56)

        points = snapshot.access_points[: self.max_networks]
        if not points and not controller.busy and not controller.error:
            self._center_text(surface, "No networks found", self.small_font, MUTED, c.cy - 20)
        for index, point in enumerate(points):
            y = c.cy - 32 + index * 25
            color = SUCCESS if point.in_use else TEXT
            prefix = ">" if point.in_use else " "
            self._left_text(
                surface,
                f"{prefix} {_ellipsize(point.ssid, 22)}",
                self.small_font,
                color,
                c.cx - 145,
                y,
            )
            self._draw_signal(surface, c.cx + 112, y + 3, point.signal, color)

        self._button(surface, self.refresh_rect, "REFRESH", enabled=not controller.busy)
        self._button(surface, self.close_rect, "CLOSE")
        self._button(surface, self.setup_rect, "START SETUP HOTSPOT", accent=True,
                     enabled=not controller.busy)

    def _draw_confirmation(self, surface: pygame.Surface,
                           controller: NetworkController) -> None:
        c = self.circle
        self._center_text(surface, "NETWORK RECOVERY", self.title_font, TEXT, c.cy - 130)
        self._center_text(surface, "Remove saved Wi-Fi networks?", self.body_font,
                          TEXT, c.cy - 72)
        self._center_text(surface, "The PiClock setup hotspot", self.small_font,
                          MUTED, c.cy - 38)
        self._center_text(surface, "will start automatically.", self.small_font,
                          MUTED, c.cy - 17)
        self._button(surface, self.cancel_rect, "CANCEL")
        self._button(surface, self.confirm_rect, "RESET", accent=True,
                     enabled=not controller.busy)

    def _button(self, surface: pygame.Surface, rect: pygame.Rect, label: str,
                *, accent: bool = False, enabled: bool = True) -> None:
        fill = ACCENT if accent else PANEL
        if not enabled:
            fill = (42, 46, 48)
        pygame.draw.rect(surface, fill, rect, border_radius=6)
        if not accent:
            pygame.draw.rect(surface, (71, 80, 83), rect, 1, border_radius=6)
        color = BG if accent and enabled else (TEXT if enabled else MUTED)
        text = self.small_font.render(label, True, color)
        surface.blit(text, text.get_rect(center=rect.center))

    def _draw_signal(self, surface: pygame.Surface, x: int, y: int,
                     signal: int, color) -> None:
        active = max(1, min(4, (signal + 24) // 25))
        for index in range(4):
            height = 4 + index * 3
            bar_color = color if index < active else (61, 68, 71)
            pygame.draw.rect(surface, bar_color, (x + index * 5, y + 12 - height, 3, height))

    def _center_text(self, surface: pygame.Surface, value: str, font,
                     color, y: int) -> None:
        text = font.render(value, True, color)
        surface.blit(text, text.get_rect(center=(self.circle.cx, y)))

    @staticmethod
    def _left_text(surface: pygame.Surface, value: str, font,
                   color, x: int, y: int) -> None:
        surface.blit(font.render(value, True, color), (x, y))


def _ellipsize(value: str, maximum: int) -> str:
    value = value.strip()
    if len(value) <= maximum:
        return value
    return value[: max(1, maximum - 3)] + "..."
