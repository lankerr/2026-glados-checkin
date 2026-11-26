{
  description = "GLaDOS Automatic Check-in";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      pkgsFor = system: import nixpkgs { inherit system; };
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
          pythonEnv = pkgs.python3.withPackages (ps: [ ps.requests ]);
        in
        {
          default = pkgs.stdenvNoCC.mkDerivation {
            pname = "glados-checkin";
            version = "1.1.0";
            src = ./.;
            buildInputs = [ pythonEnv ];
            installPhase = ''
              mkdir -p $out/bin $out/libexec/glados
              cp checkin.py $out/bin/glados-checkin
              cp checkin.py update_streak.py $out/libexec/glados/
              printf '#!%s\nexec %s/bin/python3 "%s/libexec/glados/update_streak.py" "$@"\n' ${pkgs.runtimeShell} ${pythonEnv} "$out" > $out/bin/glados-ledger
              chmod +x $out/bin/glados-{checkin,ledger}
              sed -i "1s|.*|#!${pythonEnv}/bin/python3|" $out/bin/glados-checkin
            '';
          };
        }
      );

      nixosModules.default = import ./glados-checkin.nix self;
    };
}
