#!/bin/bash
# Pull the latest Papa Ka TV and restart it.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

echo "Updating Papa Ka TV in $APP_DIR"

# refresh_ids.py rewrites index.html on every run, so the working tree is
# almost always dirty here and a plain pull would refuse. The local edits are
# just refreshed video IDs - the next refresh regenerates them.
if ! git diff --quiet -- index.html; then
    echo "  Discarding locally refreshed IDs in index.html (they will be re-fetched)"
    git checkout -- index.html
fi

git pull --ff-only

echo "  Restarting service..."
sudo systemctl restart papa-ka-tv.service

echo "  Refreshing video IDs..."
sudo systemctl start papa-ka-tv-refresh.service || echo "  (refresh had issues - see refresh_log.txt)"

echo "Done. Reload the browser on the Pi, or reboot."
