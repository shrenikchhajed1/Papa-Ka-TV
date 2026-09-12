#!/usr/bin/env python3
"""
Papa Ka TV - static file server for the Raspberry Pi.

Same no-cache server the macOS/Windows launchers start inline, but as a real
file so systemd can supervise it. Serves the repo root (the parent of this
directory) on PORT, defaulting to 8080.
"""

import http.server
import os
import socketserver
import sys

PORT = int(os.environ.get("PORT", "8080"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        # refresh_ids.py rewrites index.html underneath us; never let the
        # browser hold on to a stale copy.
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        # systemd already timestamps every line in the journal.
        sys.stderr.write("%s\n" % (fmt % args))


class ReusableTCPServer(socketserver.TCPServer):
    # Lets the service restart without waiting out TIME_WAIT on the port.
    allow_reuse_address = True


def main():
    with ReusableTCPServer(("", PORT), NoCacheHandler) as httpd:
        print(f"Papa Ka TV serving {ROOT} on port {PORT}", flush=True)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
