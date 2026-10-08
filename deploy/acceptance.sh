#!/usr/bin/env bash
set -euo pipefail

systemctl is-active --quiet bouncer.service
systemctl is-active --quiet serverwatch.service
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8501/ >/dev/null
curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8765/healthz >/dev/null

SERVE_STATUS="$(sudo tailscale serve status)"
grep -Eq '^\|-- / proxy http://localhost:8501$' <<<"${SERVE_STATUS}"
grep -Eq '/serverwatch.*(8765|127\.0\.0\.1)' <<<"${SERVE_STATUS}"

curl --fail --silent --show-error --max-time 10 https://bouncer-srv.taild4070e.ts.net/ >/dev/null
curl --fail --silent --show-error --max-time 10 https://bouncer-srv.taild4070e.ts.net/serverwatch/healthz >/dev/null

echo "PASS: Bouncer and ServerWatch services, loopback endpoints, and private routes are healthy."

