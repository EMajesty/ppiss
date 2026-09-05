from __future__ import annotations

import glob
import hashlib
import os
import pathlib
import subprocess

from .protocol import GPU, Disk, NowPlaying


def _float(value: str) -> float | None:
    try:
        return float(value.strip())
    except (ValueError, OSError):
        return None


def collect_gpus() -> tuple[GPU, ...]:
    found: list[GPU] = []
    seen_names: set[str] = set()
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2, check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = [part.strip() for part in line.split(",")]
                if len(parts) >= 3:
                    found.append(GPU(parts[0], _float(parts[1]), _float(parts[2])))
                    seen_names.add(parts[0])
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    for card_name in glob.glob("/sys/class/drm/card[0-9]*"):
        card = pathlib.Path(card_name)
        if not card.name.removeprefix("card").isdigit():
            continue
        device = card / "device"
        if not device.exists():
            continue
        driver = "GPU"
        try:
            driver = device.resolve().parent.name
            link = (device / "driver").resolve().name
            driver = {"amdgpu": "AMD GPU", "i915": "Intel GPU", "xe": "Intel GPU", "nouveau": "NVIDIA GPU"}.get(link, link)
        except OSError:
            pass
        if driver == "nvidia" and found:
            continue
        if any(driver.lower() in name.lower() for name in seen_names):
            continue
        utilization = _float((device / "gpu_busy_percent").read_text()) if (device / "gpu_busy_percent").exists() else None
        temperature = None
        for temp_file in device.glob("hwmon/hwmon*/temp1_input"):
            raw = _float(temp_file.read_text())
            if raw is not None:
                temperature = raw / 1000
                break
        found.append(GPU(f"{driver} ({card.name})", utilization, temperature))
    return tuple(found)


def _non_rotational_block_device(device: str) -> bool:
    name = os.path.basename(os.path.realpath(device))
    block = pathlib.Path("/sys/class/block") / name
    if not block.exists():
        return False
    if (block / "partition").exists():
        block = block.resolve().parent
    rotational = block / "queue/rotational"
    try:
        if rotational.exists():
            return rotational.read_text().strip() == "0"
        slaves = list((block / "slaves").iterdir())
        return bool(slaves) and all(_non_rotational_block_device(f"/dev/{slave.name}") for slave in slaves)
    except OSError:
        return False


def _physical_block_devices(device: str) -> tuple[str, ...]:
    name = os.path.basename(os.path.realpath(device))
    block = pathlib.Path("/sys/class/block") / name
    if not block.exists():
        return ()
    if (block / "partition").exists():
        block = block.resolve().parent
        name = block.name
    try:
        slaves = list((block / "slaves").iterdir())
    except OSError:
        slaves = []
    if not slaves:
        return (name,)
    physical = {
        physical_name
        for slave in slaves
        for physical_name in _physical_block_devices(f"/dev/{slave.name}")
    }
    return tuple(sorted(physical))


def collect_ssds(psutil_module) -> tuple[Disk, ...]:
    grouped: dict[tuple[str, ...], list[float]] = {}
    seen_filesystems = set()
    for partition in psutil_module.disk_partitions(all=False):
        device = os.path.realpath(partition.device)
        if device in seen_filesystems or not partition.device.startswith("/dev/"):
            continue
        if not _non_rotational_block_device(partition.device):
            continue
        physical = _physical_block_devices(partition.device)
        if not physical:
            continue
        try:
            usage = psutil_module.disk_usage(partition.mountpoint)
        except OSError:
            continue
        seen_filesystems.add(device)
        totals = grouped.setdefault(physical, [0.0, 0.0])
        totals[0] += usage.used
        totals[1] += usage.total
    return tuple(
        Disk(
            "+".join(devices),
            used / total * 100 if total else 0,
            used / 1024**3,
            total / 1024**3,
        )
        for devices, (used, total) in sorted(grouped.items())
    )


def _playerctl() -> tuple[NowPlaying | None, str | None]:
    try:
        names = subprocess.run(
            ["playerctl", "--list-all"], capture_output=True, text=True, timeout=2, check=False
        ).stdout.splitlines()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None, None
    candidates = []
    for name in names:
        try:
            state = subprocess.run(
                ["playerctl", "--player", name, "status"],
                capture_output=True, text=True, timeout=1, check=False,
            ).stdout.strip()
            metadata = subprocess.run(
                ["playerctl", "--player", name, "metadata", "--format", "{{title}}\u001f{{artist}}\u001f{{album}}\u001f{{mpris:artUrl}}"],
                capture_output=True, text=True, timeout=1, check=False,
            ).stdout.rstrip("\n").split("\x1f")
        except subprocess.TimeoutExpired:
            continue
        if metadata and metadata[0]:
            candidates.append((state != "Playing", name, state, (metadata + ["", "", ""])[:4]))
    if not candidates:
        return None, None
    _, name, state, data = min(candidates, key=lambda item: item[0])
    art_source = data[3] or None
    art_id = hashlib.sha256(art_source.encode()).hexdigest()[:20] if art_source else None
    return NowPlaying(name, state.lower(), data[0], data[1], data[2], art_id), art_source


def collect_now_playing(mpd_host: str, mpd_port: int) -> tuple[NowPlaying | None, str | bytes | None]:
    playing, art = _playerctl()
    if playing and playing.state == "playing":
        return playing, art
    try:
        from mpd import CommandError, MPDClient, ProtocolError
        from mpd import ConnectionError as MPDConnectionError
    except ImportError:
        return playing, art
    mpd_errors = (CommandError, MPDConnectionError, ProtocolError, OSError, ValueError, TypeError)
    try:
        client = MPDClient()
        client.timeout = 2
        client.connect(mpd_host, mpd_port)
        status, song = client.status(), client.currentsong()
        if not song:
            client.close()
            return playing, art
        artwork = None
        for command in (client.readpicture, client.albumart):
            try:
                response = command(song.get("file", ""))
                artwork = response.get("binary") or None
                if artwork:
                    break
            except mpd_errors:
                pass
        client.close()
        art_id = hashlib.sha256(artwork).hexdigest()[:20] if artwork else None
        return NowPlaying("mpd", status.get("state", "stop"), song.get("title") or song.get("file", ""), song.get("artist", ""), song.get("album", ""), art_id), artwork
    except mpd_errors:
        return playing, art
