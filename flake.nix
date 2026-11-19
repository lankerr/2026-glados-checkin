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
          makePkg =
            { withPlaywright ? false }:
            let
              pythonEnv = pkgs.python3.withPackages (
                ps: [ ps.requests ] ++ nixpkgs.lib.optional withPlaywright ps.playwright
              );
            in
            pkgs.stdenv.mkDerivation {
              pname = "glados-checkin" + (if withPlaywright then "-playwright" else "");
              version = "1.1.0";
              src = ./.;
              buildInputs = [ pythonEnv ];
              installPhase = ''
                mkdir -p $out/bin
                cp checkin.py $out/bin/glados-checkin
                cp browser_checkin.py $out/bin/browser_checkin.py
                chmod +x $out/bin/glados-checkin
                sed -i "1s|.*|#!${pythonEnv}/bin/python3|" $out/bin/glados-checkin
              '';
              meta.mainProgram = "glados-checkin";
            };
        in
        {
          default = makePkg { withPlaywright = false; };
          withPlaywright = makePkg { withPlaywright = true; };
        }
      );

      nixosModules.default = import ./glados-checkin.nix self;
    };
}
