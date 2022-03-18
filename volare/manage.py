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
import pathlib

import rich
import click
from click_default_group import DefaultGroup

from .git_multi_clone import mkdirp
from .click_option import opt_pdk_root


@click.group(cls=DefaultGroup, default="output", default_if_no_args=True)
def manage():
    pass


@click.command()
@opt_pdk_root
def output(pdk_root):
    current_file = os.path.join(pdk_root, "volare", "current")
    current_file_dir = os.path.dirname(current_file)
    mkdirp(current_file_dir)
    pathlib.Path(current_file).touch(exist_ok=True)

    file_content = open(current_file).read().strip()

    if sys.stdout.isatty():
        console = rich.console.Console()
        if file_content == "":
            console.log("No PDK is currently enabled.")
            exit(1)
        else:
            console.log(f"Version {file_content} is currently enabled.")
    else:
        if file_content == "":
            exit(1)
        else:
            print(f"{file_content}", end="")


manage.add_command(output)


@click.command()
@opt_pdk_root
@click.argument("version")
def enable(pdk_root, version):
    current_file = os.path.join(pdk_root, "volare", "current")
    current_file_dir = os.path.dirname(current_file)
    mkdirp(current_file_dir)

    version_dir = os.path.join(pdk_root, "volare", "versions", version)

    console = rich.console.Console()

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


manage.add_command(enable)
