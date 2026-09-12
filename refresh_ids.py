#!/usr/bin/env python3
"""
Papa Ka TV - Video ID Refresher
================================
Runs at startup (via launcher) to:
1. Fetch current live stream IDs for all news channels
2. Check all song video IDs and fix any broken ones

Updates index.html in-place. Safe to run repeatedly.
Writes a log file (refresh_log.txt) for debugging.
"""

import os
import re
import sys
import json
import time
import ssl
import urllib.request
import urllib.parse
import urllib.error
import traceback
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(SCRIPT_DIR, "index.html")
LOG_FILE = os.path.join(SCRIPT_DIR, "refresh_log.txt")

# ─── Logging ────────────────────────────────────────────────────────────────

_log_lines = []

def log(msg):
    """Print to console AND buffer for log file."""
    print(msg)
    _log_lines.append(msg)

def write_log():
    """Write buffered log to file."""
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            f.write(f"Papa Ka TV - refresh_ids.py log\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Python: {sys.version}\n")
            f.write(f"Platform: {sys.platform}\n")
            f.write(f"Script dir: {SCRIPT_DIR}\n")
            f.write(f"Index file: {INDEX_FILE}\n")
            f.write("=" * 50 + "\n\n")
            for line in _log_lines:
                f.write(line + "\n")
    except Exception as e:
        print(f"  Warning: Could not write log file: {e}")


# ─── SSL Context ────────────────────────────────────────────────────────────

def get_ssl_context():
    """Create an SSL context that works on machines with outdated certificates."""
    try:
        ctx = ssl.create_default_context()
        return ctx
    except Exception:
        # Fallback: unverified context (less secure but works everywhere)
        ctx = ssl._create_unverified_context()
        log("  Warning: Using unverified SSL (certificates may be outdated)")
        return ctx


def url_open(url, headers=None, timeout=10):
    """Open a URL with proper error handling, SSL fallback, and consent bypass."""
    if headers is None:
        headers = {}

    # Always set cookies to bypass YouTube consent page
    if "youtube.com" in url:
        headers.setdefault("Cookie", "CONSENT=PENDING+999; SOCS=CAISNQgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjMwODI5LjA3X3AxGgJlbiACGgYIgJnPpwY")
        headers.setdefault("Accept-Language", "en-US,en;q=0.9")
        headers.setdefault("User-Agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    req = urllib.request.Request(url, headers=headers)

    # Try with default SSL first
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=get_ssl_context())
    except ssl.SSLError:
        # Fallback to unverified SSL
        log(f"  Warning: SSL error for {url[:60]}..., retrying without verification")
        ctx = ssl._create_unverified_context()
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)


# ─── Helpers ────────────────────────────────────────────────────────────────

def check_video(vid):
    """Return True if a YouTube video ID is valid and embeddable."""
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
    try:
        resp = url_open(url, timeout=8)
        return resp.getcode() == 200
    except urllib.error.HTTPError as e:
        if e.code == 401 or e.code == 403:
            # Video exists but is not embeddable — still "valid" for our purposes
            # Actually no, we need embeddable. Return False.
            return False
        return False
    except Exception:
        return False


def search_youtube(query, max_results=8):
    """Search YouTube and return a list of video IDs."""
    encoded = urllib.parse.quote(query)
    url = f"https://www.youtube.com/results?search_query={encoded}"
    try:
        resp = url_open(url, timeout=15)
        html = resp.read().decode("utf-8", errors="ignore")
        ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
        seen = set()
        unique = []
        for v in ids:
            if v not in seen:
                seen.add(v)
                unique.append(v)
        return unique[:max_results]
    except Exception as e:
        log(f"  Warning: YouTube search failed for '{query[:40]}': {e}")
        return []


