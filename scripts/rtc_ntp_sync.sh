#!/usr/bin/env bash
# Write the system clock back to the DS3231 RTC, but ONLY once NTP has actually
# synchronised. With no network this is a no-op, so the DS3231 remains the trusted
# source and is never overwritten with drifted time.
set -euo pipefail

log() { logger -t piclock-rtc "$*"; echo "piclock-rtc: $*"; }

if ! command -v hwclock >/dev/null 2>&1; then
    log "hwclock not found; cannot write RTC"
    exit 0
fi

synced="$(timedatectl show -p NTPSynchronized --value 2>/dev/null || echo no)"
if [ "$synced" = "yes" ]; then
    if hwclock -w; then          # --systohc: system time -> RTC hardware
        log "NTP synchronised; wrote system time to DS3231"
    else
        log "hwclock -w failed"
    fi
else
    log "NTP not synchronised; leaving DS3231 untouched"
fi
