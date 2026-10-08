#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo ./deploy/install.sh" >&2
  exit 1
fi

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! systemctl is-active --quiet bouncer.service; then
  echo "Refusing deployment because bouncer.service is not active." >&2
  exit 1
fi

id serverwatch >/dev/null 2>&1 || useradd --system --home /opt/serverwatch --shell /usr/sbin/nologin serverwatch
install -d -o root -g root -m 0755 /opt/serverwatch /opt/serverwatch/app
install -d -o serverwatch -g serverwatch -m 0700 /var/lib/serverwatch /var/backups/serverwatch
install -d -o root -g serverwatch -m 0750 /etc/serverwatch

cp -a "${SOURCE_DIR}/serverwatch" "${SOURCE_DIR}/pyproject.toml" /opt/serverwatch/app/
python3 -m venv /opt/serverwatch/.venv
/opt/serverwatch/.venv/bin/pip install --disable-pip-version-check /opt/serverwatch/app

if [[ ! -f /etc/serverwatch/serverwatch.env ]]; then
  install -o root -g serverwatch -m 0640 "${SOURCE_DIR}/deploy/serverwatch.env.example" /etc/serverwatch/serverwatch.env
  echo "Created /etc/serverwatch/serverwatch.env. Configure credentials and SMTP before starting." >&2
fi

install -o root -g root -m 0644 "${SOURCE_DIR}/deploy/serverwatch.service" /etc/systemd/system/serverwatch.service
systemctl daemon-reload

if ! systemctl is-active --quiet bouncer.service; then
  echo "Bouncer changed state during deployment; ServerWatch was not started." >&2
  exit 1
fi

echo "Files installed. Next: configure /etc/serverwatch/serverwatch.env, then run:"
echo "  sudo systemctl enable --now serverwatch.service"
echo "The installer did not modify bouncer.service or Tailscale Serve."

