"""Standalone Production-Ready HTTP Server for ZAYVORA MATAB OS."""

import sys
import os
import mimetypes
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from matab.config import config
from matab.database.connection import init_db
from matab.api.router import ApiRouter

WEB_DIR = Path(__file__).resolve().parent / "web"

class MatabRequestHandler(BaseHTTPRequestHandler):
    server_version = "ZayvoraMatabOS/1.1"

    def do_OPTIONS(self):
        """Handle CORS Preflight."""
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        self._handle_request("GET")

    def do_POST(self):
        self._handle_request("POST")

    def do_PUT(self):
        self._handle_request("PUT")

    def do_DELETE(self):
        self._handle_request("DELETE")

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")

    def _handle_request(self, method: str):
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        # 1. API Route Dispatch
        if path.startswith("/api/"):
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length) if content_length > 0 else b""
            client_ip = self.client_address[0]

            status_code, resp_headers, resp_bytes = ApiRouter.dispatch(
                method=method,
                path=path,
                headers=dict(self.headers),
                query_params=query_params,
                body_bytes=body_bytes,
                client_ip=client_ip
            )

            self.send_response(status_code)
            self._send_cors_headers()
            for h_name, h_val in resp_headers.items():
                self.send_header(h_name, h_val)
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)
            return

        # 2. Static Asset Serving (Frontend Shell & Single Page App)
        if method != "GET":
            self.send_response(405)
            self.end_headers()
            return

        # Sanitize path
        rel_path = path.lstrip("/")
        if not rel_path or rel_path == "index.html":
            target_file = WEB_DIR / "index.html"
        else:
            target_file = (WEB_DIR / rel_path).resolve()
            # Prevent directory traversal
            if not str(target_file).startswith(str(WEB_DIR)):
                self.send_response(403)
                self.end_headers()
                return

        if not target_file.exists() or target_file.is_dir():
            # SPA fallback to index.html for client-side routing
            target_file = WEB_DIR / "index.html"

        mime_type, _ = mimetypes.guess_type(str(target_file))
        mime_type = mime_type or "text/html"

        try:
            with open(target_file, "rb") as f:
                content = f.read()
            self.send_response(200)
            self._send_cors_headers()
            self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error serving asset: {e}".encode("utf-8"))

    def log_message(self, format, *args):
        # Override to suppress noisy terminal log unless in debug
        if os.getenv("MATAB_DEBUG") == "1":
            super().log_message(format, *args)

def run_server(host: str = None, port: int = None):
    h = host or config.host
    p = port or config.port
    print(f"Initializing ZAYVORA MATAB OS Database at '{config.db_path}'...")
    init_db()
    print(f"Starting ZAYVORA MATAB OS Standalone Server at http://{h}:{p}...")
    server = ThreadingHTTPServer((h, p), MatabRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ZAYVORA MATAB OS Server.")
        server.server_close()

if __name__ == "__main__":
    run_server()
