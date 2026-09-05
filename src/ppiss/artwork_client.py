from __future__ import annotations

import threading
import urllib.request


class ArtworkClient:
    def __init__(self) -> None:
        self.requested_id: str | None = None
        self.ready: tuple[str, bytes] | None = None
        self._lock = threading.Lock()

    def request(self, artwork_id: str | None, url: str | None) -> None:
        if not artwork_id or not url or artwork_id == self.requested_id:
            return
        self.requested_id = artwork_id
        threading.Thread(target=self._fetch, args=(artwork_id, url), daemon=True).start()

    def take(self) -> tuple[str, bytes] | None:
        with self._lock:
            value, self.ready = self.ready, None
            return value

    def _fetch(self, artwork_id: str, url: str) -> None:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = response.read(10_000_001)
            if len(data) > 10_000_000:
                return
            with self._lock:
                if artwork_id == self.requested_id:
                    self.ready = (artwork_id, data)
        except (OSError, ValueError):
            pass
