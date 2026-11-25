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
  sys = pkgs.stdenv.hostPlatform.system;

  timeParts = splitString ":" cfg.checkinTime;
  checkinHour = toIntBase10 (elemAt timeParts 0);
  checkinMinute = if length timeParts > 1 then toIntBase10 (elemAt timeParts 1) else 0;

  darwinStateDir = "${config.xdg.stateHome}/glados-checkin";

  formatSystemdEnv =
    k: v:
    let
      escaped = replaceStrings [ "\\" "\"" "\n" "%" ] [ "\\\\" "\\\"" "\\n" "%%" ] v;
    in
    ''"${k}=${escaped}"'';

  envAttrs = {
    PUSH_LEVEL = cfg.pushLevel;
    GLADOS_BROWSER_ENGINE = cfg.browserEngine;
  }
  // (optionalAttrs (cfg.cookie != null) {
    GLADOS_COOKIE = cfg.cookie;
  })
  // (optionalAttrs (cfg.exchangePlan != null) {
    EXCHANGE_PLAN = cfg.exchangePlan;
  })
  // (optionalAttrs (cfg.userAgent != null) {
    GLADOS_USER_AGENT = cfg.userAgent;
  })
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

  runnerScript = pkgs.writeShellScript "glados-checkin-hm" ''
    ${optionalString (cfg.browserPackage != null) ''
      export PATH="${makeBinPath [ cfg.browserPackage ]}:$PATH"
    ''}
    ${optionalString pkgs.stdenv.isDarwin ''
      export STATE_DIRECTORY="${darwinStateDir}"
      mkdir -p "$STATE_DIRECTORY"
      cd "$STATE_DIRECTORY"
      ${optionalString (cfg.environmentFile != null) ''
        if [ -f "${cfg.environmentFile}" ]; then
          set -a
          . "${cfg.environmentFile}"
          set +a
        fi
      ''}
    ''}
    exec "${cfg.package}/bin/glados-checkin"
  '';
in
{
  options.services.glados-checkin = {
    enable = mkEnableOption "GLaDOS Automatic Check-in User Service";

    package = mkOption {
      type = types.package;
      default =
        if cfg.browserEngine == "playwright" then
          self.packages.${sys}.withPlaywright
        else
          self.packages.${sys}.default;
      defaultText = literalExpression "self.packages.\${pkgs.stdenv.hostPlatform.system}.default (or withPlaywright if browserEngine == \"playwright\")";
      description = "The glados-checkin package to use.";
    };

    cookie = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "GLaDOS Cookie (or multiple cookies separated by && or newline). Prefer environmentFile to avoid storing secrets in the Nix store.";
    };

    environmentFile = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Optional path to an environment file containing secrets (e.g. GLADOS_COOKIE, TELEGRAM_BOT_TOKEN) rendered by sops-nix or agenix.";
    };

    pushLevel = mkOption {
      type = types.enum [
        "all"
        "fail_only"
      ];
      default = "all";
      description = "Level of notification pushing: 'all' or 'fail_only'.";
    };

    exchangePlan = mkOption {
      type = types.nullOr (
        types.enum [
          "plan100"
          "plan200"
          "plan500"
          "off"
        ]
      );
      default = null;
      description = "Point exchange plan: 'plan100', 'plan200', 'plan500', or 'off'.";
    };

    userAgent = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Custom User-Agent matching your browser.";
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
      description = "Browser automation engine to use: 'auto', 'cdp', or 'playwright'.";
    };

    browserPackage = mkOption {
      type = types.nullOr types.package;
      default = null;
      description = "Optional browser package (e.g. pkgs.microsoft-edge) to provide in PATH for Turnstile verification fallback.";
    };

    browserHeadless = mkOption {
      type = types.nullOr types.bool;
      default = null;
      description = "Whether to run the browser fallback in headless mode (true -> '1', false -> '0', null -> auto-detect from DISPLAY/WAYLAND_DISPLAY or macOS desktop).";
    };

    cdpUrl = mkOption {
      type = types.nullOr types.str;
      default = null;
      description = "Custom local loopback CDP endpoint URL (e.g. http://127.0.0.1:9222 or ws://127.0.0.1:9222/devtools/browser).";
    };

    checkinTime = mkOption {
      type = types.str;
      default = "09:30:00";
      description = "Daily check-in time in HH:MM:SS (Linux systemd OnCalendar) or HH:MM (macOS launchd StartCalendarInterval).";
    };

    randomizedDelaySec = mkOption {
      type = types.str;
      default = "10m";
      description = "Random delay added to Linux systemd timer.";
    };
  };

  config = mkIf cfg.enable (mkMerge [
    {
      assertions = [
        {
          assertion = cfg.cookie != null || cfg.environmentFile != null;
          message = "services.glados-checkin: either `cookie` or `environmentFile` must be set.";
        }
      ];
    }

    (mkIf pkgs.stdenv.isLinux {
      systemd.user.services.glados-checkin = {
        Unit = {
          Description = "GLaDOS Automatic Check-in";
          After = optional (cfg.browserHeadless != true) "graphical-session.target";
        };

        Service = {
          Type = "oneshot";
          ExecStart = "${runnerScript}";
          WorkingDirectory = "%S/glados-checkin";
          StateDirectory = "glados-checkin";
          Environment = mapAttrsToList formatSystemdEnv envAttrs;
        }
        // (optionalAttrs (cfg.environmentFile != null) {
          EnvironmentFile = cfg.environmentFile;
        });
      };

      systemd.user.timers.glados-checkin = {
        Unit = {
          Description = "Timer for GLaDOS Automatic Check-in";
        };
        Timer = {
          OnCalendar = "*-*-* ${cfg.checkinTime}";
          RandomizedDelaySec = cfg.randomizedDelaySec;
          Persistent = true;
        };
        Install = {
          WantedBy = [ "timers.target" ];
        };
      };
    })

    (mkIf pkgs.stdenv.isDarwin {
      launchd.agents.glados-checkin = {
        enable = true;
        config = {
          ProgramArguments = [ "${runnerScript}" ];
          EnvironmentVariables = envAttrs;
          StartCalendarInterval = [
            {
              Hour = checkinHour;
              Minute = checkinMinute;
            }
          ];
          StandardOutPath = "${darwinStateDir}/launchd.log";
          StandardErrorPath = "${darwinStateDir}/launchd.err.log";
        };
      };
    })
  ]);
}
