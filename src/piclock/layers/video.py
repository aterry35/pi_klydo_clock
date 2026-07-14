"""Background video layer: PyAV-decoded loop, masked into a circle.

Software H.264 decode is used deliberately -- at 480x480 it is cheap on a Pi 3
and avoids the fragile legacy hardware-decode / KMS-plane path. Frames are pulled
on the video's own timeline (not the render FPS), so a 15fps loop does not burn
30fps of decode work.

If PyAV is unavailable or the file is missing/broken, the layer falls back to a
flat accent-coloured disc so the app always renders.
"""
from __future__ import annotations

from typing import Optional

import pygame

try:
    import av  # PyAV
    _HAVE_AV = True
except Exception:  # pragma: no cover - import guard
    av = None
    _HAVE_AV = False


def _circle_mask(diameter: int) -> pygame.Surface:
    """A per-pixel-alpha surface: opaque inside the circle, transparent outside."""
    mask = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
    mask.fill((0, 0, 0, 0))
    pygame.draw.circle(mask, (255, 255, 255, 255),
                       (diameter // 2, diameter // 2), diameter // 2)
    return mask


class VideoLoop:
    """Decode a looping video into circular pygame surfaces."""

    def __init__(self, path: Optional[str], diameter: int,
                 fallback_color: tuple[int, int, int]):
        self.diameter = diameter
        self.mask = _circle_mask(diameter)
        self._fallback = self._make_fallback(diameter, fallback_color)
        self._surface: Optional[pygame.Surface] = None
        self._container = None
        self._decoder = None
        self._interval = 1.0 / 24.0
        self._next_frame_at = 0.0
        self._ok = False
        if path and _HAVE_AV:
            self._open(path)

    def _make_fallback(self, diameter: int,
                       color: tuple[int, int, int]) -> pygame.Surface:
        surf = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))
        pygame.draw.circle(surf, color, (diameter // 2, diameter // 2), diameter // 2)
        return surf

    def _open(self, path: str) -> None:
        try:
            self._container = av.open(path)
            stream = self._container.streams.video[0]
            stream.thread_type = "AUTO"
            rate = stream.average_rate or stream.base_rate or 24
            self._interval = 1.0 / float(rate)
            self._decoder = self._container.decode(video=0)
            self._ok = True
        except Exception:
            self._ok = False

    def _pull_frame(self) -> None:
        if not self._ok:
            return
        try:
            frame = next(self._decoder)
        except StopIteration:
            # Seamless loop: rewind to the start and continue.
            try:
                self._container.seek(0)
                self._decoder = self._container.decode(video=0)
                frame = next(self._decoder)
            except Exception:
                self._ok = False
                return
        except Exception:
            self._ok = False
            return
        self._surface = self._to_surface(frame)

    def _to_surface(self, frame) -> pygame.Surface:
        arr = frame.to_ndarray(format="rgb24")  # (h, w, 3) uint8
        h, w = arr.shape[0], arr.shape[1]
        surf = pygame.image.frombuffer(arr.tobytes(), (w, h), "RGB")
        if (w, h) != (self.diameter, self.diameter):
            surf = pygame.transform.smoothscale(surf, (self.diameter, self.diameter))
        surf = surf.convert_alpha()
        # Apply the circular mask (multiply alpha).
        surf.blit(self.mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return surf

    def get(self, now: float) -> pygame.Surface:
        """Return the current circular frame, advancing on the video's timeline."""
        if not self._ok:
            return self._fallback
        if self._surface is None or now >= self._next_frame_at:
            self._pull_frame()
            self._next_frame_at = now + self._interval
        return self._surface if self._surface is not None else self._fallback

    def close(self) -> None:
        if self._container is not None:
            try:
                self._container.close()
            except Exception:
                pass
