# Evaluate the repository's service and timer with a dummy account setting.
let
  project = builtins.getFlake ("path:" + toString ../..);
  host = project.inputs.nixpkgs.lib.nixosSystem {
    system = "x86_64-linux";
    modules = [
      project.nixosModules.default
      {
        system.stateVersion = "26.05";
        services.glados-checkin = { enable = true; cookie = "demo"; };
      }
    ];
  };
  service = host.config.systemd.services.glados-checkin;
  timer = host.config.systemd.timers.glados-checkin.timerConfig;
in {
  inherit (timer) OnCalendar Persistent RandomizedDelaySec;
  inherit (service.serviceConfig) DynamicUser Type;
  StateDirectory = service.serviceConfig.StateDirectory or null;
  WorkingDirectory = service.serviceConfig.WorkingDirectory or null;
}
