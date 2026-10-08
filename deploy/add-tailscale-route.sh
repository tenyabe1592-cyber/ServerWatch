#!/usr/bin/env bash
set -euo pipefail

STATUS_BEFORE="$(sudo tailscale serve status)"
if ! grep -Eq '^\|-- / proxy http://localhost:8501$' <<<"${STATUS_BEFORE}"; then
  echo "Refusing route change: verified Bouncer root route was not found." >&2
  exit 1
fi
if ! curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8765/healthz >/dev/null; then
  echo "Refusing route change: ServerWatch health check failed." >&2
  exit 1
fi

install -d -o serverwatch -g serverwatch -m 0700 /var/lib/serverwatch
printf '%s\n' "${STATUS_BEFORE}" | sudo tee /var/lib/serverwatch/tailscale-serve-before.txt >/dev/null

# This adds one path handler and intentionally never clears the existing Serve configuration.
sudo tailscale serve --bg --https=443 --set-path=/serverwatch http://127.0.0.1:8765

STATUS_AFTER="$(sudo tailscale serve status)"
grep -Eq '^\|-- / proxy http://localhost:8501$' <<<"${STATUS_AFTER}"
grep -Eq '/serverwatch.*(8765|127\.0\.0\.1)' <<<"${STATUS_AFTER}"
printf '%s\n' "${STATUS_AFTER}"
