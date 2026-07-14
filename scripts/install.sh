#!/usr/bin/env bash
# =============================================================================
#  Pi Klydo Clock installer (Raspberry Pi OS Bookworm, Pi 3).
#  Idempotent: safe to re-run. Run as root on the Pi:  sudo bash scripts/install.sh
#
#  Does NOT touch /boot/.../cmdline.txt (a bad edit bricks boot) — it prints the
#  exact tokens to add by hand. See boot/cmdline.txt.notes.
# =============================================================================
set -euo pipefail

REPO_SRC="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="/opt/piclock"
DEFAULT_USER="${SUDO_USER:-piclock}"
[ "$DEFAULT_USER" = "root" ] && DEFAULT_USER="piclock"
APP_USER="${PICLOCK_USER:-$DEFAULT_USER}"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m[!] %s\033[0m\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { echo "Run as root (sudo)."; exit 1; }

# --- locate the boot config dir (Bookworm vs older) ---
if [ -d /boot/firmware ]; then BOOTDIR=/boot/firmware; else BOOTDIR=/boot; fi
CONFIG_TXT="$BOOTDIR/config.txt"

say "Installing APT dependencies"
apt-get update -y
# SDL2 runtime (pygame-ce wheels link it), ffmpeg libs (PyAV), I2C tools, comitup.
apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip \
    libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-ttf-2.0-0 \
    libcairo2 \
    ffmpeg i2c-tools \
    comitup || warn "Some APT packages failed (comitup may need the comitup repo)."

say "Using '$APP_USER' as the renderer service user"
if ! id "$APP_USER" >/dev/null 2>&1; then
    useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
fi
APP_GROUP="$(id -gn "$APP_USER")"
APP_HOME="$(getent passwd "$APP_USER" | cut -d: -f6)"
[ -n "$APP_HOME" ] || APP_HOME="/home/$APP_USER"
# Groups needed for KMS/DRM, input, and the console VT.
for g in video render input tty i2c; do
    getent group "$g" >/dev/null 2>&1 && usermod -aG "$g" "$APP_USER" || true
done

say "Deploying app to $APP_DIR"
mkdir -p "$APP_DIR"
# Copy source, configuration, designs, and scripts. Skip the venv/legacy.
rsync -a --delete \
    --exclude '.venv' --exclude '__pycache__' --exclude 'legacy' \
    "$REPO_SRC/src" "$REPO_SRC/config" "$REPO_SRC/scripts" "$REPO_SRC/designs" \
    "$REPO_SRC/requirements.txt" "$REPO_SRC/README.md" \
    "$REPO_SRC/DESIGN_REVIEW.md" "$APP_DIR/"

say "Installing device configuration"
install -d -m 0755 /etc/piclock
if [ ! -f /etc/piclock/clock.json ]; then
    install -m 0644 "$REPO_SRC/config/device-clock.example.json" /etc/piclock/clock.json
else
    echo "Preserving existing /etc/piclock/clock.json overrides."
fi

say "Creating user design import folders"
install -d -m 0775 -o "$APP_USER" -g "$APP_GROUP" "$APP_HOME/piclock-designs"
if [ -d "$BOOTDIR" ]; then
    install -d -m 0755 "$BOOTDIR/piclock-designs"
fi

say "Creating Python virtualenv + installing requirements"
if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
    python3 -m venv "$APP_DIR/.venv"
fi
# piwheels provides prebuilt ARM wheels for pygame-ce/av (avoids long source builds).
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install \
    --extra-index-url https://www.piwheels.org/simple \
    -r "$APP_DIR/requirements.txt"

say "Ensuring at least one design exists"
if [ -z "$(ls -A "$APP_DIR/designs" 2>/dev/null || true)" ]; then
    "$APP_DIR/.venv/bin/python" "$APP_DIR/scripts/make_sample_design.py" \
        --dir "$APP_DIR/designs/testcard"
fi
install -d -o "$APP_USER" -g "$APP_GROUP" /var/lib/piclock
chown -R "$APP_USER":"$APP_GROUP" "$APP_DIR"

say "Enabling I2C + DS3231 RTC (removing fake-hwclock)"
raspi-config nonint do_i2c 0 || warn "raspi-config i2c toggle failed (enable manually)."
# The DS3231 must be the time source, so remove the software fake clock.
apt-get -y remove fake-hwclock || true
update-rc.d -f fake-hwclock remove 2>/dev/null || true
systemctl disable --now fake-hwclock 2>/dev/null || true
# The distro udev hook can clobber the RTC on boot; neutralise it if present.
if [ -f /lib/udev/hwclock-set ]; then
    sed -i 's/^\(\s*\)\(--systz\)/\1# \2/' /lib/udev/hwclock-set 2>/dev/null || true
fi

say "Appending config.txt snippet (idempotent)"
if ! grep -q "Pi Klydo Clock BEGIN" "$CONFIG_TXT" 2>/dev/null; then
    printf '\n' >> "$CONFIG_TXT"
    cat "$REPO_SRC/boot/config.txt.snippet" >> "$CONFIG_TXT"
    echo "Appended to $CONFIG_TXT"
else
    echo "config.txt already contains the Pi Klydo Clock block; skipping."
fi

say "Installing comitup provisioning config"
if [ -f "$REPO_SRC/provisioning/comitup.conf" ]; then
    install -m 0644 "$REPO_SRC/provisioning/comitup.conf" /etc/comitup.conf
    systemctl enable comitup 2>/dev/null || warn "comitup service not found (install comitup)."
fi

say "Installing systemd units"
tmp_service="$(mktemp)"
sed -e "s/^User=.*/User=$APP_USER/" \
    -e "s/^Group=.*/Group=$APP_GROUP/" \
    "$REPO_SRC/systemd/piclock-renderer.service" > "$tmp_service"
install -m 0644 "$tmp_service"  /etc/systemd/system/piclock-renderer.service
rm -f "$tmp_service"
install -m 0644 "$REPO_SRC/systemd/piclock-rtc-sync.service"  /etc/systemd/system/
install -m 0644 "$REPO_SRC/systemd/piclock-rtc-sync.timer"    /etc/systemd/system/
chmod +x "$APP_DIR/scripts/rtc_ntp_sync.sh"
systemctl daemon-reload
systemctl disable --now getty@tty1.service 2>/dev/null || true
systemctl enable piclock-renderer.service
systemctl enable piclock-rtc-sync.timer

cat <<EOF

$(say "Done")
Next steps (manual):
  1. Edit $BOOTDIR/cmdline.txt to add the portrait + fast-boot tokens.
     See boot/cmdline.txt.notes for the exact tokens and how to find the DSI
     connector name. (Not automated — a bad cmdline can prevent boot.)
  2. Wire the DS3231 to the I2C header (see README) and verify:
       i2cdetect -y 1        # expect a device at 0x68
       sudo hwclock -r       # should read a time
  3. Reboot. The clock starts before Wi-Fi; if no known network is found,
     join the "PiClock-XXXX" hotspot from your phone to configure Wi-Fi.

Useful:
  systemctl status piclock-renderer
  journalctl -u piclock-renderer -b
EOF
