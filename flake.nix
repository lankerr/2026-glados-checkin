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
          default = pkgs.stdenv.mkDerivation {
            pname = "glados-checkin";
            version = "1.1.0";
            src = ./.;
            buildInputs = [ pythonEnv ];
            installPhase = ''
              mkdir -p $out/bin
              cp checkin.py $out/bin/glados-checkin
              chmod +x $out/bin/glados-checkin
              sed -i "1s|.*|#!${pythonEnv}/bin/python3|" $out/bin/glados-checkin
            '';
          };
        }
      );

      nixosModules.default = import ./glados-checkin.nix self;
    };
}
