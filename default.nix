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
  lib,
  buildPythonPackage,
  click,
  pyyaml,
  rich,
  httpx,
  pcpp,
  zstandard,
  truststore,
  nix-gitignore,
}:

buildPythonPackage rec {
  name = "volare";

  version_file = builtins.readFile ./volare/__version__.py;
  version_list = builtins.match ''.+''\n__version__ = "([^"]+)"''\n.+''$'' version_file;
  version = builtins.head version_list;

  src = nix-gitignore.gitignoreSourcePure ./.gitignore ./.;

  doCheck = false;

  propagatedBuildInputs = [
    click
    pyyaml
    rich
    httpx
    pcpp
    zstandard
    truststore
  ] ++ httpx.optional-dependencies.socks;
  
  meta = with lib; {
    mainProgram = "volare";
    description = "Version manager and builder for open-source PDKs";
    homepage = "https://github.com/efabless/volare";
    license = licenses.asl20;
    platforms = platforms.darwin ++ platforms.linux;
  };
}
