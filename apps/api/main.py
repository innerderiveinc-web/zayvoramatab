"""Application Server Entrypoint for ZAYVORA MATAB OS."""

import os
import sys
import mimetypes
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from apps.api.config import config
from apps.api.database.migrator import run_migrations
from apps.api.router import ApiRouter

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
PACKAGES_DIR = Path(__file__).resolve().parent.parent.parent / "packages"

class MatabRequestHandler(BaseHTTPRequestHandler):
    server_version = "ZayvoraMatabOS-Foundation/1.1"

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_security_headers()
        self.end_headers()

    def do_GET(self):
        self._handle_request("GET")

    def do_POST(self):
        self._handle_request("POST")

    def do_PATCH(self):
        self._handle_request("PATCH")

    def do_PUT(self):
        self._handle_request("PUT")

    def do_DELETE(self):
        self._handle_request("DELETE")

    def _send_security_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-Id")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-XSS-Protection", "1; mode=block")

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
            self._send_security_headers()
            for h_name, h_val in resp_headers.items():
                self.send_header(h_name, h_val)
            self.send_header("Content-Length", str(len(resp_bytes)))
            self.end_headers()
            self.wfile.write(resp_bytes)
            return

        # 2. Static Web Shell Serving
        if method != "GET":
            self.send_response(405)
            self.end_headers()
            return

        rel_path = path.lstrip("/")
        if path.startswith("/packages/"):
            pkg_rel = path.replace("/packages/", "", 1)
            target_file = (PACKAGES_DIR / pkg_rel).resolve()
            if not str(target_file).startswith(str(PACKAGES_DIR)):
                self.send_response(403)
                self.end_headers()
                return
        elif not rel_path or rel_path == "index.html":
            target_file = WEB_DIR / "index.html"
        else:
            target_file = (WEB_DIR / rel_path).resolve()
            if not str(target_file).startswith(str(WEB_DIR)):
                self.send_response(403)
                self.end_headers()
                return

        if not target_file.exists() or target_file.is_dir():
            target_file = WEB_DIR / "index.html"

        mime_type, _ = mimetypes.guess_type(str(target_file))
        mime_type = mime_type or "text/html"

        try:
            with open(target_file, "rb") as f:
                content = f.read()
            self.send_response(200)
            self._send_security_headers()
            self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Internal asset read error")

    def log_message(self, format, *args):
        if os.getenv("MATAB_DEBUG") == "1":
            super().log_message(format, *args)

def start_server():
    print(f"=== ZAYVORA MATAB OS (Phase 1 Foundation) ===")
    print(f"Environment: {config.env} | Profile: {config.profile}")
    print(f"Database: {config.db_path}")

    # Apply database migrations on boot
    run_migrations()

    print(f"Server listening on http://{config.host}:{config.port}")
    server = ThreadingHTTPServer((config.host, config.port), MatabRequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ZAYVORA MATAB OS Server.")
        server.server_close()

if __name__ == "__main__":
    start_server()
