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
  };
  config = lib.mkIf cfg.enable {
    home.packages = [ cfg.package ];
    systemd.user.services.ppiss = {
      Unit = {
        Description = "PPISS PC telemetry sender";
        After = [ "network-online.target" ];
        Wants = [ "network-online.target" ];
      };
      Service = {
        ExecStart = lib.concatStringsSep " " [
          "${cfg.package}/bin/ppiss-send"
          "--host ${lib.escapeShellArg cfg.host}"
          "--port ${toString cfg.port}"
          "--interval ${toString cfg.interval}"
        ];
        Restart = "on-failure";
        RestartSec = 3;
      };
      Install.WantedBy = [ "default.target" ];
    };
  };
}
