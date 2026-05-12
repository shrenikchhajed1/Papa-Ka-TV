#!/bin/bash
# ============================================
# Papa Ka TV Launcher (macOS)
# Double-click this file to start Papa Ka TV!
# ============================================

# Get the directory where this script lives
DIR="$(cd "$(dirname "$0")" && pwd)"

PORT=8080

# Refresh video IDs (news live streams + broken song IDs)
echo ""
echo "============================================"
echo "  Papa Ka TV - Starting up..."
echo "============================================"
echo ""

# Check Python3 is available
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3 is not installed!"
    echo "Please install Python from: https://python.org"
    echo ""
    echo "Press any key to exit..."
    read -n 1
    exit 1
fi

echo "Refreshing video IDs (this may take a moment)..."
cd "$DIR"
python3 refresh_ids.py
REFRESH_EXIT=$?

if [ $REFRESH_EXIT -ne 0 ]; then
    echo ""
    echo "WARNING: Video refresh had issues (exit code $REFRESH_EXIT)"
    echo "Check refresh_log.txt for details."
    echo "Starting app with existing video IDs..."
    echo ""
fi

# Check if something is already running on the port
if lsof -i :$PORT >/dev/null 2>&1; then
    echo "Server already running on port $PORT"
else
    echo "Starting Papa Ka TV server on port $PORT..."
    # Start Python HTTP server with no-cache headers (in background)
    cd "$DIR"
    python3 -c "
import http.server
import socketserver

class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

with socketserver.TCPServer(('', $PORT), NoCacheHandler) as httpd:
    httpd.serve_forever()
" &
    SERVER_PID=$!
    echo "Server started (PID: $SERVER_PID)"
    # Give the server a moment to start
    sleep 1
fi

# Open the browser
echo "Opening Papa Ka TV in your browser..."
open "http://localhost:$PORT/index.html"

# Start ngrok tunnel (if ngrok is installed)
NGROK_URL=""
if command -v ngrok &>/dev/null; then
    echo ""
    echo "Starting ngrok tunnel..."
    # Kill any existing ngrok process
    pkill -f "ngrok http" 2>/dev/null
    sleep 1
    # Start ngrok in background
    ngrok http $PORT --log=stdout > /dev/null 2>&1 &
    NGROK_PID=$!
    # Wait for ngrok to start and get the public URL
    sleep 3
    NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for t in data.get('tunnels', []):
        if t.get('proto') == 'https':
            print(t['public_url'])
            break
    else:
        for t in data.get('tunnels', []):
            print(t['public_url'])
            break
except:
    pass
" 2>/dev/null)
    if [ -n "$NGROK_URL" ]; then
        echo ""
        echo "============================================"
        echo "  REMOTE ACCESS URL:"
        echo "  ${NGROK_URL}/index.html"
        echo ""
        echo "  Share this link with Papa!"
        echo "  Works from any device, anywhere."
        echo "============================================"
    else
        echo "  WARNING: ngrok started but could not get URL."
        echo "  Check: http://127.0.0.1:4040"
    fi
else
    echo ""
    echo "  (ngrok not installed - skipping remote access)"
    echo "  Install from: https://ngrok.com/download"
fi

echo ""
echo "============================================"
echo "  Papa Ka TV is running!"
echo "  Local:  http://localhost:$PORT/index.html"
if [ -n "$NGROK_URL" ]; then
echo "  Remote: ${NGROK_URL}/index.html"
fi
echo ""
echo "  To stop: close this window or press Ctrl+C"
echo "============================================"
echo ""

# Keep the script running so the server stays alive
# When the user closes the Terminal window, the server dies too
wait
