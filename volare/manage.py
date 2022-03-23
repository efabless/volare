#!/usr/bin/env python3
# Copyright 2022 Efabless Corporation
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
import os
import sys
import json
import pathlib

import rich
import rich.tree
import click
from click_default_group import DefaultGroup

from .git_multi_clone import mkdirp
from .common import opt_pdk_root, check_version, get_versions_dir, get_version_dir


def get_installed_list(pdk_root):
    versions_dir = get_versions_dir(pdk_root)
    mkdirp(versions_dir)
    return os.listdir(versions_dir)


def print_installed_list(pdk_root, version, console):
    installed_list = get_installed_list(pdk_root)
    versions_dir = get_versions_dir(pdk_root)
    if len(installed_list) == 0:
        console.print("[red]No PDKs installed.")
        return

    tree = rich.tree.Tree(f"{versions_dir}")
    for installed in installed_list:
        if installed == version:
            tree.add(f"[green][bold]{installed} (enabled)")
        else:
            tree.add(installed)
    console.print(tree)


@click.group(cls=DefaultGroup, default="output", default_if_no_args=True)
def manage():
    """Allows you to list and enable installed PDKs. (default)"""
    pass


@click.command()
@opt_pdk_root
def output(pdk_root):
    """Outputs the currently installed PDK version."""
    current_file = os.path.join(pdk_root, "volare", "current")
    current_file_dir = os.path.dirname(current_file)
    mkdirp(current_file_dir)
    pathlib.Path(current_file).touch(exist_ok=True)

    file_content = open(current_file).read().strip()

    if sys.stdout.isatty():
        console = rich.console.Console()
        print_installed_list(pdk_root, file_content, console)
    else:
        if file_content == "":
            exit(1)
        else:
            print(f"{file_content}", end="")


manage.add_command(output)


@click.command("list")
@opt_pdk_root
def list_cmd(pdk_root):
    """Lists installed PDK versions in a parsable format."""
    print(json.dumps(get_installed_list(pdk_root)))


manage.add_command(list_cmd)


@click.command("path")
@opt_pdk_root
@click.argument("version")
def path_cmd(pdk_root, version):
    """Prints the path of a specific pdk version installation."""
    path_of_version = os.path.join(get_versions_dir(pdk_root), version)
    if sys.stdout.isatty():
        print(path_of_version)
    else:
        print(path_of_version, end="")


manage.add_command(path_cmd)


@click.command()
@opt_pdk_root
@click.option(
    "-f",
    "--metadata-file",
    "tool_metadata_file_path",
    default=None,
    help="Explicitly define a tool metadata file instead of searching for a metadata file",
)
@click.argument("version", required=False)
def enable(pdk_root, tool_metadata_file_path, version):
    """
    Activates a given PDK version.

    Parameters: <version> (Optional)

    If a version is not given, and you run this in the top level directory of
    tools with a tool_metadata.yml file, for example OpenLane or DFFRAM,
    the appropriate version will be enabled automatically.
    """
    console = rich.console.Console()

    version = check_version(version, tool_metadata_file_path, console)

    current_file = os.path.join(pdk_root, "volare", "current")
    current_file_dir = os.path.dirname(current_file)
    mkdirp(current_file_dir)

    version_dir = get_version_dir(pdk_root, version)

    variants = ["sky130A", "sky130B"]
    version_paths = [os.path.join(version_dir, variant) for variant in variants]
    final_paths = [os.path.join(pdk_root, variant) for variant in variants]

    if not os.path.exists(version_dir):
        # TODO: Enable a pre-built version to be downloaded from the internet, if applicable
        console.print(
            f"[red]Version {version} is not downloaded, and thus cannot be enabled."
        )
        exit(1)

    with console.status(f"Enabling version {version}…"):
        for path in final_paths:
            if os.path.exists(path):
                if os.path.islink(path):
                    os.unlink(path)
                else:
                    console.print(
                        f"[red]Error: {path} exists, and not as a symlink. Please manually remove it before continuing."
                    )
                    exit(1)

        for vpath, fpath in zip(version_paths, final_paths):
            src = os.path.relpath(vpath, pdk_root)
            os.symlink(src=src, dst=fpath)

        with open(current_file, "w") as f:
            f.write(version)

    console.print(f"PDK version {version} enabled.")


manage.add_command(enable)
