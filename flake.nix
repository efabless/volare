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
    nixpkgs.url = github:nixos/nixpkgs/nixos-23.11;
  };

  outputs = {
    self,
    nixpkgs,
    ...
  }: {
    # Helper functions
    forAllSystems = function:
      nixpkgs.lib.genAttrs [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ] (
        system:
          function (import nixpkgs {
            inherit system;
          })
      );

    # Outputs
    packages = self.forAllSystems (pkgs: let
      callPackage = pkgs.lib.callPackageWith (pkgs // self.packages.${pkgs.system});
      callPythonPackage = pkgs.lib.callPackageWith (pkgs // pkgs.python3.pkgs // self.packages.${pkgs.system});
    in
      rec {
        volare = callPythonPackage ./default.nix {};
        default = volare;
      }
    );
  };
}
