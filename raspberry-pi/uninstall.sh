#!/bin/bash
# Remove everything install.sh set up. Leaves the app folder itself alone.
set -uo pipefail

RUN_USER="${SUDO_USER:-$USER}"
RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"

echo "Removing Papa Ka TV services and autostart..."

sudo systemctl disable --now papa-ka-tv.service 2>/dev/null
sudo systemctl disable --now papa-ka-tv-refresh.timer 2>/dev/null
sudo rm -f /etc/systemd/system/papa-ka-tv.service \
           /etc/systemd/system/papa-ka-tv-refresh.service \
           /etc/systemd/system/papa-ka-tv-refresh.timer
sudo systemctl daemon-reload

rm -f "$RUN_HOME/.config/autostart/papa-ka-tv.desktop"
rm -f "$RUN_HOME/Desktop/PapaKaTV.desktop"

if [ -f "$RUN_HOME/.config/wayfire.ini" ]; then
    sed -i '/papakatv/d' "$RUN_HOME/.config/wayfire.ini"
fi

echo "Done."
echo ""
echo "Not undone (do these by hand if you want them back):"
echo "  - autologin / screen blanking : sudo raspi-config"
echo "  - 720p mode from tune-pi4.sh  : restore /boot/firmware/config.txt.papakatv.bak"
echo "  - the app folder itself       : still here, delete it yourself"
