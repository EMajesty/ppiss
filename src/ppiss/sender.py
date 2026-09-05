from __future__ import annotations

import argparse
import socket
import sys
import time

from .artwork import ArtworkServer
from .collectors import collect_gpus, collect_now_playing
from .protocol import NowPlaying, Telemetry, encode


def collect(now_playing: NowPlaying | None = None) -> Telemetry:
    try:
        import psutil
    except ImportError as exc:
        raise SystemExit("Install sender dependencies: pip install 'ppiss[sender]'") from exc

    temperatures = psutil.sensors_temperatures() if hasattr(psutil, "sensors_temperatures") else {}
    cpu_temp = next(
        (entry.current for group in temperatures.values() for entry in group if entry.current), None
    )
    return Telemetry(
        hostname=socket.gethostname(),
        cpu_percent=psutil.cpu_percent(interval=None),
        memory_percent=psutil.virtual_memory().percent,
        cpu_temp_c=cpu_temp,
        timestamp=time.time(),
        gpus=collect_gpus(),
        now_playing=now_playing,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Send PC telemetry to a PPISS display")
    parser.add_argument("--host", default="10.55.0.2", help="Pi address")
    parser.add_argument("--port", type=int, default=45891)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--art-port", type=int, default=45892)
    parser.add_argument("--mpd-host", default="127.0.0.1")
    parser.add_argument("--mpd-port", type=int, default=6600)
    args = parser.parse_args()

    if sys.platform != "linux":
        raise SystemExit("The PPISS telemetry sender supports Linux only")

    artwork = ArtworkServer("0.0.0.0", args.art_port)
    artwork.start()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((args.host, args.port))
        advertised_host = sock.getsockname()[0]
        try:
            while True:
                playing, source = collect_now_playing(args.mpd_host, args.mpd_port)
                artwork.update(playing.artwork_id if playing else None, source)
                if playing and playing.artwork_id and artwork.data:
                    playing = NowPlaying(
                        playing.player, playing.state, playing.title, playing.artist, playing.album,
                        playing.artwork_id, f"http://{advertised_host}:{args.art_port}/art/{playing.artwork_id}",
                    )
                sock.send(encode(collect(playing)))
                time.sleep(max(0.1, args.interval))
        finally:
            artwork.stop()


if __name__ == "__main__":
    main()
