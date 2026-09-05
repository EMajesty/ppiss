from __future__ import annotations

import argparse
import socket
import time

from .protocol import Telemetry, encode


def collect() -> Telemetry:
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
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Send PC telemetry to a PPISS display")
    parser.add_argument("--host", default="10.55.0.2", help="Pi address")
    parser.add_argument("--port", type=int, default=45891)
    parser.add_argument("--interval", type=float, default=1.0)
    args = parser.parse_args()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        while True:
            sock.sendto(encode(collect()), (args.host, args.port))
            time.sleep(max(0.1, args.interval))


if __name__ == "__main__":
    main()
