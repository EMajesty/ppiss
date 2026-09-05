# PPISS

ABSOLUTELY VIBECODED SLOP <3

A generative, retro-styled PC status display for a Raspberry Pi Zero W and a portrait HDMI screen.

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
  };
}
```

This installs and starts the Linux telemetry sender as a systemd user service.

## Development

```sh
nix develop
pip install -e '.[pi,sender,dev]'
ppiss-display --windowed
```

In another terminal:

```sh
ppiss-send --host 127.0.0.1
```

Run tests with `python -m unittest discover -s tests`.

## Status

CPU, memory, and CPU temperature telemetry are implemented. GPU telemetry, MPD/MPRIS now-playing
metadata, and album-art transfer are planned but not implemented. Telemetry is unauthenticated and
intended for the dedicated USB network.
