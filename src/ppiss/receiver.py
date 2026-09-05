from __future__ import annotations

import socket
import threading
import time

from .protocol import MAX_PACKET_BYTES, Telemetry, decode


class TelemetryReceiver:
    """Keep only the newest valid UDP telemetry packet."""

    def __init__(self, host: str, port: int) -> None:
        self.host, self.port = host, port
        self.latest: Telemetry | None = None
        self.peer_host: str | None = None
        self.received_at = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="telemetry", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.5)

    def snapshot(self) -> tuple[Telemetry | None, float]:
        with self._lock:
            return self.latest, time.monotonic() - self.received_at if self.received_at else float("inf")

    def _run(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.settimeout(0.5)
            while not self._stop.is_set():
                try:
                    packet, address = sock.recvfrom(MAX_PACKET_BYTES + 1)
                    value = decode(packet)
                except (TimeoutError, ValueError, OSError):
                    continue
                with self._lock:
                    self.latest, self.received_at = value, time.monotonic()
                    self.peer_host = address[0]
