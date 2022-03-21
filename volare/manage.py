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
import click
from click_default_group import DefaultGroup

from .git_multi_clone import mkdirp
from .common import opt_pdk_root, check_version


def get_installed_list(pdk_root):
    version_dir = os.path.join(pdk_root, "volare", "versions")
    mkdirp(version_dir)
    return os.listdir(version_dir)


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
        if file_content == "":
            console.log("No PDK is currently enabled.")
            console.print(f"Installed PDKs: {get_installed_list(pdk_root)}")
            exit(1)
        else:
            console.log(f"Version {file_content} is currently enabled.")
    else:
        if file_content == "":
            exit(1)
        else:
            print(f"{file_content}", end="")


manage.add_command(output)


@click.command("list")
@opt_pdk_root
def list_cmd(pdk_root):
    """Lists installed PDK versions."""
    console = rich.console.Console()
    if sys.stdout.isatty():
        console.print(f"Current installed versions: {get_installed_list(pdk_root)}")
    else:
        print(json.dumps(get_installed_list(pdk_root)))


manage.add_command(list_cmd)


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

    version_dir = os.path.join(pdk_root, "volare", "versions", version)

    variants = ["sky130A", "sky130B"]
    version_paths = [os.path.join(version_dir, variant) for variant in variants]
    final_paths = [os.path.join(pdk_root, variant) for variant in variants]

    if not os.path.exists(version_dir):
        # TODO: Enable a pre-built version to be downloaded from the internet, if applicable
        console.log(f"Version {version} is not downloaded, and thus cannot be enabled.")
        exit(1)

    with console.status(f"Enabling version {version}..."):
        for path in final_paths:
            if os.path.exists(path):
                if os.path.islink(path):
                    os.unlink(path)
                else:
                    console.log(
                        f"Error: {path} exists, and not as a symlink. Please manually remove it before continuing."
                    )
                    exit(1)

        for vpath, fpath in zip(version_paths, final_paths):
            src = os.path.relpath(vpath, pdk_root)
            os.symlink(src=src, dst=fpath)

        with open(current_file, "w") as f:
            f.write(version)

    console.log(f"PDK version {version} enabled.")


manage.add_command(enable)