def _norm(text):
    """Lowercase and strip everything but letters/digits, so 'TV9 Bharatvarsh'
    and 'tv9bharatvarsh' compare equal."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _parse_watching(blob):
    """Pull the concurrent viewer count out of a lockup, as an int."""
    m = re.search(r'"content":\s*"([\d.,]+)([KMB]?) watching"', blob)
    if not m:
        return 0
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return 0
    return int(n * {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(m.group(2), 1))


def _title_score(title, handle):
    """How much a title looks like the channel's rolling 24x7 feed.

    Zero means "this is a one-off event stream" - a press conference or a
    single story, which ends within hours and then plays back as a recording.
    Only a positive score is worth using.
    """
    t = _norm(title)
    if not t:
        return 0
    # "Aaj Tak LIVE TV", "TV9 Bharatvarsh LIVE", "News18 India TV Live" - the
    # channel branding its own continuous feed.
    if _norm(handle) in t and "live" in t:
        return 100
    if "livetv" in t or "tvlive" in t:
        return 90
    # "Republic TV 24x7"
    if "24x7" in t or "24hours" in t:
        return 85
    return 0


def get_main_live_stream(handle, retries=2):
    """Find the channel's rolling 24x7 live stream.

    Reads the channel's /streams tab, keeps only currently-live entries, and
    prefers the one whose title looks like the main feed rather than a one-off
    event. Returns (video_id, title) or (None, reason).
    """
    data = None
    reason = "not attempted"

    # YouTube intermittently serves a page with no ytInitialData. Falling back
    # to /live on the first miss is how an event stream sneaks in, so retry
    # before giving up.
    for attempt in range(retries + 1):
        try:
            resp = url_open(f"https://www.youtube.com/@{handle}/streams", timeout=20)
            html = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            reason = f"{type(e).__name__}: {e}"
            if attempt < retries:
                time.sleep(1.5)
            continue

        m = re.search(r"var ytInitialData = (\{.*?\});</script>", html)
        if not m:
            reason = "no ytInitialData"
            if attempt < retries:
                time.sleep(1.5)
            continue

        try:
            data = json.loads(m.group(1))
            break
        except Exception as e:
            reason = f"bad ytInitialData: {e}"
            if attempt < retries:
                time.sleep(1.5)

    if data is None:
        return None, reason

    candidates = []

    def walk(node):
        if isinstance(node, dict):
            lockup = node.get("lockupViewModel")
            if isinstance(lockup, dict) and lockup.get("contentId"):
                blob = json.dumps(lockup, ensure_ascii=False)
                # YouTube moved this page to lockupViewModel; the badge style is
                # the only reliable "live right now" marker left on it.
                if "THUMBNAIL_OVERLAY_BADGE_STYLE_LIVE" in blob:
                    meta = lockup.get("metadata", {}).get("lockupMetadataViewModel", {})
                    title = meta.get("title", {}).get("content", "")
                    candidates.append((lockup["contentId"], title, _parse_watching(blob)))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)

    seen = set()
    unique = []
    for vid, title, watching in candidates:
        if vid not in seen:
            seen.add(vid)
            unique.append((vid, title, watching))

    if not unique:
        return None, "no live streams listed"

    # Title decides; viewers only break ties between equally-branded feeds.
    scored = [(_title_score(t, handle), w, vid, t) for vid, t, w in unique]
    best = max(scored, key=lambda c: (c[0], c[1]))
    if best[0] == 0:
        return None, f"{len(unique)} live, none branded as a main feed"
    return best[2], best[3]


def get_live_video_id(handle, retries=2):
    """Fetch the current live stream video ID for a YouTube channel handle.
    
    Returns (video_id, is_live, method_or_error) tuple for diagnostics.
    is_live is True if the stream is currently live, False otherwise.
    """
    # Prefer the channel's rolling 24x7 feed. /live names whichever stream
    # YouTube considers current, which on a news channel is often a one-off
    # event that ends within hours.
    main_id, detail = get_main_live_stream(handle)
    if main_id:
        return main_id, True, f"main-feed ({detail[:40]})"
    log(f"  Note: {handle} - main feed not found ({detail}); falling back to /live")

    url = f"https://www.youtube.com/@{handle}/live"

    for attempt in range(retries + 1):
        try:
            resp = url_open(url, timeout=12)
            final_url = resp.url if hasattr(resp, 'url') else url
            html = resp.read().decode("utf-8", errors="ignore")

            # Check if we got a consent/cookie wall redirect
            if "consent.youtube.com" in final_url or "consent.google.com" in final_url:
                log(f"  Warning: {handle} - got consent redirect (attempt {attempt + 1})")
                if attempt < retries:
                    time.sleep(1)
                    continue
                return None, False, "consent-redirect"

            # Check if we got a valid page (should be > 10KB for a real YT page)
            if len(html) < 10000:
                log(f"  Warning: {handle} - page too small ({len(html)} bytes, attempt {attempt + 1})")
                if attempt < retries:
                    time.sleep(1)
                    continue
                return None, False, f"page-too-small ({len(html)} bytes)"

            # Check liveness: YouTube embeds "isLive":true in the page JSON
            is_live = '"isLive":true' in html

            # Method 1: canonical link (most reliable)
            m = re.search(
                r'<link rel="canonical" href="https://www.youtube.com/watch\?v=([^"]+)"',
                html,
            )
            if m:
                return m.group(1), is_live, "canonical"

            # Method 2: videoId in JSON data
            m2 = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
            if m2:
                return m2.group(1), is_live, "json-videoId"

            # Method 3: Check if there's a live stream URL embedded
            m3 = re.search(r'/watch\?v=([a-zA-Z0-9_-]{11})', html)
            if m3:
                return m3.group(1), is_live, "watch-url"

            return None, False, f"no-video-id-found (html={len(html)} bytes)"

        except urllib.error.HTTPError as e:
            error_msg = f"HTTP {e.code}"
            if attempt < retries:
                log(f"  Warning: {handle} - {error_msg} (attempt {attempt + 1}, retrying...)")
                time.sleep(1)
                continue
            return None, False, error_msg

        except urllib.error.URLError as e:
            error_msg = f"URL error: {e.reason}"
            if attempt < retries:
                log(f"  Warning: {handle} - {error_msg} (attempt {attempt + 1}, retrying...)")
                time.sleep(1)
                continue
            return None, False, error_msg

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            if attempt < retries:
                log(f"  Warning: {handle} - {error_msg} (attempt {attempt + 1}, retrying...)")
                time.sleep(1)
                continue
            return None, False, error_msg

    return None, False, "max-retries-exceeded"


# ─── Phase 1: Refresh News Channel Live IDs ─────────────────────────────────

def refresh_news_ids(content):
    """Update live stream video IDs and isLive status for news channels."""
    log("\n--- Refreshing news channel live stream IDs ---")

    # Extract channel handles, current videoIds, and isLive status
    # Pattern matches: handle: 'X', videoId: 'Y', isLive: true/false
    pattern = re.compile(
        r"handle:\s*'([^']+)',\s*videoId:\s*'([^']+)',\s*isLive:\s*(true|false)"
    )
    matches = list(pattern.finditer(content))

    if not matches:
        log("  ERROR: No channel patterns found in index.html!")
        log("  Expected pattern: handle: 'X', videoId: 'Y', isLive: true/false")
        return content

    log(f"  Found {len(matches)} news channels")

    updated = 0
    failed = 0
    for m in matches:
        handle = m.group(1)
        old_vid = m.group(2)
        old_live = m.group(3)
        new_vid, is_live, method = get_live_video_id(handle)
        new_live = "true" if is_live else "false"

        if new_vid:
            old_str = f"handle: '{handle}', videoId: '{old_vid}', isLive: {old_live}"
            new_str = f"handle: '{handle}', videoId: '{new_vid}', isLive: {new_live}"
            if old_str in content:
                content = content.replace(old_str, new_str)
                changed_parts = []
                if new_vid != old_vid:
                    changed_parts.append(f"vid: {old_vid} -> {new_vid}")
                if new_live != old_live:
                    changed_parts.append(f"live: {old_live} -> {new_live}")
                if changed_parts:
                    log(f"  OK {handle}: {', '.join(changed_parts)} (via {method})")
                    updated += 1
                else:
                    log(f"  OK {handle}: already current ({old_vid}, live={new_live})")
            else:
                log(f"  ERROR {handle}: pattern not found for replacement!")
                failed += 1
        else:
            log(f"  FAIL {handle}: could not fetch - {method} (keeping old ID: {old_vid})")
            failed += 1

    log(f"  Summary: {updated} updated, {len(matches) - updated - failed} current, {failed} failed")
    return content


# ─── Phase 2: Check & Fix Song Video IDs ────────────────────────────────────

def refresh_song_ids(content):
    """Check all song video IDs and replace broken ones."""
    log("\n--- Checking song video IDs ---")

    # Extract all song videoIds
    song_pattern = re.compile(
        r"hindi:\s*'([^']+)',\s*english:\s*'([^']+)',\s*videoId:\s*'([^']+)'"
    )

    # Also figure out which artist each song belongs to
    artist_pattern = re.compile(
        r"\{\s*hindi:\s*'([^']+)',\s*english:\s*'([^']+)',\s*color:\s*'[^']+',\s*songs:\s*\["
    )

    # Build song->artist mapping by position
    songs = []
    current_artist = "Unknown"
    for line_num, line in enumerate(content.split("\n")):
        am = artist_pattern.search(line)
        if am:
            current_artist = am.group(2)  # english name
        sm = song_pattern.search(line)
        if sm:
            songs.append({
                "artist": current_artist,
                "hindi": sm.group(1),
                "english": sm.group(2),
                "videoId": sm.group(3),
            })

    total = len(songs)
    log(f"  Found {total} songs to check")

    if total == 0:
        log("  ERROR: No songs found in index.html!")
        return content

    # Get unique IDs to check (avoid redundant checks)
    unique_ids = list(set(s["videoId"] for s in songs))
    log(f"  Checking {len(unique_ids)} unique video IDs...")

    # Batch check all IDs
    id_status = {}
    check_errors = 0
    for i, vid in enumerate(unique_ids):
        id_status[vid] = check_video(vid)
        if not id_status[vid]:
            check_errors += 1
        if (i + 1) % 50 == 0:
            log(f"    ...checked {i + 1}/{len(unique_ids)}")

    broken = [s for s in songs if not id_status.get(s["videoId"], False)]
    ok_count = total - len(broken)
    log(f"  OK: {ok_count} songs, Broken: {len(broken)} songs")

    if not broken:
        log("  All songs are working!")
        return content

    log(f"  Searching for replacements...")

    fixed = 0
    failed = 0
    already_fixed = set()  # Don't search for same ID twice

    for i, song in enumerate(broken):
        old_vid = song["videoId"]

        # If we already found a fix for this ID, skip searching
        if old_vid in already_fixed:
            continue

        queries = [
            f"{song['english']} {song['artist']} official audio",
            f"{song['english']} {song['artist']} hindi song",
            f"{song['english']} hindi film song full audio",
        ]

        found = False
        for query in queries:
            results = search_youtube(query)
            for vid in results:
                if check_video(vid):
                    # Replace in content
                    content = content.replace(
                        f"videoId: '{old_vid}'",
                        f"videoId: '{vid}'",
                    )
                    log(f"  FIXED {song['artist']} - {song['english']}: {old_vid} -> {vid}")
                    already_fixed.add(old_vid)
                    fixed += 1
                    found = True
                    break
            if found:
                break
            time.sleep(0.2)

        if not found:
            log(f"  FAIL {song['artist']} - {song['english']}: no replacement found")
            already_fixed.add(old_vid)
            failed += 1

        time.sleep(0.15)

    log(f"\n  Song fix summary: {fixed} fixed, {failed} could not fix")
    return content


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    exit_code = 0

    log("=" * 50)
    log("  Papa Ka TV - Refreshing Video IDs")
    log(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 50)

    # Check Python version
    log(f"  Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} on {sys.platform}")

    # Check index.html exists
    if not os.path.exists(INDEX_FILE):
        log(f"ERROR: {INDEX_FILE} not found!")
        write_log()
        sys.exit(1)

    # Check index.html is readable
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        log(f"  Loaded index.html ({len(content)} bytes)")
    except Exception as e:
        log(f"ERROR: Cannot read {INDEX_FILE}: {e}")
        write_log()
        sys.exit(1)

    # Check internet connectivity
    log("\n  Checking internet connectivity...")
    try:
        resp = url_open("https://www.youtube.com/", timeout=10)
        log(f"  Internet OK (youtube.com responded, {resp.getcode()})")
    except Exception as e:
        log(f"  WARNING: Cannot reach youtube.com: {e}")
        log("  Skipping refresh (no internet). App will use existing video IDs.")
        write_log()
        sys.exit(0)  # Exit cleanly — don't block the launcher

    original = content

    # Phase 1: News channels (always runs)
    try:
        content = refresh_news_ids(content)
    except Exception as e:
        log(f"\nERROR in news refresh: {e}")
        log(traceback.format_exc())
        exit_code = 1

    # Phase 2: Songs (only with --check-songs flag, since they rarely change)
    if "--check-songs" in sys.argv:
        try:
            content = refresh_song_ids(content)
        except Exception as e:
            log(f"\nERROR in song refresh: {e}")
            log(traceback.format_exc())
            exit_code = 1
    else:
        log("\n--- Skipping song check (use --check-songs to enable) ---")

    # Save if changed
    if content != original:
        try:
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                f.write(content)
            log(f"\nDONE: index.html updated ({len(content)} bytes written)")
        except Exception as e:
            log(f"\nERROR: Cannot write {INDEX_FILE}: {e}")
            log("  Check file permissions!")
            exit_code = 1
    else:
        log("\nDONE: No changes needed -- everything is up to date!")

    log("=" * 50)
    write_log()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
