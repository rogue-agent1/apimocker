#!/usr/bin/env python3
"""apimocker - Mock REST API server from a JSON spec.

One file. Zero deps. Fake APIs fast.

Usage:
  apimocker.py routes.json                → serve mock API on :8080
  apimocker.py routes.json -p 3000        → custom port
  apimocker.py --example                  → print example routes.json
  apimocker.py routes.json --delay 200    → add 200ms latency

Routes file format:
  [{"method":"GET","path":"/users","status":200,"body":[{"id":1,"name":"Alice"}]}]
"""

import argparse
import json
import os
import re
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

EXAMPLE = [
    {"method": "GET", "path": "/", "status": 200, "body": {"message": "API Mock Server"}},
    {"method": "GET", "path": "/users", "status": 200, "body": [
        {"id": 1, "name": "Alice", "email": "alice@example.com"},
        {"id": 2, "name": "Bob", "email": "bob@example.com"},
    ]},
    {"method": "GET", "path": "/users/:id", "status": 200, "body": {"id": 1, "name": "Alice"}},
    {"method": "POST", "path": "/users", "status": 201, "body": {"id": 3, "message": "Created"}},
    {"method": "DELETE", "path": "/users/:id", "status": 204, "body": None},
]


def path_matches(pattern: str, path: str) -> tuple[bool, dict]:
    parts_p = pattern.strip("/").split("/")
    parts_r = path.strip("/").split("/")
    if len(parts_p) != len(parts_r):
        return False, {}
    params = {}
    for pp, pr in zip(parts_p, parts_r):
        if pp.startswith(":"):
            params[pp[1:]] = pr
        elif pp != pr:
            return False, {}
    return True, params


class MockHandler(BaseHTTPRequestHandler):
    routes = []
    delay_ms = 0
    cors = True

    def do_request(self):
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000)

        parsed = urlparse(self.path)
        path = parsed.path
        method = self.command

        for route in self.routes:
            if route.get("method", "GET").upper() != method:
                continue
            matched, params = path_matches(route["path"], path)
            if matched:
                status = route.get("status", 200)
                body = route.get("body")
                headers = route.get("headers", {})

                self.send_response(status)
                self.send_header("Content-Type", headers.get("Content-Type", "application/json"))
                if self.cors:
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Access-Control-Allow-Methods", "*")
                    self.send_header("Access-Control-Allow-Headers", "*")
                for k, v in headers.items():
                    if k != "Content-Type":
                        self.send_header(k, v)
                self.end_headers()

                if body is not None:
                    if isinstance(body, (dict, list)):
                        resp = json.dumps(body)
                    else:
                        resp = str(body)
                    self.wfile.write(resp.encode())
                return

        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Not found", "path": path}).encode())

    def log_message(self, format, *args):
        sys.stderr.write(f"  {self.command:6s} {self.path} → {args[1] if len(args) > 1 else '?'}\n")

    do_GET = do_request
    do_POST = do_request
    do_PUT = do_request
    do_PATCH = do_request
    do_DELETE = do_request
    do_OPTIONS = do_request


def main():
    p = argparse.ArgumentParser(description="Mock REST API server")
    p.add_argument("file", nargs="?", help="Routes JSON file")
    p.add_argument("-p", "--port", type=int, default=8080)
    p.add_argument("--delay", type=int, default=0, help="Response delay in ms")
    p.add_argument("--no-cors", action="store_true")
    p.add_argument("--example", action="store_true")
    args = p.parse_args()

    if args.example:
        print(json.dumps(EXAMPLE, indent=2))
        return 0

    if not args.file:
        p.print_help()
        return 1

    with open(args.file) as f:
        routes = json.load(f)

    MockHandler.routes = routes
    MockHandler.delay_ms = args.delay
    MockHandler.cors = not args.no_cors

    server = HTTPServer(("0.0.0.0", args.port), MockHandler)
    print(f"🚀 Mock API running on http://localhost:{args.port}")
    print(f"   {len(routes)} routes loaded, delay={args.delay}ms, CORS={'on' if not args.no_cors else 'off'}")
    for r in routes:
        print(f"   {r.get('method','GET'):6s} {r['path']}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
