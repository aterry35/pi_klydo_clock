#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT/Tools/clock-design-creator-app/app"
KEY="${DESIGNER_KEY:-$ROOT/Amazon_certificate/Terryt.pem}"
TARGET="${DESIGNER_TARGET:-ubuntu@18.191.209.51}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
ARCHIVE="/tmp/pi-clock-designer-$STAMP.tar.gz"
REMOTE_ARCHIVE="/tmp/pi-clock-designer-$STAMP.tar.gz"
REMOTE_CADDYFILE="/tmp/pi-clock-designer-Caddyfile-$STAMP"

cleanup() {
    rm -f "$ARCHIVE"
}
trap cleanup EXIT

if [[ ! -f "$KEY" ]]; then
    printf 'Missing EC2 key: %s\n' "$KEY" >&2
    exit 1
fi
chmod 600 "$KEY"

(
    cd "$APP_DIR"
    npm test
    npm run build
    COPYFILE_DISABLE=1 tar --no-xattrs -czf "$ARCHIVE" -C dist .
)

scp -i "$KEY" "$ARCHIVE" "$TARGET:$REMOTE_ARCHIVE"
scp -i "$KEY" "$ROOT/deploy/Caddyfile" "$TARGET:$REMOTE_CADDYFILE"

ssh -i "$KEY" "$TARGET" "set -e
release=/var/www/pi-clock-designer/releases/$STAMP
sudo install -d -m 0755 \"\$release\"
sudo tar --no-same-owner -xzf '$REMOTE_ARCHIVE' -C \"\$release\"
sudo find \"\$release\" -type d -exec chmod 0755 {} +
sudo find \"\$release\" -type f -exec chmod 0644 {} +
sudo install -d -m 0755 /var/www/pi-clock-designer
sudo ln -sfn \"\$release\" /var/www/pi-clock-designer/current
sudo install -m 0644 '$REMOTE_CADDYFILE' /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
rm -f '$REMOTE_ARCHIVE' '$REMOTE_CADDYFILE'
printf 'Deployed release: %s\n' \"\$release\""

printf 'Designer URL: https://designer.18-191-209-51.sslip.io\n'
