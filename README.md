# PPISS

ABSOLUTELY VIBECODED <3

![PPISS display showing telemetry, album art, and a procedural background](assets/ppiss-screenshot.png)

A generative, retro-styled PC status display for a Raspberry Pi Zero W and a portrait HDMI screen.
Its original low-resolution patterns use layered palette cycling, scrolling, and sinusoidal scanline
distortion inspired by techniques used in 16-bit-era battle backgrounds. It contains no game assets.
PC statistics are drawn as a stable, monospace terminal table over the animation.

```text
Linux PC -> UDP over USB Ethernet -> Raspberry Pi -> HDMI
```

## Pi

Install Raspberry Pi OS Lite, enable SSH, then run:

```sh
curl -fsSL https://raw.githubusercontent.com/EMajesty/ppiss/main/deploy/install-pi.sh | sudo sh
sudo reboot
```

The installer configures direct DRM/KMS rendering, USB Ethernet, and a system service. It defaults
to the 1280×800 test display rotated 90 degrees. Override the mode with `PPISS_VIDEO_MODE`, or set it
to an empty string to use EDID without rotation.

Connect the PC to the Pi Zero's USB **data** port. The Pi uses `10.55.0.2` and UDP port `45891`.

## PC

Add the repository to your Nix flake:

```nix
inputs.ppiss.url = "github:EMajesty/ppiss";
inputs.ppiss.inputs.nixpkgs.follows = "nixpkgs";
```

Import and configure it in Home Manager:

```nix
{ inputs, ... }:
{
  imports = [ inputs.ppiss.homeManagerModules.ppiss ];

  services.ppiss = {
    enable = true;
    host = "10.55.0.2";
    rgb.enable = true;
  };
}
```

This installs and starts the Linux telemetry sender as a systemd user service.

For the ASRock B650M Pro RS WiFi, PPISS can also mirror the animation onto six 12-LED A-RGB
fans through OpenRGB. Connect two daisy-chained fans to each 5 V addressable header (never the 12 V
RGB header); leave fan PWM on the motherboard fan headers. Each pair mirrors one sampled region
because the fans' A-RGB splitter is parallel. `rgb.enable` starts a localhost OpenRGB server,
configures the three 12-LED addressable zones, and updates them at 10 Hz. On NixOS, also set
`services.hardware.openrgb.enable = true;` in the system configuration so the user service gets HID access.
Brightness defaults to 35% and can be changed with `services.ppiss.rgb.brightness`.

## Development

```sh
direnv allow
./scripts/run-demo.sh
```

Without direnv, run `nix develop` first.
The script starts both the windowed display and a local telemetry sender, then stops the sender when
the display closes. Additional arguments are passed to the display.

Run tests with `python -m unittest discover -s tests`.

## Status

CPU, memory, temperature, and multi-GPU telemetry are implemented. NVIDIA uses `nvidia-smi`; AMD,
Intel, and other DRM devices use the metrics exposed by their kernel driver. Missing driver metrics
are omitted.

Spotify and other MPRIS players are detected through Playerctl, with direct MPD as a fallback.
While music is playing, metadata and album art appear on the Pi. Artwork is cached and served by the
PC on TCP port `45892`. Telemetry is unauthenticated and intended for the dedicated USB network.
