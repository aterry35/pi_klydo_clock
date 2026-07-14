"""The single source of truth for wall-clock time.

On the Pi the system clock is backed by the DS3231 RTC (hwclock reads it at boot,
see systemd/piclock-rtc-sync.service), so `datetime.now()` is already correct with
no network. The renderer reads time from HERE every frame and derives hand angles
from it -- crucially NOT from the video frame counter -- so the hands stay correct
independently of whatever the design loop is doing (the Klydo requirement).
"""
from __future__ import annotations

from datetime import datetime


class TimeSource:
    """Wall-clock time with sub-second precision for a smooth second hand."""

    def now(self) -> datetime:
        return datetime.now()

    def hms(self) -> tuple[float, float, float]:
        """Return (hour[0-12), minute[0-60), second[0-60)) as floats.

        Sub-second precision is folded into the second so the second hand can
        sweep smoothly, and minute/hour advance continuously.
        """
        n = self.now()
        sec = n.second + n.microsecond / 1_000_000.0
        minute = n.minute + sec / 60.0
        hour = (n.hour % 12) + minute / 60.0
        return hour, minute, sec
