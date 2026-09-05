{
  description = "PPISS PC telemetry sender and Home Manager module";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      packageFor = pkgs: pkgs.python3Packages.buildPythonApplication {
        pname = "ppiss";
        version = "0.1.0";
        pyproject = true;
        src = self;
        build-system = [ pkgs.python3Packages.setuptools ];
        dependencies = [
          pkgs.python3Packages.psutil
          pkgs.python3Packages.python-mpd2
          pkgs.python3Packages.openrgb-python
        ];
        makeWrapperArgs = [ "--prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.playerctl ]}" ];
        nativeCheckInputs = [ pkgs.python3Packages.pytestCheckHook ];
        pythonImportsCheck = [ "ppiss.protocol" "ppiss.sender" ];
      };
    in {
      packages = forAllSystems (system:
        let package = packageFor nixpkgs.legacyPackages.${system};
        in { default = package; ppiss = package; });
      apps = forAllSystems (system: {
        default = { type = "app"; program = "${self.packages.${system}.default}/bin/ppiss-send"; };
      });
      homeManagerModules.default = import ./nix/home-manager-module.nix self;
      homeManagerModules.ppiss = self.homeManagerModules.default;
      devShells = forAllSystems (system: {
        default = let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3.withPackages (ps: [
            ps.psutil ps.pygame ps.pytest ps.python-mpd2 ps.openrgb-python
          ]);
        in pkgs.mkShell {
          packages = [ python pkgs.openrgb pkgs.playerctl pkgs.ruff ];
          shellHook = ''
            export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
          '';
        };
      });
    };
}
