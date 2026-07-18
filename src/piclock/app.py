"""Main application: window/KMS setup, the render loop, and layer wiring.

Every frame: keep the fixture area black -> blit the current video frame into
the top circle -> apply a subtle live ambiance overlay inside the cutouts ->
draw the dial + real-time hands on top -> draw the swinging pendulum below.
Hands and pendulum are driven by the clock (TimeSource) and animation time,
never by the video, so they stay correct independently of the loop.
"""
from __future__ import annotations

import time

import pygame

from .config import Circle, Config
from .designs import Design, DesignSet
from .input import Dispatcher, InputRouter
from .layers.ambiance import Ambiance
from .layers.hands import draw_dial, draw_hands
from .layers.network_settings import NetworkSettingsPanel
from .layers.pendulum import PendulumLayer
from .layers.video import VideoLoop
from .network import NetworkClient, NetworkController
from .timesource import TimeSource


_CIRCLE_MASK_CACHE: dict[int, pygame.Surface] = {}
_ASPECT_SOURCE_CACHE: dict[int, pygame.Surface] = {}
_ASPECT_TARGET_CACHE: dict[tuple[int, int], pygame.Surface] = {}


def _circle_alpha_mask(diameter: int) -> pygame.Surface:
    mask = _CIRCLE_MASK_CACHE.get(diameter)
    if mask is None:
        mask = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255),
                           (diameter // 2, diameter // 2), diameter // 2)
        _CIRCLE_MASK_CACHE[diameter] = mask
    return mask


def _aspect_correct_circle(surface: pygame.Surface, circle: Circle,
                           y_scale: float) -> None:
    """Scale one complete circle layer around its unchanged screen centre."""
    if abs(y_scale - 1.0) < 0.0001 or circle.r <= 0:
        return

    diameter = circle.diameter
    source = _ASPECT_SOURCE_CACHE.get(diameter)
    if source is None:
        source = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        _ASPECT_SOURCE_CACHE[diameter] = source
    source.fill((0, 0, 0, 0))
    source.blit(surface, (circle.r - circle.cx, circle.r - circle.cy))
    source.blit(_circle_alpha_mask(diameter), (0, 0),
                special_flags=pygame.BLEND_RGBA_MULT)

    # Remove the uncorrected pixels, then place the corrected layer at the same centre.
    pygame.draw.circle(surface, (0, 0, 0), (circle.cx, circle.cy), circle.r + 2)
    target_h = max(1, round(diameter * y_scale))
    target_key = (diameter, target_h)
    corrected = _ASPECT_TARGET_CACHE.get(target_key)
    if corrected is None:
        corrected = pygame.Surface(target_key, pygame.SRCALPHA)
        _ASPECT_TARGET_CACHE[target_key] = corrected
    pygame.transform.smoothscale(source, target_key, corrected)
    surface.blit(corrected, corrected.get_rect(center=(circle.cx, circle.cy)))


class ClockApp:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.ts = TimeSource()
        self.running = True
        self.designs = DesignSet.scan(
            cfg.design_dirs,
            state_path=cfg.state_path,
            default_mode=cfg.design_mode,
            dial_diameters=cfg.dial_diameters,
            pendulum_diameters=cfg.pendulum_diameters,
        )

        pygame.init()
        pygame.display.set_caption("Pi Klydo Clock")
        self._init_display()
        if not cfg.windowed:
            pygame.mouse.set_visible(False)

        # Offscreen portrait canvas; rotated onto the display if needed.
        self.canvas = pygame.Surface(cfg.size).convert()

        self.dispatcher = Dispatcher()
        self.dispatcher.on("quit", self._quit)
        self.dispatcher.on("next_design", self._next_design)
        self.dispatcher.on("prev_design", self._prev_design)
        self.dispatcher.on("daily_design", self._daily_design)
        self.dispatcher.on("toggle_dim", self._toggle_dim)
        self.dispatcher.on("open_network_settings", self._open_network_settings)
        self.dispatcher.on("close_network_settings", self._close_network_settings)
        self.dispatcher.on("refresh_network_settings", self._refresh_network_settings)
        self.dispatcher.on("network_tap", self._network_tap)
        self.router = InputRouter(cfg, self.dispatcher)

        self.network_open = False
        self.network_controller = None
        self.network_panel = None
        if cfg.network.enabled:
            self.network_controller = NetworkController(
                NetworkClient(cfg.network.control_socket)
            )
            self.network_panel = NetworkSettingsPanel(
                cfg.top,
                cfg.circle_y_scale,
                cfg.network.max_visible_networks,
            )

        self.video = None
        self.pendulum = None
        self.ambiance = None
        self._bottom_source = None
        self._bottom_frame = None
        self.top_circle = cfg.top
        self.bottom_circle = cfg.bottom
        self._load_current()

    # --- display / rotation ---
    def _init_display(self) -> None:
        rot = self.cfg.rotate % 360
        if rot in (90, 270):
            disp_size = (self.cfg.height, self.cfg.width)  # landscape framebuffer
        else:
            disp_size = self.cfg.size
        flags = 0 if self.cfg.windowed else pygame.FULLSCREEN
        self.display = pygame.display.set_mode(disp_size, flags)

    def _present(self) -> None:
        rot = self.cfg.rotate % 360
        if rot == 0:
            self.display.blit(self.canvas, (0, 0))
        else:
            self.display.blit(pygame.transform.rotate(self.canvas, rot), (0, 0))
        pygame.display.flip()

    # --- design lifecycle ---
    def _load_current(self) -> None:
        if self.video is not None:
            self.video.close()
        design = self.designs.current
        if design is None:
            self.top_circle = self.cfg.top
            self.bottom_circle = self.cfg.bottom
            self.router.set_top_circle(self.top_circle)
            self.video = None
            self.pendulum = None
            self.ambiance = Ambiance(self.cfg.size, _placeholder_theme())
            self._bottom_source = None
            self._bottom_frame = None
            self._current_design = None
            return
        theme = design.theme
        self.top_circle = Circle(self.cfg.top.cx, self.cfg.top.cy,
                                 theme.dial_diameter // 2)
        self.bottom_circle = Circle(self.cfg.bottom.cx, self.cfg.bottom.cy,
                                    theme.bottom.diameter // 2)
        self.router.set_top_circle(self.top_circle)
        self.video = VideoLoop(design.loop_path, self.top_circle.diameter, theme.accent)
        self.pendulum = PendulumLayer(design.pendulum_path, self.bottom_circle, theme)
        self.ambiance = Ambiance(self.cfg.size, theme)
        self._bottom_source = None
        self._bottom_frame = None
        self._current_design = design

    def _next_design(self) -> None:
        self.designs.next()
        self._load_current()

    def _prev_design(self) -> None:
        self.designs.prev()
        self._load_current()

    def _daily_design(self) -> None:
        self.designs.daily()
        self._load_current()

    def _toggle_dim(self) -> None:
        self.cfg.dim = not self.cfg.dim

    def _open_network_settings(self) -> None:
        if self.network_panel is None or self.network_controller is None:
            return
        self.network_open = True
        self.router.set_settings_open(True)
        self.network_panel.open()
        self.network_controller.refresh()

    def _close_network_settings(self) -> None:
        if not self.network_open:
            return
        self.network_open = False
        self.router.set_settings_open(False)
        if self.network_panel is not None:
            self.network_panel.close()

    def _refresh_network_settings(self) -> None:
        if self.network_controller is not None:
            self.network_controller.refresh()

    def _network_tap(self, pos: tuple[float, float]) -> None:
        if self.network_panel is None or self.network_controller is None:
            return
        action = self.network_panel.handle_tap(pos, busy=self.network_controller.busy)
        if action == "close":
            self._close_network_settings()
        elif action == "refresh":
            self.network_controller.refresh()
        elif action == "start_hotspot":
            self.network_controller.start_hotspot()

    def _quit(self) -> None:
        self.running = False

    # --- main loop ---
    def run(self) -> None:
        clock = pygame.time.Clock()
        while self.running:
            self.router.process(pygame.event.get())

            t = time.monotonic()
            n = self.ts.now()
            sec = n.second + n.microsecond / 1_000_000.0
            minute = n.minute + sec / 60.0
            hms = ((n.hour % 12) + minute / 60.0, minute, sec)
            hour24 = n.hour + minute / 60.0

            self._render(t, hms, hour24)
            self._present()
            clock.tick(self.cfg.fps)

        if self.video is not None:
            self.video.close()
        if self.network_controller is not None:
            self.network_controller.close()
        pygame.quit()

    def _render(self, t: float, hms, hour24: float) -> None:
        cv = self.canvas
        cv.fill((0, 0, 0))

        design = self._current_design
        if design is not None:
            frame = self.video.get(t)
            if self.network_open:
                self._draw_network_settings(cv)
            else:
                cv.blit(frame, self.top_circle.topleft)
                self.ambiance.draw_circle_overlay(cv, self.top_circle, hour24, t)
                draw_dial(cv, self.top_circle, design.theme)
                draw_hands(cv, self.top_circle, design.theme, hms)
                self._draw_fixture_ring(cv, self.top_circle)
                _aspect_correct_circle(cv, self.top_circle, self.cfg.circle_y_scale)
            self._draw_bottom_backdrop(cv, frame, design.theme, hour24, t)
            self.pendulum.draw(cv, t)
            self._draw_fixture_ring(cv, self.bottom_circle)
            _aspect_correct_circle(cv, self.bottom_circle, self.cfg.circle_y_scale)
        elif self.network_open:
            self._draw_network_settings(cv)
        else:
            self._draw_no_designs(cv)

        if self.cfg.dim:
            overlay = pygame.Surface(self.cfg.size, pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            cv.blit(overlay, (0, 0))

    def _draw_network_settings(self, cv: pygame.Surface) -> None:
        if self.network_panel is None or self.network_controller is None:
            return
        self.network_panel.draw(cv, self.network_controller)
        self._draw_fixture_ring(cv, self.cfg.top)
        _aspect_correct_circle(cv, self.cfg.top, self.cfg.circle_y_scale)

    def _draw_bottom_backdrop(self, cv: pygame.Surface, frame: pygame.Surface,
                              theme, hour24: float, t: float) -> None:
        mode = theme.bottom.mode
        if mode == "none":
            return
        if mode == "solid":
            pygame.draw.circle(cv, theme.bottom.color,
                               (self.bottom_circle.cx, self.bottom_circle.cy),
                               self.bottom_circle.r)
        else:
            bottom_frame = self._scaled_bottom_frame(frame)
            cv.blit(bottom_frame, self.bottom_circle.topleft)
        self.ambiance.draw_circle_overlay(cv, self.bottom_circle, hour24, t, strength=0.75)

    def _draw_fixture_ring(self, cv: pygame.Surface, circle) -> None:
        if self.cfg.fixture_border_px <= 0:
            return
        pygame.draw.circle(cv, (0, 0, 0), (circle.cx, circle.cy), circle.r,
                           self.cfg.fixture_border_px)

    def _scaled_bottom_frame(self, frame: pygame.Surface) -> pygame.Surface:
        """Reuse the scaled bottom backdrop while the source video frame is unchanged."""
        if self._bottom_source is not frame or self._bottom_frame is None:
            bd = self.bottom_circle.diameter
            self._bottom_frame = pygame.transform.smoothscale(frame, (bd, bd))
            self._bottom_source = frame
        return self._bottom_frame

    def _draw_no_designs(self, cv: pygame.Surface) -> None:
        font = pygame.font.Font(None, 28)
        msg = font.render("No designs found in configured folders",
                          True, (200, 200, 200))
        cv.blit(msg, msg.get_rect(center=(self.cfg.width // 2, self.cfg.height // 2)))


def _placeholder_theme():
    from .designs import Theme
    return Theme.from_dict({"name": "placeholder"})


def run(cfg: Config) -> None:
    ClockApp(cfg).run()
