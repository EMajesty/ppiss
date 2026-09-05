"""Animation colour streaming for three A-RGB zones driving six paired case fans."""

from __future__ import annotations

import json
import math
import socket
import threading
import time

RGB_PORT = 45893
FAN_COUNT = 3
LEDS_PER_FAN = 12
ZONE_NAMES = (
    "Addressable Header 1",
    "Addressable Header 2",
    "Addressable Header 3/Audio",
)


def encode_colors(fans: list[list[tuple[int, int, int]]]) -> bytes:
    if len(fans) != FAN_COUNT or any(len(fan) != LEDS_PER_FAN for fan in fans):
        raise ValueError("an RGB frame must contain three 12-LED fans")
    return json.dumps({"v": 1, "fans": fans}, separators=(",", ":")).encode()


def decode_colors(packet: bytes) -> list[list[tuple[int, int, int]]]:
    value = json.loads(packet)
    fans = value["fans"]
    if value.get("v") != 1 or len(fans) != FAN_COUNT:
        raise ValueError("unsupported RGB frame")
    result = []
    for fan in fans:
        if len(fan) != LEDS_PER_FAN:
            raise ValueError("wrong LED count")
        result.append([tuple(max(0, min(255, int(channel))) for channel in color) for color in fan])
    return result


class AnimationColorSender:
    """Sample three rings for three mirrored two-fan zones and send them to the PC."""

    def __init__(self, port: int = RGB_PORT, rate: float = 10.0) -> None:
        self.port, self.period = port, 1.0 / max(1.0, rate)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.last_sent = 0.0

    def update(self, surface, host: str | None, now: float) -> None:
        if not host or now - self.last_sent < self.period:
            return
        width, height = surface.get_size()
        radius = max(2, min(width // 8, height // 12))
        center_y = height // 2
        fans = []
        for fan_index in range(FAN_COUNT):
            center_x = (fan_index * 2 + 1) * width // (FAN_COUNT * 2)
            colors = []
            for led in range(LEDS_PER_FAN):
                angle = -math.pi / 2 + math.tau * led / LEDS_PER_FAN
                x = max(0, min(width - 1, round(center_x + math.cos(angle) * radius)))
                y = max(0, min(height - 1, round(center_y + math.sin(angle) * radius)))
                colors.append(tuple(surface.get_at((x, y))[:3]))
            fans.append(colors)
        self.socket.sendto(encode_colors(fans), (host, self.port))
        self.last_sent = now

    def close(self) -> None:
        self.socket.close()


class OpenRGBOutput:
    """Receive PPISS RGB frames and apply them to selected OpenRGB zones."""

    def __init__(
        self,
        bind: str,
        port: int,
        server_host: str,
        server_port: int,
        device_name: str,
        zone_names: tuple[str, ...],
        brightness: float,
    ) -> None:
        self.bind, self.port = bind, port
        self.server_host, self.server_port = server_host, server_port
        self.device_name, self.zone_names = device_name, zone_names
        self.brightness = max(0.0, min(1.0, brightness))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="ppiss-rgb", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _connect(self):
        from openrgb import OpenRGBClient

        client = OpenRGBClient(self.server_host, self.server_port, name="PPISS")
        device = next(
            (item for item in client.devices if self.device_name.lower() in item.name.lower()), None
        )
        if device is None:
            raise RuntimeError(f"OpenRGB device not found: {self.device_name}")
        zones = []
        for name in self.zone_names:
            zone = next((item for item in device.zones if item.name == name), None)
            if zone is None:
                raise RuntimeError(f"OpenRGB zone not found: {name}")
            zone.resize(LEDS_PER_FAN)
            zones.append(zone)
        device.set_mode("Direct")
        return client, zones

    def _run(self) -> None:
        from openrgb.utils import RGBColor

        _client = zones = None
        retry_at = 0.0
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.bind, self.port))
            sock.settimeout(0.5)
            while not self._stop.is_set():
                try:
                    packet, _ = sock.recvfrom(4096)
                    fans = decode_colors(packet)
                except (TimeoutError, OSError, ValueError, KeyError, json.JSONDecodeError):
                    continue
                if zones is None and time.monotonic() >= retry_at:
                    try:
                        _client, zones = self._connect()
                    except (ConnectionError, OSError, RuntimeError):
                        retry_at = time.monotonic() + 5
                        continue
                if zones is None:
                    continue
                try:
                    for zone, fan in zip(zones, fans, strict=True):
                        zone.set_colors([
                            RGBColor(*(round(channel * self.brightness) for channel in color))
                            for color in fan
                        ], fast=True)
                except (ConnectionError, OSError):
                    _client = zones = None
