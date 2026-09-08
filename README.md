# Papa Ka TV (पापा का टीवी)

A simple, TV-like web app for watching Hindi news channels and listening to classic Hindi songs on YouTube. Designed for someone who doesn't know how to use a laptop — big buttons, simple controls, no clutter.

## What's Inside

- **8 Hindi News Channels** — Aaj Tak, NDTV India, India TV, ABP News, Zee News, Republic Bharat, TV9 Bharatvarsh, News18 India
- **30 Classic Artists** — Lata Mangeshkar, Mohammad Rafi, Kishore Kumar, Jagjit Singh, Nusrat Fateh Ali Khan, and more, with ~20 songs each
- **600 songs** — all verified with working YouTube video IDs
- **Auto-refresh** — every time you launch, news channel IDs are automatically checked and updated
- **LIVE / RECORDED badges** — see at a glance which channels are currently live
- **Remote access via ngrok** — if ngrok is installed, the launcher auto-creates a public URL so Papa can watch from another device
- **TV-like experience** — click a channel or song and it plays, no menus to figure out

## Requirements

- **Python 3** (required for the launcher and auto-refresh)
- **Internet connection** (for YouTube and for refreshing video IDs)
- **Any web browser** (Chrome, Firefox, Safari, Edge — anything)
- **ngrok** (optional — for remote access from another device; [download here](https://ngrok.com/download))
- Works on **macOS, Windows, and Linux**

## How to Run

### macOS (IMPORTANT — read this first!)

macOS blocks downloaded files by default. You need to do this **once** after unzipping:

1. Open **Terminal** (search "Terminal" in Spotlight, or find it in Applications > Utilities)
2. Copy-paste this command and press Enter (change the path if you unzipped somewhere else):
   ```
   xattr -cr ~/Downloads/Papa-Ka-TV/
   ```
3. Now double-click **`start-papa-ka-tv.command`**
4. If macOS still asks "are you sure?", click **Open**
5. The app will refresh video IDs and open in your browser

> **Alternative:** Right-click `start-papa-ka-tv.command` > Open > Click "Open" in the dialog.

### Windows
1. Double-click **`start-papa-ka-tv.bat`**
2. If Windows SmartScreen warns you, click "More info" > "Run anyway"
3. It will refresh video IDs automatically, then open the browser

### Linux / Manual
1. Open a terminal in this folder
2. Run: `python3 refresh_ids.py` (optional but recommended — updates any stale IDs)
3. Run: `python3 -m http.server 8080`
4. Open your browser to: `http://localhost:8080/index.html`

> **Why a server?** YouTube embeds require HTTP — they don't work if you open the file directly (`file://`).

### Raspberry Pi (always-on TV box)

A Pi turns this into a real appliance: plug in the power and the TV shows Papa
Ka TV fullscreen, no login, mouse only.

```
git clone https://github.com/shrenikchhajed1/Papa-Ka-TV.git
cd Papa-Ka-TV
bash raspberry-pi/install.sh
sudo reboot
```

Full hardware list, tuning and troubleshooting: **[raspberry-pi/README.md](raspberry-pi/README.md)**

## Auto-Refresh (How It Works)

Every time you launch the app, `refresh_ids.py` runs automatically and:

1. **Checks internet connectivity** — skips refresh if YouTube is unreachable
2. **Fetches current live stream IDs** for all 8 news channels from YouTube
3. **Detects LIVE vs RECORDED** — badges show which channels are broadcasting live right now
4. **Updates `index.html`** in-place with the new IDs and live status

Song video IDs are **not checked by default** (they rarely change). To also check and fix song IDs, run:
```
python3 refresh_ids.py --check-songs
```
This scans all 600 songs, finds replacements for broken ones via YouTube search, and can take several minutes.

A full diagnostic log is written to `refresh_log.txt` every run.

## Remote Access via ngrok

If [ngrok](https://ngrok.com/download) is installed on your machine, the launcher **automatically starts an ngrok tunnel** so the app can be accessed from any device on the internet (e.g., Papa's phone or tablet on a different network).

### How it works
1. The launcher starts the local server on port 8080
2. It starts `ngrok http 8080` in the background
3. It prints the **public ngrok URL** (e.g., `https://xxxx-xx-xx.ngrok-free.app`)
4. Share that URL with anyone — they can watch in their browser, no setup needed

### Setup (one-time)
1. [Download ngrok](https://ngrok.com/download) and install it
2. Sign up for a free account at [ngrok.com](https://ngrok.com)
3. Run: `ngrok config add-authtoken YOUR_TOKEN`
4. That's it — the launcher handles everything else

### If ngrok is not installed
The launcher gracefully skips ngrok and just runs locally on `http://localhost:8080`. No error, no problem.

## How to Use

### Home Screen
- Click any **news channel** to start watching live TV
- Click **"गाने सुनें (Songs)"** to browse artists
- Press number keys **1-8** to quickly pick a news channel

### Artist Screen
- Browse 30 artists across pages (12 per page)
- Click an artist to go to the player
- Use **arrow left/right** to flip pages

### Player Screen
- **Artist strip** (top) — switch artists anytime
- **Song list** (right panel) — pick any song from the selected artist
- **News channels** (bottom strip) — switch to news anytime
- **Volume control** (left side) — slider, +/- buttons, mute
- Songs auto-advance to the next when one finishes

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| Arrow Up/Down | Volume up/down |
| Arrow Left/Right | Previous/next song (or page) |
| M | Mute/unmute |
| Escape / Backspace | Go back |
| 1-8 | Quick news channel (home screen) |

## Files

| File | Description |
|------|-------------|
| `index.html` | The entire app (HTML + CSS + JS, single file) |
| `refresh_ids.py` | Auto-refreshes news and song video IDs (use `--check-songs` to also check songs) |
| `start-papa-ka-tv.command` | macOS launcher (double-click to run) |
| `start-papa-ka-tv.bat` | Windows launcher (double-click to run) |
| `refresh_log.txt` | Diagnostic log from the last refresh run (auto-generated) |
| `raspberry-pi/` | Raspberry Pi kiosk setup — installer, systemd services, kiosk launcher |
| `README.md` | This file |

## Troubleshooting

### "App is damaged and should be moved to Bin" (macOS)
This is macOS Gatekeeper blocking downloaded files. Run this in Terminal:
```
xattr -cr ~/Downloads/Papa-Ka-TV/
```
Replace the path with wherever you unzipped the folder.

### News channel shows error / black screen
The live stream ID may have expired. Restart the app (close and double-click the launcher again) — it will auto-fetch fresh IDs.

### News channels show old/recorded content instead of live
If the refresh script had issues, check the **`refresh_log.txt`** file in the app folder — it logs everything that happened during the refresh. Common causes:
- **No internet**: The script skips refresh if YouTube is unreachable
- **YouTube consent page**: Fixed in the latest version (consent cookie bypass)
- **SSL/certificate issues**: The script has SSL fallback for older systems
- **File permissions**: Make sure the folder is not read-only

### Song won't play
If a song fails, it automatically skips to the next one. To find replacements for broken songs, run:
```
python3 refresh_ids.py --check-songs
```

### Checking the log file
Every time `refresh_ids.py` runs, it writes a `refresh_log.txt` file in the app folder with full diagnostics. If something isn't working, check this file first.
