#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT/Tools/clock-design-creator-app/app"
KEY="${DESIGNER_KEY:-$ROOT/Amazon_certificate/Terryt.pem}"
TARGET="${DESIGNER_TARGET:-ubuntu@18.191.209.51}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
WEB_ARCHIVE="/tmp/pi-clock-designer-web-$STAMP.tar.gz"
APP_ARCHIVE="/tmp/pi-clock-community-$STAMP.tar.gz"
REMOTE_WEB_ARCHIVE="/tmp/pi-clock-designer-web-$STAMP.tar.gz"
REMOTE_APP_ARCHIVE="/tmp/pi-clock-community-$STAMP.tar.gz"
REMOTE_CADDYFILE="/tmp/pi-clock-designer-Caddyfile-$STAMP"

cleanup() {
    rm -f "$WEB_ARCHIVE" "$APP_ARCHIVE"
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
    COPYFILE_DISABLE=1 tar --no-xattrs -czf "$WEB_ARCHIVE" -C dist .
)
"$ROOT/.venv/bin/python" -m unittest discover -s "$ROOT/community/tests" -v
COPYFILE_DISABLE=1 tar --no-xattrs -czf "$APP_ARCHIVE" -C "$ROOT" community designs deploy

scp -i "$KEY" "$WEB_ARCHIVE" "$TARGET:$REMOTE_WEB_ARCHIVE"
scp -i "$KEY" "$APP_ARCHIVE" "$TARGET:$REMOTE_APP_ARCHIVE"
scp -i "$KEY" "$ROOT/deploy/Caddyfile" "$TARGET:$REMOTE_CADDYFILE"

ssh -i "$KEY" "$TARGET" "set -e
web_release=/var/www/pi-clock-designer/releases/$STAMP
app_release=/opt/pi-clock-community/releases/$STAMP
if ! dpkg -s python3-venv >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv
fi
if ! id piclock-community >/dev/null 2>&1; then
  sudo useradd --system --home /var/lib/pi-clock-community --shell /usr/sbin/nologin piclock-community
fi
if [ ! -f /etc/piclock-community.env ]; then
  sudo install -o root -g piclock-community -m 0640 /dev/null /etc/piclock-community.env
fi
sudo install -d -m 0755 \"\$web_release\" \"\$app_release\"
sudo tar --no-same-owner -xzf '$REMOTE_WEB_ARCHIVE' -C \"\$web_release\"
sudo tar --no-same-owner -xzf '$REMOTE_APP_ARCHIVE' -C \"\$app_release\"
sudo find \"\$web_release\" -type d -exec chmod 0755 {} +
sudo find \"\$web_release\" -type f -exec chmod 0644 {} +
sudo find \"\$app_release\" -type d -exec chmod 0755 {} +
sudo find \"\$app_release\" -type f -exec chmod 0644 {} +
sudo install -d -m 0755 /var/www/pi-clock-designer
sudo install -d -m 0755 /opt/pi-clock-community/releases
sudo install -d -o piclock-community -g piclock-community -m 0750 /var/lib/pi-clock-community
if [ ! -x /opt/pi-clock-community/venv/bin/python ]; then
  sudo python3 -m venv /opt/pi-clock-community/venv
fi
sudo /opt/pi-clock-community/venv/bin/pip install --disable-pip-version-check -r \"\$app_release/community/requirements.txt\"
sudo ln -sfn \"\$web_release\" /var/www/pi-clock-designer/current
sudo ln -sfn \"\$app_release\" /opt/pi-clock-community/current
cd \"\$app_release\"
sudo -u piclock-community env PICLOCK_DATA_DIR=/var/lib/pi-clock-community /opt/pi-clock-community/venv/bin/python -m community.seed --data /var/lib/pi-clock-community --designs \"\$app_release/designs\"
sudo install -m 0644 \"\$app_release/deploy/piclock-community.service\" /etc/systemd/system/piclock-community.service
sudo install -m 0644 \"\$app_release/deploy/piclock-community-backup.service\" /etc/systemd/system/piclock-community-backup.service
sudo install -m 0644 \"\$app_release/deploy/piclock-community-backup.timer\" /etc/systemd/system/piclock-community-backup.timer
sudo install -m 0644 '$REMOTE_CADDYFILE' /etc/caddy/Caddyfile
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl daemon-reload
sudo systemctl enable piclock-community.service piclock-community-backup.timer
sudo systemctl restart piclock-community.service
sudo systemctl start piclock-community-backup.timer
sudo systemctl reload caddy
curl --retry 30 --retry-connrefused --retry-delay 1 --retry-max-time 35 \
  --fail --silent http://127.0.0.1:8080/api/health
rm -f '$REMOTE_WEB_ARCHIVE' '$REMOTE_APP_ARCHIVE' '$REMOTE_CADDYFILE'
printf '\nWeb release: %s\nAPI release: %s\n' \"\$web_release\" \"\$app_release\""

printf 'Designer URL: https://designer.18-191-209-51.sslip.io\n'
