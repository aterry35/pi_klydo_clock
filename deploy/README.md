# Designer deployment

The production designer is served by Caddy at:

<https://designer.18-191-209-51.sslip.io>

The hostname uses `sslip.io` DNS to resolve to the EC2 public IP. Caddy obtains and
renews the TLS certificate automatically. Ports 80 and 443 must be allowed by the
instance's EC2 security group.

## Deploy an update

From the repository root:

```bash
DESIGNER_KEY=Amazon_certificate/Terryt.pem ./scripts/deploy_designer_ec2.sh
```

The script runs the designer and API tests, builds the Vite application, uploads
timestamped frontend and backend releases, seeds the bundled designs into the
community gallery, validates Caddy, and atomically changes each `current` symlink.
Previous frontend releases remain under `/var/www/pi-clock-designer/releases/` and
backend releases under `/opt/pi-clock-community/releases/` for rollback.

## Services and data

```text
piclock-community.service          Gunicorn/Flask API on 127.0.0.1:8080
piclock-community-backup.timer     daily SQLite backup with 14-day retention
/var/lib/pi-clock-community/       database, uploaded ZIPs/previews, and backups
/opt/pi-clock-community/current/   active API release
/var/www/pi-clock-designer/current active frontend release
/etc/piclock-community.env       private agent token hash and agent identity
```

Caddy serves the frontend and proxies `/api/*` to Gunicorn. Check the deployed
service with:

```bash
curl https://designer.18-191-209-51.sslip.io/api/health
ssh -i Amazon_certificate/Terryt.pem ubuntu@18.191.209.51 \
  'sudo systemctl status piclock-community --no-pager'
```

The EC2 instance is the only application host during the soft opening. Backups are
local to that instance, so copy them off-host before treating the service as durable.
See `COMMUNITY_SOFT_OPENING.md` for current limits and operating steps.

Promote an existing account without handling its password:

```bash
cd /opt/pi-clock-community/current
sudo -u piclock-community env PICLOCK_DATA_DIR=/var/lib/pi-clock-community \
  /opt/pi-clock-community/venv/bin/python -m community.manage promote \
  --email administrator@example.com
```

The private key is excluded by `*.pem` in the repository `.gitignore` and must never be
copied into the web root or committed to Git.
