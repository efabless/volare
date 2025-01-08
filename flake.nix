# Copyright 2024 Efabless Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
{
  inputs = {
    nix-eda.url = github:efabless/nix-eda;
  };

  outputs = {
    self,
    nix-eda,
    ...
  }: let
    nixpkgs = nix-eda.inputs.nixpkgs;
    lib = nixpkgs.lib;
  in {
    overlays = {
      default = nix-eda.composePythonOverlay (pkgs': pkgs: pypkgs': pypkgs: let
        callPythonPackage = lib.callPackageWith (pkgs' // pkgs'.python3.pkgs);
      in {
        volare = callPythonPackage ./default.nix {};
      });
    };

    legacyPackages = nix-eda.forAllSystems (
      system:
        import nixpkgs {
          inherit system;
          overlays = [
            nix-eda.overlays.default
            self.overlays.default
          ];
        }
    );

    # Outputs
    packages = nix-eda.forAllSystems (
      system: let
        pkgs = self.legacyPackages."${system}";
      in {
        inherit (pkgs.python3.pkgs) volare;
        default = self.packages."${system}".volare;
      }
    );
  };
}
