#!/bin/bash
# Pi 4 / Pi 3 only: force the screen to 720p.
# A Pi 4 decodes YouTube's VP9 1080p in software and drops most of the frames.
# At 720p the picture is steady, and on a TV across the room the difference in
# sharpness is far less noticeable than the stutter.
set -euo pipefail

MODEL="unknown"
[ -f /proc/device-tree/model ] && MODEL="$(tr -d '\0' < /proc/device-tree/model)"
echo "Board: $MODEL"

if [[ "$MODEL" == *"Pi 5"* ]]; then
    echo ""
    echo "This is a Pi 5 - it decodes 1080p fine. You do not need this script."
    echo "Re-run with FORCE=1 if you want 720p anyway."
    [ "${FORCE:-0}" != "1" ] && exit 0
fi

CONFIG=/boot/firmware/config.txt
[ -f "$CONFIG" ] || CONFIG=/boot/config.txt
[ -f "$CONFIG" ] || { echo "No config.txt found" >&2; exit 1; }

echo "Editing $CONFIG (backup: ${CONFIG}.papakatv.bak)"
sudo cp "$CONFIG" "${CONFIG}.papakatv.bak"

# Drop any block we wrote before, so re-running does not stack duplicates.
sudo sed -i '/# --- Papa Ka TV 720p ---/,/# --- end Papa Ka TV ---/d' "$CONFIG"

sudo tee -a "$CONFIG" >/dev/null <<'CFG'
# --- Papa Ka TV 720p ---
hdmi_group=1
hdmi_mode=4
hdmi_drive=2
disable_overscan=1
# --- end Papa Ka TV ---
CFG

echo ""
echo "Done. Reboot to apply:  sudo reboot"
echo "To undo:  sudo cp ${CONFIG}.papakatv.bak $CONFIG && sudo reboot"
