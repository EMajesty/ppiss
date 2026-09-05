"""Small, dependency-free wire protocol shared by display and sender."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = 1
MAX_PACKET_BYTES = 8192


@dataclass(frozen=True, slots=True)
class Telemetry:
    hostname: str
    cpu_percent: float
    memory_percent: float
    gpu_percent: float | None = None
    gpu_temp_c: float | None = None
    cpu_temp_c: float | None = None
    fps: float | None = None
    timestamp: float = 0.0

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "Telemetry":
        def number(name: str, *, optional: bool = False) -> float | None:
            raw = value.get(name)
            if raw is None and optional:
                return None
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ValueError(f"{name} must be a number")
            return float(raw)

        hostname = value.get("hostname")
        if not isinstance(hostname, str) or not hostname[:64]:
            raise ValueError("hostname must be a non-empty string")
        return cls(
            hostname=hostname[:64],
            cpu_percent=float(number("cpu_percent")),
            memory_percent=float(number("memory_percent")),
            gpu_percent=number("gpu_percent", optional=True),
            gpu_temp_c=number("gpu_temp_c", optional=True),
            cpu_temp_c=number("cpu_temp_c", optional=True),
            fps=number("fps", optional=True),
            timestamp=float(number("timestamp")),
        )


def encode(telemetry: Telemetry, secret: str = "") -> bytes:
    payload = {
        "v": PROTOCOL_VERSION,
        "stats": {
            "hostname": telemetry.hostname,
            "cpu_percent": telemetry.cpu_percent,
            "memory_percent": telemetry.memory_percent,
            "gpu_percent": telemetry.gpu_percent,
            "gpu_temp_c": telemetry.gpu_temp_c,
            "cpu_temp_c": telemetry.cpu_temp_c,
            "fps": telemetry.fps,
            "timestamp": telemetry.timestamp or time.time(),
        },
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    envelope = {"payload": payload}
    if secret:
        envelope["signature"] = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
    result = json.dumps(envelope, separators=(",", ":")).encode()
    if len(result) > MAX_PACKET_BYTES:
        raise ValueError("telemetry packet is too large")
    return result


def decode(packet: bytes, secret: str = "") -> Telemetry:
    if len(packet) > MAX_PACKET_BYTES:
        raise ValueError("telemetry packet is too large")
    try:
        envelope = json.loads(packet)
        payload = envelope["payload"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("invalid telemetry packet") from exc
    if payload.get("v") != PROTOCOL_VERSION:
        raise ValueError("unsupported protocol version")
    if secret:
        canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        expected = hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(envelope.get("signature", "")), expected):
            raise ValueError("invalid telemetry signature")
    return Telemetry.from_mapping(payload.get("stats", {}))

