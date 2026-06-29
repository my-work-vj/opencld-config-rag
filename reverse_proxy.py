"""
Reverse proxy: serves ingestion and query frontends under a single port.
  /ingestion/*       → localhost:3001  (ingestion Vite)
  /ret_gen/*         → localhost:3000  (query Vite)
  /ingestion/api/*   → localhost:8081/api/v1/* (ingestion backend)
  /ret_gen/api/*     → localhost:8083/api/v1/* (query backend)
"""

import json
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

INGESTION_UI = "http://localhost:3001"
QUERY_UI = "http://localhost:3000"
INGESTION_API = "http://localhost:8081/api/v1"
QUERY_API = "http://localhost:8083/api/v1"


def route(path: str) -> str:
    """Return the target URL for a given path."""
    if path.startswith("/ingestion/api/"):
        suffix = path[len("/ingestion/api"):]  # keep the /
        return INGESTION_API.rstrip("/") + suffix
    if path == "/ingestion/api":
        return INGESTION_API.rstrip("/") + "/"
    if path.startswith("/ret_gen/api/"):
        suffix = path[len("/ret_gen/api"):]
        return QUERY_API.rstrip("/") + suffix
    if path == "/ret_gen/api":
        return QUERY_API.rstrip("/") + "/"
    if path.startswith("/ingestion"):
        return INGESTION_UI.rstrip("/") + path
    if path.startswith("/ret_gen"):
        return QUERY_UI.rstrip("/") + path
    return INGESTION_UI.rstrip("/") + path


def proxy_request(method: str, target: str, headers: dict, body: bytes) -> tuple:
    """Forward a request and return (status_code, response_headers, body)."""
    req = urllib.request.Request(target, data=body or None, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read()
            resp_headers = dict(resp.headers)
            return resp.status, resp_headers, resp_body
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()
    except urllib.error.URLError as e:
        return 502, {"Content-Type": "text/plain"}, str(e.reason).encode()


class ThreadedProxy(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_PUT(self):
        self._handle("PUT")

    def do_DELETE(self):
        self._handle("DELETE")

    def do_OPTIONS(self):
        self._handle("OPTIONS")

    def _handle(self, method: str):
        target = route(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        # Forward headers (skip hop-by-hop)
        fwd_headers = {}
        hop_by_hop = {"host", "connection", "transfer-encoding", "proxy-connection",
                      "keep-alive", "upgrade"}
        for k, v in self.headers.items():
            if k.lower() not in hop_by_hop:
                fwd_headers[k] = v

        status, resp_headers, resp_body = proxy_request(method, target, fwd_headers, body)

        self.send_response(status)
        # Forward response headers
        sent_ct = False
        for k, v in resp_headers.items():
            kl = k.lower()
            if kl in ("content-length", "content-type"):
                self.send_header(k, v)
                if kl == "content-type":
                    sent_ct = True
            elif kl not in ("transfer-encoding", "connection", "keep-alive", "proxy-connection"):
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(resp_body)))
        if not sent_ct:
            self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(resp_body)

    def log_message(self, format, *args):
        print(f"[proxy] {self.address_string()} - {format % args}")


if __name__ == "__main__":
    port = 3002
    server = ThreadedProxy(("0.0.0.0", port), ProxyHandler)
    print(f"Reverse proxy listening on http://0.0.0.0:{port}")
    print("Routes:")
    print(f"  /ingestion/*        -> {INGESTION_UI}")
    print(f"  /ingestion/api/*    -> {INGESTION_API}/*")
    print(f"  /ret_gen/*          -> {QUERY_UI}")
    print(f"  /ret_gen/api/*      -> {QUERY_API}/*")
    server.serve_forever()
