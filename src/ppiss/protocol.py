"""Small, dependency-free PPISS wire protocol shared by display and sender."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

PROTOCOL_VERSION = 1
MAX_PACKET_BYTES = 8192


@dataclass(frozen=True, slots=True)
class GPU:
    name: str
    utilization_percent: float | None = None
    temperature_c: float | None = None


@dataclass(frozen=True, slots=True)
class NowPlaying:
    player: str
    state: str
    title: str
    artist: str = ""
    album: str = ""
    artwork_id: str | None = None
    artwork_url: str | None = None


@dataclass(frozen=True, slots=True)
class Disk:
    device: str
    percent: float
    used_gb: float
    total_gb: float


@dataclass(frozen=True, slots=True)
class Telemetry:
    hostname: str
    cpu_percent: float
    memory_percent: float
    cpu_name: str = "cpu"
    memory_used_gb: float = 0.0
    memory_total_gb: float = 0.0
    gpu_percent: float | None = None
    gpu_temp_c: float | None = None
    cpu_temp_c: float | None = None
    fps: float | None = None
    timestamp: float = 0.0
    gpus: tuple[GPU, ...] = ()
    now_playing: NowPlaying | None = None
    disks: tuple[Disk, ...] = ()

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> Telemetry:
        def number(name: str, *, optional: bool = False) -> float | None:
            raw = value.get(name)
            if raw is None and optional:
                return None
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise TypeError(f"{name} must be a number")
            return float(raw)

        hostname = value.get("hostname")
        if not isinstance(hostname, str) or not hostname[:64]:
            raise ValueError("hostname must be a non-empty string")
        gpus = tuple(
            GPU(
                name=str(gpu.get("name", "GPU"))[:96],
                utilization_percent=(float(gpu["utilization_percent"]) if gpu.get("utilization_percent") is not None else None),
                temperature_c=(float(gpu["temperature_c"]) if gpu.get("temperature_c") is not None else None),
            )
            for gpu in value.get("gpus", [])
            if isinstance(gpu, dict)
        )
        playing = value.get("now_playing")
        now_playing = None
        if isinstance(playing, dict) and playing.get("title"):
            now_playing = NowPlaying(
                player=str(playing.get("player", ""))[:64], state=str(playing.get("state", ""))[:16],
                title=str(playing["title"])[:256], artist=str(playing.get("artist", ""))[:256],
                album=str(playing.get("album", ""))[:256], artwork_id=playing.get("artwork_id"),
                artwork_url=playing.get("artwork_url"),
            )
        disks = tuple(
            Disk(
                device=str(disk.get("device", disk.get("mountpoint", "")))[:256],
                percent=float(disk.get("percent", 0)),
                used_gb=float(disk.get("used_gb", 0)),
                total_gb=float(disk.get("total_gb", 0)),
            )
            for disk in value.get("disks", [])
            if isinstance(disk, dict)
        )
        return cls(
            hostname=hostname[:64],
            cpu_percent=float(number("cpu_percent")),
            memory_percent=float(number("memory_percent")),
            cpu_name=str(value.get("cpu_name") or "cpu")[:128],
            memory_used_gb=float(number("memory_used_gb", optional=True) or 0),
            memory_total_gb=float(number("memory_total_gb", optional=True) or 0),
            gpu_percent=number("gpu_percent", optional=True),
            gpu_temp_c=number("gpu_temp_c", optional=True),
            cpu_temp_c=number("cpu_temp_c", optional=True),
            fps=number("fps", optional=True),
            timestamp=float(number("timestamp")),
            gpus=gpus,
            now_playing=now_playing,
            disks=disks,
        )


def encode(telemetry: Telemetry) -> bytes:
    payload = {
        "v": PROTOCOL_VERSION,
        "stats": {
            "hostname": telemetry.hostname,
            "cpu_percent": telemetry.cpu_percent,
            "memory_percent": telemetry.memory_percent,
            "cpu_name": telemetry.cpu_name,
            "memory_used_gb": telemetry.memory_used_gb,
            "memory_total_gb": telemetry.memory_total_gb,
            "gpu_percent": telemetry.gpu_percent,
            "gpu_temp_c": telemetry.gpu_temp_c,
            "cpu_temp_c": telemetry.cpu_temp_c,
            "fps": telemetry.fps,
            "timestamp": telemetry.timestamp or time.time(),
            "gpus": [
                {"name": gpu.name, "utilization_percent": gpu.utilization_percent, "temperature_c": gpu.temperature_c}
                for gpu in telemetry.gpus
            ],
            "now_playing": (
                {
                    "player": telemetry.now_playing.player, "state": telemetry.now_playing.state,
                    "title": telemetry.now_playing.title, "artist": telemetry.now_playing.artist,
                    "album": telemetry.now_playing.album, "artwork_id": telemetry.now_playing.artwork_id,
                    "artwork_url": telemetry.now_playing.artwork_url,
                } if telemetry.now_playing else None
            ),
            "disks": [
                {
                    "device": disk.device, "percent": disk.percent,
                    "used_gb": disk.used_gb, "total_gb": disk.total_gb,
                }
                for disk in telemetry.disks
            ],
        },
    }
    envelope = {"payload": payload}
    result = json.dumps(envelope, separators=(",", ":")).encode()
    if len(result) > MAX_PACKET_BYTES:
        raise ValueError("telemetry packet is too large")
    return result


def decode(packet: bytes) -> Telemetry:
    if len(packet) > MAX_PACKET_BYTES:
        raise ValueError("telemetry packet is too large")
    try:
        envelope = json.loads(packet)
        payload = envelope["payload"]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("invalid telemetry packet") from exc
    if payload.get("v") != PROTOCOL_VERSION:
        raise ValueError("unsupported protocol version")
    return Telemetry.from_mapping(payload.get("stats", {}))
