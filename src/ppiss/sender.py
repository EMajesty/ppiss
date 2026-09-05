from __future__ import annotations

import argparse
import functools
import socket
import sys
import time

from .artwork import ArtworkServer
from .collectors import collect_gpus, collect_now_playing, collect_ssds
from .protocol import NowPlaying, Telemetry, encode
from .rgb import RGB_PORT, ZONE_NAMES, OpenRGBOutput


@functools.lru_cache(maxsize=1)
def cpu_name() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as cpuinfo:
            for line in cpuinfo:
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return "cpu"


def collect(now_playing: NowPlaying | None = None) -> Telemetry:
    try:
        import psutil
    except ImportError as exc:
        raise SystemExit("Install sender dependencies: pip install 'ppiss[sender]'") from exc

    temperatures = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
    memory = psutil.virtual_memory()
    cpu_temp = next(
        (entry.current for group in temperatures.values() for entry in group if entry.current), None
    )
    return Telemetry(
        hostname=socket.gethostname(),
        cpu_percent=psutil.cpu_percent(interval=None),
        memory_percent=memory.percent,
        cpu_name=cpu_name(),
        memory_used_gb=memory.used / 1024**3,
        memory_total_gb=memory.total / 1024**3,
        cpu_temp_c=cpu_temp,
        timestamp=time.time(),
        gpus=collect_gpus(),
        now_playing=now_playing,
        disks=collect_ssds(psutil),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Send PC telemetry to a PPISS display")
    parser.add_argument("--host", default="10.55.0.2", help="Pi address")
    parser.add_argument("--port", type=int, default=45891)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--art-port", type=int, default=45892)
    parser.add_argument("--mpd-host", default="127.0.0.1")
    parser.add_argument("--mpd-port", type=int, default=6600)
    parser.add_argument("--rgb", action="store_true", help="Drive OpenRGB zones from the display")
    parser.add_argument("--rgb-bind", default="0.0.0.0")
    parser.add_argument("--rgb-port", type=int, default=RGB_PORT)
    parser.add_argument("--openrgb-host", default="127.0.0.1")
    parser.add_argument("--openrgb-port", type=int, default=6742)
    parser.add_argument("--openrgb-device", default="ASRock B650M Pro RS WiFi")
    parser.add_argument("--rgb-brightness", type=float, default=0.35)
    args = parser.parse_args()

    if sys.platform != "linux":
        raise SystemExit("The PPISS telemetry sender supports Linux only")

    artwork = ArtworkServer("0.0.0.0", args.art_port)
    artwork.start()
    rgb = OpenRGBOutput(
        args.rgb_bind, args.rgb_port, args.openrgb_host, args.openrgb_port,
        args.openrgb_device, ZONE_NAMES, args.rgb_brightness,
    ) if args.rgb else None
    if rgb:
        rgb.start()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.connect((args.host, args.port))
        advertised_host = probe.getsockname()[0]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            while True:
                playing, source = collect_now_playing(args.mpd_host, args.mpd_port)
                artwork.update(playing.artwork_id if playing else None, source)
                if playing and playing.artwork_id and artwork.data:
                    playing = NowPlaying(
                        playing.player, playing.state, playing.title, playing.artist, playing.album,
                        playing.artwork_id, f"http://{advertised_host}:{args.art_port}/art/{playing.artwork_id}",
                    )
                sock.sendto(encode(collect(playing)), (args.host, args.port))
                time.sleep(max(0.1, args.interval))
        finally:
            if rgb:
                rgb.stop()
            artwork.stop()


if __name__ == "__main__":
    main()
