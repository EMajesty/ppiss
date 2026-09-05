flake: { config, lib, pkgs, ... }:
let cfg = config.services.ppiss;
in {
  options.services.ppiss = {
    enable = lib.mkEnableOption "PPISS PC telemetry sender";
    package = lib.mkOption {
      type = lib.types.package;
      default = flake.packages.${pkgs.stdenv.hostPlatform.system}.default;
      defaultText = lib.literalExpression "ppiss.packages.${pkgs.system}.default";
      description = "PPISS package to use.";
    };
    host = lib.mkOption {
      type = lib.types.str;
      default = "10.55.0.2";
      description = "Hostname or address of the Raspberry Pi display.";
    };
    port = lib.mkOption {
      type = lib.types.port;
      default = 45891;
      description = "UDP telemetry port on the display.";
    };
    interval = lib.mkOption {
      type = lib.types.ints.positive;
      default = 1;
      description = "Seconds between telemetry samples.";
    };
    artworkPort = lib.mkOption {
      type = lib.types.port;
      default = 45892;
      description = "TCP port used to serve album artwork to the display.";
    };
    mpdHost = lib.mkOption {
      type = lib.types.str;
      default = "127.0.0.1";
      description = "MPD server address.";
    };
    mpdPort = lib.mkOption {
      type = lib.types.port;
      default = 6600;
      description = "MPD server port.";
    };
    rgb = {
      enable = lib.mkEnableOption "PPISS animation-synchronised case lighting";
      port = lib.mkOption {
        type = lib.types.port;
        default = 45893;
        description = "UDP port receiving sampled animation colours from the display.";
      };
      brightness = lib.mkOption {
        type = lib.types.float;
        default = 0.35;
        description = "Lighting brightness multiplier from 0.0 to 1.0.";
      };
      device = lib.mkOption {
        type = lib.types.str;
        default = "ASRock B650M Pro RS WiFi";
        description = "OpenRGB motherboard device name.";
      };
      openrgbPort = lib.mkOption {
        type = lib.types.port;
        default = 6742;
        description = "Local OpenRGB SDK server port.";
      };
      startOpenRGB = lib.mkOption {
        type = lib.types.bool;
        default = true;
        description = "Start a localhost-only OpenRGB SDK server.";
      };
    };
  };
  config = lib.mkIf cfg.enable {
    assertions = [{
      assertion = cfg.rgb.brightness >= 0.0 && cfg.rgb.brightness <= 1.0;
      message = "services.ppiss.rgb.brightness must be between 0.0 and 1.0";
    }];
    home.packages = [ cfg.package pkgs.playerctl ] ++ lib.optional cfg.rgb.enable pkgs.openrgb;
    systemd.user.services.ppiss-openrgb = lib.mkIf (cfg.rgb.enable && cfg.rgb.startOpenRGB) {
      Unit.Description = "OpenRGB SDK server for PPISS";
      Service = {
        ExecStart = lib.concatStringsSep " " [
          "${pkgs.openrgb}/bin/openrgb"
          "--server --server-host 127.0.0.1"
          "--server-port ${toString cfg.rgb.openrgbPort}"
          "--noautoconnect"
        ];
        Restart = "on-failure";
        RestartSec = 3;
      };
      Install.WantedBy = [ "default.target" ];
    };
    systemd.user.services.ppiss = {
      Unit = {
        Description = "PPISS PC telemetry sender";
        After = [ "network-online.target" ]
          ++ lib.optional (cfg.rgb.enable && cfg.rgb.startOpenRGB) "ppiss-openrgb.service";
        Wants = [ "network-online.target" ]
          ++ lib.optional (cfg.rgb.enable && cfg.rgb.startOpenRGB) "ppiss-openrgb.service";
      };
      Service = {
        ExecStart = lib.concatStringsSep " " ([
          "${cfg.package}/bin/ppiss-send"
          "--host ${lib.escapeShellArg cfg.host}"
          "--port ${toString cfg.port}"
          "--interval ${toString cfg.interval}"
          "--art-port ${toString cfg.artworkPort}"
          "--mpd-host ${lib.escapeShellArg cfg.mpdHost}"
          "--mpd-port ${toString cfg.mpdPort}"
        ] ++ lib.optionals cfg.rgb.enable [
          "--rgb"
          "--rgb-port ${toString cfg.rgb.port}"
          "--openrgb-port ${toString cfg.rgb.openrgbPort}"
          "--openrgb-device ${lib.escapeShellArg cfg.rgb.device}"
          "--rgb-brightness ${toString cfg.rgb.brightness}"
        ]);
        Restart = "on-failure";
        RestartSec = 3;
      };
      Install.WantedBy = [ "default.target" ];
    };
  };
}
