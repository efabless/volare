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
  poetry-core,
}:
buildPythonPackage {
  pname = "volare";
  version = (builtins.fromTOML (builtins.readFile ./pyproject.toml)).tool.poetry.version;
  format = "pyproject";

  src = ./.;
  doCheck = false;

  nativeBuildInputs = [
    poetry-core
  ];


  dependencies =
    [
      click
      pyyaml
      rich
      httpx
      pcpp
      zstandard
      truststore
    ]
    ++ httpx.optional-dependencies.socks;

  meta = {
    mainProgram = "volare";
    description = "Version manager and builder for open-source PDKs";
    homepage = "https://github.com/efabless/volare";
    license = lib.licenses.asl20;
    platforms = lib.platforms.darwin ++ lib.platforms.linux;
  };
}
