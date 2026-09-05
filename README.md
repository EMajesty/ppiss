# PPISS

ABSOLUTELY VIBECODED SLOP <3

A lightweight, original generative system monitor for a Raspberry Pi Zero W. It renders an evolving psychedelic background with a readable PC-stat overlay on a portrait HDMI display. The visual mood draws from the kinetic, abstract energy of 16-bit RPG battle backgrounds without copying game assets.

The PC sends a compact JSON telemetry packet over UDP. USB Ethernet is the intended link, but Wi-Fi or wired LAN works without code changes.

## Architecture

```text
PC: psutil -> ppiss-send -> UDP/45891 -> USB Ethernet -> Pi: ppiss-display -> HDMI
```

The display detects the active fullscreen resolution. Its animation canvas is generated at one-quarter resolution on each axis and nearest-neighbor scaled to the panel; the overlay is laid out at native resolution. This gives the image a crisp retro texture and reduces work for the Pi Zero.

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

## Linux PC sender

The monitored PC must run Linux. Nix with the Home Manager module below is the primary installation
method. For a manual development installation, use Python 3.11+:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[sender]'
ppiss-send --host 10.55.0.2 --interval 1
```

CPU and memory are collected from Linux through psutil. CPU temperature availability depends on
the kernel and hardware sensor drivers. GPU metrics are included in the protocol but not collected
yet; they can later be populated through an NVIDIA/AMD-specific adapter without changing the Pi.

UDP telemetry is intentionally one-way and lossy: the newest sample matters, and an old sample should never block animation. The dedicated USB network is treated as a trusted link; telemetry is not encrypted or authenticated.

## Nix and Home Manager

The flake exports `packages`, a default `app`, a development shell, and
`homeManagerModules.ppiss`. Add PPISS as an input to the flake containing your Home Manager
configuration:

```nix
inputs.ppiss.url = "github:YOUR_ACCOUNT/ppiss";
inputs.ppiss.inputs.nixpkgs.follows = "nixpkgs";
```

Then import its module and configure the user service in your `ppiss.nix`:

```nix
{ inputs, ... }:
{
  imports = [ inputs.ppiss.homeManagerModules.ppiss ];

  services.ppiss = {
    enable = true;
    host = "10.55.0.2";
    port = 45891;
    interval = 1;
  };
}
```

The module installs PPISS and starts `ppiss-send` as a restarting systemd user service. You can
also run it without Home Manager using `nix run . -- --host 10.55.0.2`.

## Now playing and album art

This is feasible without making the renderer heavy. The intended extension is:

1. A PC-side adapter reads MPD or the Linux MPRIS interface used by Spotify clients.
2. Artist, title, album, playback state, and an artwork content ID travel in telemetry.
3. The PC exposes the current artwork over a tiny HTTP endpoint on the USB network.
4. The Pi fetches an image only when its content ID changes, scales it once, and caches it.
5. The overlay transitions to a now-playing layout while playback is active and returns to stats
   after a configurable idle timeout.

Artwork should not be fragmented into UDP packets: covers are much larger than telemetry and need
reliable transfer. MPD can expose embedded or local cover data; Spotify on Linux normally exposes
metadata and an artwork URL through MPRIS. Remote artwork may require the PC to fetch and proxy it,
so the Pi itself does not need general internet access. This adapter and artwork endpoint are not
implemented yet.

## Project layout

```text
src/ppiss/display.py   renderer and overlay
src/ppiss/receiver.py  non-blocking UDP receiver
src/ppiss/sender.py    Linux PC collector
src/ppiss/protocol.py  versioned telemetry protocol
deploy/                     systemd and USB network examples
tests/                      protocol tests
```

## Next useful extensions

- Add NVIDIA (`nvidia-smi`) and AMD telemetry adapters on the PC.
- Add named visual presets and slow palette transitions.
- Benchmark on the actual panel, then tune logical resolution and FPS.
- Add more Linux telemetry sources through optional collectors.
