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

    cookie = mkOption {
      type = types.str;
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
  };

  config = mkIf cfg.enable {
    systemd.services.glados-checkin = {
      description = "GLaDOS Automatic Check-in";
      wants = [ "network-online.target" ];
      after = [ "network-online.target" ];

      environment = {
        GLADOS_COOKIE = cfg.cookie;
        PUSH_LEVEL = cfg.pushLevel;
      }
      // (optionalAttrs (cfg.telegramBotToken != null) {
        TELEGRAM_BOT_TOKEN = cfg.telegramBotToken;
      })
      // (optionalAttrs (cfg.telegramChatId != null) {
        TELEGRAM_CHAT_ID = cfg.telegramChatId;
      })
      // (optionalAttrs (cfg.pushplusToken != null) {
        PUSHPLUS_TOKEN = cfg.pushplusToken;
      });

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${self.packages.${pkgs.system}.default}/bin/glados-checkin";
        LoadCredential = [ ]; # Can be used for secrets later if needed
        DynamicUser = true;
      };
    };

    systemd.timers.glados-checkin = {
      description = "Timer for GLaDOS Automatic Check-in";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = [
          "*-*-* 09:30:00"
        ];
        RandomizedDelaySec = "10m";
        Persistent = true;
      };
    };
  };
}
