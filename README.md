# PPISS

ABSOLUTELY VIBECODED SLOP <3

A lightweight, original generative system monitor for a Raspberry Pi Zero W. It renders an evolving psychedelic background with a readable PC-stat overlay on an 800×1280 portrait HDMI display. The visual mood draws from the kinetic, abstract energy of 16-bit RPG battle backgrounds without copying game assets.

The PC sends a compact JSON telemetry packet over UDP. USB Ethernet is the intended link, but Wi-Fi or wired LAN works without code changes.

## Architecture

```text
PC: psutil -> ppiss-send -> UDP/45891 -> USB Ethernet -> Pi: ppiss-display -> HDMI
```

The animation is drawn at 200×320 and nearest-neighbor scaled to 800×1280. This is intentional: it gives the image a crisp retro texture and reduces work for the Pi Zero.

## Try it on a development machine

Requires Python 3.11+.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[pi,sender,dev]'
ppiss-display --windowed
```

In a second terminal:

```sh
. .venv/bin/activate
ppiss-send --host 127.0.0.1
```

Escape closes the development window. Run tests with `python -m unittest discover -s tests`
(or `pytest`) and lint with `ruff check .`.

## Raspberry Pi installation

Use Raspberry Pi OS Lite 64-bit (Bookworm or newer). Configure the HDMI panel for portrait orientation in `/boot/firmware/cmdline.txt` or the display's own controls; the app always requests 800×1280.

```sh
sudo apt update
sudo apt install -y python3-venv python3-pygame git
sudo mkdir -p /opt/ppiss
sudo chown "$USER" /opt/ppiss
git clone YOUR_REPOSITORY_URL /opt/ppiss
cd /opt/ppiss
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e .
sudo cp deploy/ppiss.service /etc/systemd/system/
sudo cp config/ppiss.env.example /etc/ppiss.env
sudo systemctl daemon-reload
sudo systemctl enable --now ppiss
```

Change `User=pi` in the service if the Pi account has a different name. Some displays need `SDL_VIDEODRIVER=wayland` or no explicit video driver; adjust the service if KMSDRM is unavailable.

## USB Ethernet link

Pi Zero W USB gadget mode uses the **USB data** port, not the power-only port. Before editing boot files, keep a backup or a second way to access the Pi.

1. Add `dtoverlay=dwc2` on its own line in `/boot/firmware/config.txt`.
2. In the single line of `/boot/firmware/cmdline.txt`, append `modules-load=dwc2,g_ether`.
3. Copy `deploy/10-usb0.network` to `/etc/systemd/network/10-usb0.network` and enable `systemd-networkd`, or configure `usb0` as `10.55.0.2/24` with NetworkManager.
4. Reboot and connect the Pi data port to the PC. Set the PC side to `10.55.0.1/24` if it does not obtain an address automatically.
5. Allow outbound UDP port 45891 in the PC firewall and run `ppiss-send --host 10.55.0.2`.

USB gadget details vary across Pi OS images, so verify interface names with `ip link`. Regular Wi-Fi is a useful first test: pass the Pi's Wi-Fi address to `ppiss-send`.

## PC sender

Install Python 3.11+ and the sender only:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: . .venv/bin/activate
pip install -e '.[sender]'
ppiss-send --host 10.55.0.2 --interval 1
```

CPU and memory work on Windows, Linux, and macOS through psutil. CPU temperature availability depends on the OS. GPU metrics are included in the protocol but not collected yet; they can later be populated through an NVIDIA/AMD-specific adapter without changing the Pi.

For packet authentication, set `PPISS_SECRET` on the Pi and pass the same value using `ppiss-send --secret VALUE`. UDP telemetry is intentionally one-way and lossy: the newest sample matters, and an old sample should never block animation.

## Project layout

```text
src/ppiss/display.py   renderer and overlay
src/ppiss/receiver.py  non-blocking UDP receiver
src/ppiss/sender.py    cross-platform PC collector
src/ppiss/protocol.py  versioned optional-HMAC protocol
deploy/                     systemd and USB network examples
tests/                      protocol tests
```

## Next useful extensions

- Add NVIDIA (`nvidia-smi`) and AMD telemetry adapters on the PC.
- Add named visual presets and slow palette transitions.
- Benchmark on the actual panel, then tune logical resolution and FPS.
- Add sender auto-start (Windows Task Scheduler or a user systemd service).
