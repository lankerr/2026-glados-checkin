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
      default =
        if cfg.browserEngine == "playwright" then
          self.packages.${pkgs.stdenv.hostPlatform.system}.withPlaywright
        else
          self.packages.${pkgs.stdenv.hostPlatform.system}.default;
      defaultText = literalExpression "self.packages.\${pkgs.stdenv.hostPlatform.system}.default (or withPlaywright if browserEngine == \"playwright\")";
      description = "The glados-checkin package to use.";
    };

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

    serverchanSendkey = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "ServerChan SendKey for notifications (Turbo or ServerChan 3).";
    };

    browserEngine = mkOption {
      type = types.enum [
        "auto"
        "cdp"
        "playwright"
      ];
      default = "auto";
      description = "Browser automation engine to use: 'auto' (prefers system browser CDP, falls back to Playwright), 'cdp', or 'playwright'.";
    };

    browserPackage = mkOption {
      type = types.nullOr types.package;
      default = null;
      description = "Optional browser package (e.g. pkgs.microsoft-edge) to provide in PATH for Turnstile verification fallback.";
    };

    browserHeadless = mkOption {
      type = types.nullOr types.bool;
      default = null;
      description = "Whether to run the browser fallback in headless mode (true -> '1', false -> '0', null -> auto-detect from DISPLAY/WAYLAND_DISPLAY).";
    };

    cdpUrl = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Custom local loopback CDP (Chrome DevTools Protocol) endpoint URL (e.g. http://127.0.0.1:9222 or ws://127.0.0.1:9222/devtools/browser).";
    };
  };

  config = mkIf cfg.enable {
    systemd.services.glados-checkin = {
      description = "GLaDOS Automatic Check-in";
      wants = [ "network-online.target" ];
      after = [ "network-online.target" ];
      path = optional (cfg.browserPackage != null) cfg.browserPackage;

      environment = {
        GLADOS_COOKIE = cfg.cookie;
        PUSH_LEVEL = cfg.pushLevel;
        GLADOS_BROWSER_ENGINE = cfg.browserEngine;
      }
      // (optionalAttrs (cfg.browserHeadless != null) {
        GLADOS_BROWSER_HEADLESS = if cfg.browserHeadless then "1" else "0";
      })
      // (optionalAttrs (cfg.browserEngine == "playwright") {
        PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright-driver.browsers}";
        PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS = "true";
      })
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
      })
      // (optionalAttrs (cfg.cdpUrl != null) {
        GLADOS_CDP_URL = cfg.cdpUrl;
      });

      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${cfg.package}/bin/glados-checkin";
        WorkingDirectory = "%S/glados-checkin";
        LoadCredential = [ ]; # Can be used for secrets later if needed
        DynamicUser = true;
        StateDirectory = "glados-checkin";
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
