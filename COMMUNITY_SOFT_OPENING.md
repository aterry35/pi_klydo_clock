# Community Soft Opening

The first public release uses the existing EC2 instance and designer hostname:

<https://designer.18-191-209-51.sslip.io>

The root URL is the public project landing page. The designer is at `/designer`,
the community gallery is at `/community`, the artist guide is at `/artists`, the
DIY Raspberry Pi guide is at `/build`, and administration is at `/admin`.

It is intentionally a low-cost validation release. The browser designer remains
usable without an account. The Community page adds public browsing and downloads,
while registration is required for design submission, likes, and comments.

## Included in this release

- Artist registration and sign-in with server-side sessions.
- Editable artist name and required dial watermark metadata.
- Validated ZIP and preview upload from the designer.
- Pre-publication review: new submissions remain private until an administrator
  approves them.
- Immediate administrator email for each new submission, with its preview and a
  secure link to the review queue.
- Searchable gallery with newest, most liked, and most downloaded sorting.
- Design detail, comments, likes, and direct package downloads.
- Community reporting for copyright, inappropriate content, spam, broken packages,
  and other issues.
- Private administration for report resolution, design hide/restore, artist
  suspend/restore, and moderation audit history.
- Bundled repository designs seeded into the gallery without changing `designs/`.
- Upload size limits, ZIP path validation, request rate limits, CSRF protection,
  secure cookies, and same-origin checks.
- Daily local SQLite backups retained for 14 days.

## Current limits

- Accounts do not yet have email verification or password recovery.
- SQLite, packages, previews, and backups live on one EC2 instance.
- Local backups do not protect against instance or volume loss.
- No CDN, object storage, autoscaling, or multi-instance API is configured.

These limits are acceptable for a controlled soft opening, but not for an unmonitored
large public launch. Keep the existing AWS budget alerts enabled and monitor storage,
traffic, service logs, and the pending-review queue. Existing designs that were
already published before this workflow was introduced remain published.

## Operator checks

```bash
curl https://designer.18-191-209-51.sslip.io/api/health
ssh -i Amazon_certificate/Terryt.pem ubuntu@18.191.209.51 \
  'sudo systemctl status piclock-community caddy --no-pager'
ssh -i Amazon_certificate/Terryt.pem ubuntu@18.191.209.51 \
  'sudo journalctl -u piclock-community -n 100 --no-pager'
ssh -i Amazon_certificate/Terryt.pem ubuntu@18.191.209.51 \
  'sudo systemctl status piclock-admin-submissions.timer --no-pager'
ssh -i Amazon_certificate/Terryt.pem ubuntu@18.191.209.51 \
  'sudo du -sh /var/lib/pi-clock-community'
```

Backups are stored in `/var/lib/pi-clock-community/backups/`. Copy them to another
machine or S3 before inviting a wider audience.

## Promotion criteria

Move uploads and previews to S3, add off-host database backups, email verification,
password recovery, and error monitoring before a broad launch. PostgreSQL becomes
appropriate when traffic or concurrent writes outgrow the single-instance SQLite
service. If review volume grows, add trusted-artist approval rules or a multi-admin
queue instead of bypassing pre-publication review globally.
