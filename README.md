# ServerWatch M1

ServerWatch M1 is a bounded, single-server monitoring application for `bouncer-srv`. It implements exactly the approved six capabilities:

1. CPU, RAM, and disk monitoring with failed/stale collection detection.
2. A persistent current-and-historical dashboard.
3. Ubuntu service and HTTP endpoint health with `healthy`, `unhealthy`, and `unknown` states.
4. Deterministic threshold/service alerts with one open incident per rule to prevent flooding.
5. Persistent incident, resolution, acknowledgement, and alert history.
6. One SMTP notification channel with one bounded retry and visible delivery failures.

Release safeguards included in M1 are HTTP Basic authentication, Tailscale-private HTTPS deployment, SQLite backup/restore, systemd recovery, fail-closed health states, and controlled acceptance checks. ServerWatch can observe only conditions while the server and ServerWatch are operational; external total-outage detection is explicitly outside M1.

## Local verification

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest
SERVERWATCH_TEST_MODE=true SERVERWATCH_DB_PATH=./serverwatch.db SERVERWATCH_ROOT_PATH= uvicorn serverwatch.app:create_app --factory --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`. Test mode disables authentication only when no password hash is configured; it must never be set in production.

## Deployment preparation for `/opt/serverwatch`

The deployment intentionally creates a new `serverwatch.service`; it neither edits nor restarts `bouncer.service`.

1. Copy this release directory to `bouncer-srv`.
2. Run `sudo bash deploy/install.sh`. The installer refuses to proceed if `bouncer.service` is not active.
3. Generate a password hash as the service user after installation:

   ```bash
   sudo -u serverwatch /opt/serverwatch/.venv/bin/python -m serverwatch hash-password
   ```

4. Put the hash and one SMTP channel configuration in `/etc/serverwatch/serverwatch.env`; keep permissions at `0640 root:serverwatch`.
5. Start only the new service:

   ```bash
   sudo systemctl enable --now serverwatch.service
   curl --fail http://127.0.0.1:8765/healthz
   ```

6. Sign in locally through an SSH tunnel and run a test notification. Confirm its `sent` record in the dashboard. Controlled threshold and service-failure tests should be performed before production acceptance.
7. Only after the local health check passes, run `sudo bash deploy/add-tailscale-route.sh`. It verifies the existing Bouncer `/` route, records the before-state, adds `/serverwatch`, and verifies both handlers. It never calls `tailscale serve reset`.
8. Run `sudo bash deploy/acceptance.sh`, then sign in at `https://bouncer-srv.taild4070e.ts.net/serverwatch/`.

The additive route command prepared for Tailscale 1.102.4 is:

```bash
sudo tailscale serve --bg --https=443 --set-path=/serverwatch http://127.0.0.1:8765
```

## Backup and restore

Create an online, integrity-checked backup:

```bash
sudo -u serverwatch /opt/serverwatch/.venv/bin/python -m serverwatch.backup
```

Restore is deliberately explicit. Stop ServerWatch, preserve the current database separately, restore, fix ownership, and start the service:

```bash
sudo systemctl stop serverwatch.service
sudo -u serverwatch /opt/serverwatch/.venv/bin/python -m serverwatch.restore /var/backups/serverwatch/serverwatch-TIMESTAMP.db --replace
sudo chown serverwatch:serverwatch /var/lib/serverwatch/serverwatch.db
sudo systemctl start serverwatch.service
```

Then run the acceptance script and verify historical samples/incidents in the UI. The automated suite exercises backup integrity and restore into a fresh database.

## Production acceptance status

The application and deployment assets are ready and automated offline tests can verify deterministic behavior. Production is not complete until deployment on `bouncer-srv` demonstrates all six capabilities using real measurements, a controlled failure, a delivered SMTP test, restart recovery, backup/restore, private HTTPS access, and continued Bouncer health.

No Docker, AI incident analysis, multi-server support, automated remediation, custom rule builder, or additional integration is included.
