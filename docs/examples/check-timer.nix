# Evaluate the repository's service and timer with a dummy account setting.
let
  project = builtins.getFlake ("path:" + toString ../..);
  makeHost = settings: project.inputs.nixpkgs.lib.nixosSystem {
    system = "x86_64-linux";
    modules = [
      project.nixosModules.default
      ({ pkgs, ... }: {
        system.stateVersion = "26.05";
        services.glados-checkin = { enable = true; } // settings pkgs;
      })
    ];
  };
  host = makeHost (_: { cookie = "demo"; });
  runtimeHost = makeHost (pkgs: {
    environmentFile = "/run/secrets/glados.env";
    package = pkgs.writeShellScriptBin "glados-checkin" "exit 0";
  });
  unconfigured = makeHost (_: {});
  runtimeService = runtimeHost.config.systemd.services.glados-checkin;
  service = host.config.systemd.services.glados-checkin;
  timer = host.config.systemd.timers.glados-checkin.timerConfig;
in
assert service.environment.GLADOS_COOKIE == "demo";
assert !(service.serviceConfig ? EnvironmentFile);
assert !(runtimeService.environment ? GLADOS_COOKIE);
assert runtimeService.serviceConfig.EnvironmentFile == "/run/secrets/glados.env";
assert runtimeService.serviceConfig.ExecStart == "${runtimeHost.config.services.glados-checkin.package}/bin/glados-checkin";
assert builtins.any (item: !item.assertion && item.message == "Set services.glados-checkin.environmentFile or services.glados-checkin.cookie.") unconfigured.config.assertions;
{
  inherit (runtimeService.serviceConfig) EnvironmentFile;
  inherit (timer) OnCalendar Persistent RandomizedDelaySec;
  inherit (service.serviceConfig) DynamicUser Type;
  StateDirectory = service.serviceConfig.StateDirectory or null;
  WorkingDirectory = service.serviceConfig.WorkingDirectory or null;
}
