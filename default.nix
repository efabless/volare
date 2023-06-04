{
  pkgs? import <nixpkgs> {},
  gitignore-src ? import ./nix/gitignore.nix { inherit pkgs; },
}:

with pkgs; with python3.pkgs; buildPythonPackage rec {
  name = "volare";

  version_file = builtins.readFile ./volare/__version__.py;
  version_list = builtins.match ''.+''\n__version__ = "([^"]+)"''\n.+''$'' version_file;
  version = builtins.head version_list;

  src = gitignore-src.gitignoreSource ./.;

  doCheck = false;
  PIP_DISABLE_PIP_VERSION_CHECK = "1";

  propagatedBuildInputs = [
    click
    pyyaml
    rich
    requests
    pcpp
    zstandard
  ];
}