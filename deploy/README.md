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

The script runs the designer tests, builds the Vite application, uploads a timestamped
release, validates the Caddy configuration, and atomically changes the `current`
symlink. Previous releases remain under `/var/www/pi-clock-designer/releases/` for
rollback.

The private key is excluded by `*.pem` in the repository `.gitignore` and must never be
copied into the web root or committed to Git.
