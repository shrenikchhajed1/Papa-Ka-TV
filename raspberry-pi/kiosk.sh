#!/bin/bash
# Launches Chromium fullscreen on Papa Ka TV. Started by the desktop session,
# not by systemd, because it needs the logged-in user's display.
set -uo pipefail

PORT="${PORT:-8080}"
URL="http://localhost:${PORT}/index.html"

# Pick whichever Chromium this Raspberry Pi OS release ships.
BROWSER=""
for candidate in chromium-browser chromium; do
    if command -v "$candidate" &>/dev/null; then
        BROWSER="$candidate"
        break
    fi
done

if [ -z "$BROWSER" ]; then
    echo "kiosk: no chromium found; run raspberry-pi/install.sh first" >&2
    exit 1
fi

# Wait for the server to answer. It is a systemd service starting in parallel
# with the desktop, so on a cold boot the desktop usually wins the race.
for _ in $(seq 1 30); do
    if curl -sf -o /dev/null "$URL"; then
        break
    fi
    sleep 1
done

# Stop the screen blanking mid-song. Wayland (labwc/wayfire) and X11 each need
# their own call, and only one of them will exist on any given Pi.
command -v wlopm &>/dev/null && wlopm --on '*' 2>/dev/null
if [ -n "${DISPLAY:-}" ] && command -v xset &>/dev/null; then
    xset s off -dpms 2>/dev/null
fi

# A hard power cut leaves crash flags behind, and Chromium then opens a
# "restore pages?" bar over the video that Papa would have to dismiss.
PROFILE="$HOME/.config/chromium/Default/Preferences"
if [ -f "$PROFILE" ]; then
    sed -i 's/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PROFILE" 2>/dev/null
    sed -i 's/"exited_cleanly":false/"exited_cleanly":true/' "$PROFILE" 2>/dev/null
fi

exec "$BROWSER" \
    --kiosk \
    --start-fullscreen \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-features=Translate,TranslateUI \
    --no-first-run \
    --check-for-update-interval=31536000 \
    --autoplay-policy=no-user-gesture-required \
    "$URL"
