from __future__ import annotations

import http.server
import threading
import urllib.parse
import urllib.request


class ArtworkServer:
    def __init__(self, host: str, port: int) -> None:
        self.host, self.port = host, port
        self.artwork_id: str | None = None
        self.data: bytes | None = None
        self._server: http.server.ThreadingHTTPServer | None = None

    def update(self, artwork_id: str | None, source: str | bytes | None) -> None:
        if artwork_id == self.artwork_id:
            return
        self.artwork_id, self.data = artwork_id, None
        if isinstance(source, bytes):
            self.data = source
        elif source:
            try:
                parsed = urllib.parse.urlparse(source)
                if parsed.scheme == "file":
                    with open(urllib.request.url2pathname(parsed.path), "rb") as stream:
                        self.data = stream.read(10_000_001)
                elif parsed.scheme in ("http", "https"):
                    with urllib.request.urlopen(source, timeout=5) as response:
                        self.data = response.read(10_000_001)
                if self.data and len(self.data) > 10_000_000:
                    self.data = None
            except (OSError, ValueError):
                self.data = None

    def start(self) -> None:
        owner = self
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == f"/art/{owner.artwork_id}" and owner.data:
                    self.send_response(200); self.send_header("Content-Type", "image/*")
                    self.send_header("Content-Length", str(len(owner.data))); self.end_headers(); self.wfile.write(owner.data)
                else:
                    self.send_error(404)
            def log_message(self, *_):
                pass
        self._server = http.server.ThreadingHTTPServer((self.host, self.port), Handler)
        threading.Thread(target=self._server.serve_forever, name="artwork-http", daemon=True).start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
