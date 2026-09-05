from __future__ import annotations

import glob
import hashlib
import pathlib
import subprocess
import urllib.parse

from .protocol import GPU, NowPlaying


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


def _playerctl() -> tuple[NowPlaying | None, str | None]:
    try:
        names = subprocess.run(["playerctl", "--list-all"], capture_output=True, text=True, timeout=2).stdout.splitlines()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None, None
    candidates = []
    for name in names:
        try:
            state = subprocess.run(["playerctl", "--player", name, "status"], capture_output=True, text=True, timeout=1).stdout.strip()
            metadata = subprocess.run(
                ["playerctl", "--player", name, "metadata", "--format", "{{title}}\u001f{{artist}}\u001f{{album}}\u001f{{mpris:artUrl}}"],
                capture_output=True, text=True, timeout=1,
            ).stdout.rstrip("\n").split("\x1f")
        except subprocess.TimeoutExpired:
            continue
        if metadata and metadata[0]:
            candidates.append((state != "Playing", name, state, (metadata + ["", "", ""])[:4]))
    if not candidates:
        return None, None
    _, name, state, data = sorted(candidates, key=lambda item: item[0])[0]
    art_source = data[3] or None
    art_id = hashlib.sha256(art_source.encode()).hexdigest()[:20] if art_source else None
    return NowPlaying(name, state.lower(), data[0], data[1], data[2], art_id), art_source


def collect_now_playing(mpd_host: str, mpd_port: int) -> tuple[NowPlaying | None, str | bytes | None]:
    playing, art = _playerctl()
    if playing and playing.state == "playing":
        return playing, art
    try:
        from mpd import MPDClient
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
                chunks = bytearray()
                while True:
                    response = command(song.get("file", ""), len(chunks))
                    chunk = response.get("binary", b"")
                    if not chunk:
                        break
                    chunks.extend(chunk)
                    if len(chunks) >= int(response.get("size", len(chunks))):
                        artwork = bytes(chunks)
                        break
                if artwork:
                    break
            except Exception:
                continue
        client.close()
        art_id = hashlib.sha256(artwork).hexdigest()[:20] if artwork else None
        return NowPlaying("mpd", status.get("state", "stop"), song.get("title") or song.get("file", ""), song.get("artist", ""), song.get("album", ""), art_id), artwork
    except Exception:
        return playing, art
