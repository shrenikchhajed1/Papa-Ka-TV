#!/bin/bash
# =============================================================
#  Papa Ka TV - Raspberry Pi installer
#  Run once on the Pi:   bash raspberry-pi/install.sh
#  Safe to re-run; every step overwrites rather than appends.
# =============================================================
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI_DIR="$APP_DIR/raspberry-pi"
RUN_USER="${SUDO_USER:-$USER}"
RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"
PORT="${PORT:-8080}"

if [ "$(id -u)" -eq 0 ] && [ -z "${SUDO_USER:-}" ]; then
    echo "Run this as your normal user (it will call sudo itself), not as root." >&2
    exit 1
fi

echo "============================================"
echo "  Papa Ka TV - Raspberry Pi setup"
echo "============================================"
echo "  App directory : $APP_DIR"
echo "  Desktop user  : $RUN_USER"
echo "  Port          : $PORT"
echo ""

if [ ! -f "$APP_DIR/index.html" ]; then
    echo "ERROR: index.html not found in $APP_DIR" >&2
    echo "Run this script from inside the cloned Papa-Ka-TV folder." >&2
    exit 1
fi

MODEL="unknown"
[ -f /proc/device-tree/model ] && MODEL="$(tr -d '\0' < /proc/device-tree/model)"
echo "  Board         : $MODEL"
echo ""

# ── 1. Packages ─────────────────────────────────────────────
echo "[1/6] Checking packages..."
NEED=()
command -v python3 &>/dev/null || NEED+=(python3)
command -v curl &>/dev/null || NEED+=(curl)
if ! command -v chromium-browser &>/dev/null && ! command -v chromium &>/dev/null; then
    NEED+=(chromium-browser)
fi
if [ ${#NEED[@]} -gt 0 ]; then
    echo "      Installing: ${NEED[*]}"
    sudo apt-get update -qq
    sudo apt-get install -y "${NEED[@]}"
else
    echo "      All present."
fi

# ── 2. The web server, as a service ─────────────────────────
echo "[2/6] Installing papa-ka-tv.service..."
sudo tee /etc/systemd/system/papa-ka-tv.service >/dev/null <<UNIT
[Unit]
Description=Papa Ka TV web server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$APP_DIR
Environment=PORT=$PORT
ExecStart=/usr/bin/python3 $PI_DIR/serve.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

# ── 3. Live-stream ID refresh, at boot and nightly ──────────
echo "[3/6] Installing papa-ka-tv-refresh timer..."
sudo tee /etc/systemd/system/papa-ka-tv-refresh.service >/dev/null <<UNIT
[Unit]
Description=Refresh Papa Ka TV YouTube live stream IDs
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$RUN_USER
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 $APP_DIR/refresh_ids.py
# The news channels are the point of the refresh; never block boot on it.
TimeoutStartSec=180
UNIT

sudo tee /etc/systemd/system/papa-ka-tv-refresh.timer >/dev/null <<'UNIT'
[Unit]
Description=Refresh Papa Ka TV IDs at boot and every night

[Timer]
OnBootSec=30s
OnCalendar=*-*-* 04:30:00
Persistent=true

[Install]
WantedBy=timers.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now papa-ka-tv.service
sudo systemctl enable --now papa-ka-tv-refresh.timer

# ── 4. Kiosk autostart ──────────────────────────────────────
# Raspberry Pi OS has moved compositors twice (X11 -> wayfire -> labwc), so
# install into whichever the session actually uses. XDG autostart is honoured
# by all three, and is the one that survives another switch.
echo "[4/6] Setting up kiosk autostart..."
install -d -o "$RUN_USER" -g "$RUN_USER" "$RUN_HOME/.config/autostart"
sudo -u "$RUN_USER" tee "$RUN_HOME/.config/autostart/papa-ka-tv.desktop" >/dev/null <<DESKTOP
[Desktop Entry]
Type=Application
Name=Papa Ka TV
Exec=$PI_DIR/kiosk.sh
X-GNOME-Autostart-enabled=true
DESKTOP

if [ -f "$RUN_HOME/.config/wayfire.ini" ]; then
    echo "      wayfire detected - adding autostart entry"
    sudo -u "$RUN_USER" python3 - "$RUN_HOME/.config/wayfire.ini" "$PI_DIR/kiosk.sh" <<'PY'
import sys
ini, cmd = sys.argv[1], sys.argv[2]
text = open(ini).read()
if "papakatv" not in text:
    if "[autostart]" in text:
        text = text.replace("[autostart]", f"[autostart]\npapakatv = {cmd}", 1)
    else:
        text = text.rstrip() + f"\n\n[autostart]\npapakatv = {cmd}\n"
    open(ini, "w").write(text)
PY
fi

# ── 5. Screen blanking and autologin ────────────────────────
echo "[5/6] Disabling screen blanking / enabling autologin..."
if command -v raspi-config &>/dev/null; then
    # B4 = desktop, autologin as the current user.
    sudo raspi-config nonint do_boot_behaviour B4 || \
        echo "      (autologin step skipped - set it yourself via raspi-config)"
    sudo raspi-config nonint do_blanking 1 || \
        echo "      (blanking step skipped)"
else
    echo "      raspi-config not found - skipping (not a Raspberry Pi OS image?)"
fi

# ── 6. Desktop icon, as a way back in ───────────────────────
echo "[6/6] Adding a desktop shortcut..."
if [ -d "$RUN_HOME/Desktop" ]; then
    sudo -u "$RUN_USER" tee "$RUN_HOME/Desktop/PapaKaTV.desktop" >/dev/null <<DESKTOP
[Desktop Entry]
Type=Application
Name=Papa Ka TV
Comment=Open Papa Ka TV
Exec=$PI_DIR/kiosk.sh
Terminal=false
DESKTOP
    chmod +x "$RUN_HOME/Desktop/PapaKaTV.desktop"
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo ""
echo "============================================"
echo "  Done."
echo ""
echo "  On this Pi     : http://localhost:$PORT/index.html"
[ -n "$IP" ] && echo "  On the network : http://$IP:$PORT/index.html"
echo ""
echo "  Reboot to see it come up by itself:  sudo reboot"
echo ""
echo "  Status : systemctl status papa-ka-tv"
echo "  Logs   : journalctl -u papa-ka-tv -f"
if [[ "$MODEL" == *"Pi 4"* ]] || [[ "$MODEL" == *"Pi 3"* ]]; then
echo ""
echo "  NOTE: this is a $MODEL - run raspberry-pi/tune-pi4.sh"
echo "        to drop the screen to 720p, or video will stutter."
fi
echo "============================================"
