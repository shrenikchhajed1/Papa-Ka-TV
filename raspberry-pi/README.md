# Papa Ka TV on a Raspberry Pi

Turns a Raspberry Pi into a dedicated Papa Ka TV box: plug in the power, and
after about 40 seconds the TV shows the app fullscreen. No login, no desktop,
no keyboard needed — just a mouse to click channels and songs.

## What you need

| | |
|---|---|
| **Raspberry Pi 5 (4GB)** | The Pi 4 works but needs `tune-pi4.sh` (see below) |
| **Official 27W USB-C power supply** | Not a phone charger — see the warning below |
| **microSD card, 32GB, A2-rated** | Size barely matters; see "About storage" |
| **micro-HDMI to HDMI cable** | The Pi's own port is *micro*-HDMI, not full size |
| **Active cooler** | The Pi 5 throttles without one when playing video |
| **A mouse** | The only thing Papa needs to touch |
| **Wired ethernet, if you can** | Live news over wifi is the usual cause of buffering |

### About storage

**The songs are not stored on the Pi.** Every channel and every song is a
YouTube embed streamed live over the internet — the 600 songs in the app are
just video IDs, a few kilobytes of text. The card only holds the operating
system and the app itself, about 5GB in total.

So a bigger card buys you nothing here, and the Pi needs a **permanent
internet connection** to play anything at all. Get a 32GB A2-rated card from a
brand you recognise: a slow or fake card is the single most common cause of a
Pi that boots slowly or corrupts itself.

### The power supply is not optional

An underpowered supply — a phone charger, a laptop USB port — causes
undervoltage throttling and random reboots. On this app that looks exactly
like *"the video keeps stopping, the app is broken"*. Buy the official 27W
supply for a Pi 5, or the official 15W one for a Pi 4.

## Install

On the Pi, with Raspberry Pi OS (64-bit, Desktop) already running:

```bash
git clone https://github.com/shrenikchhajed1/Papa-Ka-TV.git
cd Papa-Ka-TV
bash raspberry-pi/install.sh
sudo reboot
```

After the reboot it comes up on its own, fullscreen.

## What the installer does

1. Installs Chromium, Python 3 and curl if missing
2. **`papa-ka-tv.service`** — serves the app on port 8080, restarts if it dies
3. **`papa-ka-tv-refresh.timer`** — re-fetches the news live-stream IDs 30
   seconds after boot and again at 4:30 AM nightly, so channels don't go stale
4. **Kiosk autostart** — Chromium fullscreen on login, installed for whichever
   compositor the Pi uses (labwc, wayfire, or X11)
5. **Autologin + no screen blanking** — boots to the app, never sleeps
6. **A desktop shortcut** — a way back in if you ever exit kiosk mode

## The other scripts

| Script | What it's for |
|---|---|
| `tune-pi4.sh` | **Pi 4 / Pi 3 only.** Forces 720p. Without it, 1080p YouTube stutters badly on a Pi 4 |
| `update.sh` | Pulls the latest version and restarts everything |
| `uninstall.sh` | Removes the services and autostart |

## Watching from another device

The Pi serves on your home network, so anything on the same wifi can open it —
a phone, a tablet, another laptop:

```
http://<the-pi's-ip>:8080/index.html
```

`install.sh` prints that address when it finishes. `hostname -I` on the Pi
shows it again later.

## If something goes wrong

**Black screen / no picture at all** — check the cable is in the correct
micro-HDMI port. On a Pi 5 and Pi 4 it's the one nearest the USB-C power
socket.

**The app doesn't appear, but the desktop does** — the server or the kiosk
script failed:

```bash
systemctl status papa-ka-tv
journalctl -u papa-ka-tv -n 50
```

**News channels show old recordings instead of live TV** — the refresh
couldn't reach YouTube. Check `refresh_log.txt` in the app folder, then:

```bash
sudo systemctl start papa-ka-tv-refresh.service
```

**Video stutters or tears** — a Pi 4 at 1080p; run `tune-pi4.sh`. On a Pi 5,
suspect the power supply or a missing cooler.

**Rainbow square or lightning bolt in the corner** — undervoltage. That is the
power supply, every time.

**To get out of kiosk mode** — `Alt+F4`, or plug in a keyboard and press
`Ctrl+Alt+T` for a terminal.
