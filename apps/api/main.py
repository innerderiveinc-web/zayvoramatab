"""Application Server Entrypoint for ZAYVORA MATAB OS."""

import os
import sys
import mimetypes
from urllib.parse import urlparse, parse_qs
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Ensure root workspace directory is always in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

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

    def _send_security_headers(self, custom_headers=None):
        custom_headers = custom_headers or {}
        custom_lower = {k.lower(): v for k, v in custom_headers.items()}
        req_origin = self.headers.get("Origin", "")
        allowed = [o.strip() for o in getattr(config, "allowed_origins", "").split(",") if o.strip()]
        
        # Check against allowed list or standard local addresses
        if req_origin and (req_origin in allowed or any(req_origin.startswith(h) for h in ["http://localhost:", "http://127.0.0.1:", "https://localhost:"])):
            origin_to_send = req_origin
            self.send_header("Access-Control-Allow-Credentials", "true")
        elif not req_origin:
            origin_to_send = allowed[0] if allowed else "http://127.0.0.1:8000"
        else:
            origin_to_send = allowed[0] if allowed else "http://127.0.0.1:8000"
            
        self.send_header("Access-Control-Allow-Origin", origin_to_send)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-Id, Range")
        self.send_header("Vary", "Origin")
        if "x-content-type-options" not in custom_lower:
            self.send_header("X-Content-Type-Options", "nosniff")
        if "x-frame-options" not in custom_lower:
            self.send_header("X-Frame-Options", "SAMEORIGIN")
        if "x-xss-protection" not in custom_lower:
            self.send_header("X-XSS-Protection", "1; mode=block")
        if "referrer-policy" not in custom_lower:
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        if "permissions-policy" not in custom_lower:
            self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if "content-security-policy" not in custom_lower:
            csp = "default-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; frame-ancestors 'none';"
            self.send_header("Content-Security-Policy", csp)
        if "cache-control" not in custom_lower:
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")

    def _handle_request(self, method: str):
        parsed = urlparse(self.path)
        path = parsed.path
        query_params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        # 1. API Route Dispatch
        if path.startswith("/api/"):
            try:
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
            except Exception as e:
                import traceback
                import json
                sys.stderr.write(f"[!] Top-level gateway exception: {e}\n{traceback.format_exc()}\n")
                status_code = 500
                resp_headers = {"Content-Type": "application/json"}
                resp_bytes = json.dumps({"error": True, "message": "Captured unhandled gateway error."}).encode("utf-8")

            self.send_response(status_code)
            self._send_security_headers(resp_headers)
            for h_name, h_val in resp_headers.items():
                safe_val = str(h_val).encode("latin-1", "replace").decode("latin-1")
                self.send_header(h_name, safe_val)
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
        elif rel_path in ("science", "research", "publications", "whitepapers", "science_and_research.html"):
            target_file = WEB_DIR / "science_and_research.html"
        else:
            target_file = (WEB_DIR / rel_path).resolve()
            if not str(target_file).startswith(str(WEB_DIR)):
                self.send_response(403)
                self.end_headers()
                return

        if not target_file.exists() or target_file.is_dir():
            target_file = WEB_DIR / "index.html"

        ext = target_file.suffix.lower()
        if ext == ".js":
            mime_type = "application/javascript"
        elif ext == ".css":
            mime_type = "text/css"
        elif ext in (".html", ".htm"):
            mime_type = "text/html"
        elif ext == ".svg":
            mime_type = "image/svg+xml"
        elif ext == ".json":
            mime_type = "application/json"
        elif ext in (".woff", ".woff2"):
            mime_type = f"font/{ext.lstrip('.')}"
        else:
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

    def address_string(self):
        return self.client_address[0]

    def log_message(self, format, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))

def start_server():
    print(f"=== ZAYVORA MATAB OS (Phase 1 Foundation) ===")
    print(f"Environment: {config.env} | Profile: {config.profile}")
    print(f"Database: {config.db_path}")

    # Apply database migrations on boot
    run_migrations()

    # Layer 3 ACID Armor: Start background database snapshot daemon
    try:
        from apps.api.core.backup_daemon import start_backup_daemon
        start_backup_daemon(interval_seconds=3600)
    except Exception as daemon_err:
        print(f"[*] Backup daemon startup notice: {daemon_err}")

    print(f"Server listening on http://{config.host}:{config.port}")
    print(f"Local Access: http://127.0.0.1:{config.port} or http://localhost:{config.port}")
    try:
        ThreadingHTTPServer.allow_reuse_address = True
        server = ThreadingHTTPServer((config.host, config.port), MatabRequestHandler)
        server.timeout = 30
    except OSError as e:
        if e.errno == 48:
            print(f"\n[!] Port {config.port} is already in use by another process.")
            print(f"[!] To release the port, run: kill -9 $(lsof -ti :{config.port})")
            print(f"[!] Or start with: ./start_matab.sh (which automatically frees the port).\n")
            sys.exit(1)
        raise

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ZAYVORA MATAB OS Server.")
        server.server_close()

if __name__ == "__main__":
    start_server()
