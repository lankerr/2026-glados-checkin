self:
{
  config,
  lib,
  pkgs,
  ...
}:

with lib;

let
  cfg = config.services.glados-checkin;
in
{
  options.services.glados-checkin = {
    enable = mkEnableOption "GLaDOS Automatic Check-in Service";

    package = mkOption {
      type = types.package;
      default = self.packages.${pkgs.stdenv.hostPlatform.system}.default;
      description = "Package providing bin/glados-checkin or bin/glados-ledger for the chosen mode.";
    };

    mode = mkOption {
      type = types.enum [ "checkin" "ledger" ];
      default = "checkin";
      description = "Use ledger to report points history only (no check-in, redemption or push).";
    };

    checkinTime = mkOption {
      type = types.strMatching "([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]";
      default = "09:30:00";
      description = "Daily start time in the host timezone, HH:MM:SS (plus up to ten minutes of jitter).";
    };

    environmentFile = mkOption {
      type = types.nullOr (types.strMatching "/.+");
      default = null;
      description = "Absolute path to a runtime systemd EnvironmentFile containing GLADOS_COOKIE and optional notification settings.";
    };

    cookie = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "GLaDOS Cookie (or multiple cookies separated by && or newline). Keep it secret.";
    };

    pushLevel = mkOption {
      type = types.enum [
        "all"
        "fail_only"
      ];
      default = "all";
      description = "Level of notification pushing: 'all' or 'fail_only'.";
    };

    telegramBotToken = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Telegram Bot Token for notifications.";
    };

    telegramChatId = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Telegram Chat ID for notifications.";
    };

    pushplusToken = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "PushPlus Token for notifications.";
    };

    serverchanSendkey = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "ServerChan SendKey for notifications (Turbo or ServerChan 3).";
    };
  };

  config = mkIf cfg.enable {
    assertions = [{
      assertion = cfg.cookie != null || cfg.environmentFile != null;
      message = "Set services.glados-checkin.environmentFile or services.glados-checkin.cookie.";
    }];
    systemd.services.glados-checkin = {
      description = "GLaDOS Automatic Check-in";
      wants = [ "network-online.target" ];
      after = [ "network-online.target" ];

      environment = {
        PUSH_LEVEL = cfg.pushLevel;
      }
      // (optionalAttrs (cfg.cookie != null) { GLADOS_COOKIE = cfg.cookie; })
      // (optionalAttrs (cfg.telegramBotToken != null) {
        TELEGRAM_BOT_TOKEN = cfg.telegramBotToken;
      })
      // (optionalAttrs (cfg.telegramChatId != null) {
        TELEGRAM_CHAT_ID = cfg.telegramChatId;
      })
      // (optionalAttrs (cfg.pushplusToken != null) {
        PUSHPLUS_TOKEN = cfg.pushplusToken;
      })
      // (optionalAttrs (cfg.serverchanSendkey != null) {
        SERVERCHAN_SENDKEY = cfg.serverchanSendkey;
      });

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${cfg.package}/bin/${if cfg.mode == "ledger" then "glados-ledger" else "glados-checkin"}";
        DynamicUser = true;
        StateDirectory = "glados-checkin";
        WorkingDirectory = "%S/glados-checkin";
      } // optionalAttrs (cfg.environmentFile != null) { EnvironmentFile = cfg.environmentFile; };
    };

    systemd.timers.glados-checkin = {
      description = "Timer for GLaDOS Automatic Check-in";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = [
          "*-*-* ${cfg.checkinTime}"
        ];
        RandomizedDelaySec = "10m";
        Persistent = true;
      };
    };
  };
}
