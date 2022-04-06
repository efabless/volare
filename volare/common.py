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
from functools import partial
from typing import Optional
from typing import Callable

import rich
import click

opt = partial(click.option, show_default=True)


def opt_pdk_root(function: Callable):
    function = click.option(
        "--pdk-root",
        required=False,
        default=os.getenv("PDK_ROOT") or os.path.expanduser("~/.volare"),
        help="Path to the PDK root",
        show_default=True,
    )(function)
    return function


def check_version(
    version: Optional[str],
    tool_metadata_file_path: Optional[str],
    console: Optional[rich.console.Console] = None,
) -> str:
    """
    Takes an optional version and tool_metadata_file_path.

    If version is set, it is returned.

    If not, tool_metadata_file_path is checked if it exists.

    If not specified, ./tool_metadata.yml and ./dependencies/tool_metadata.yml
    are both checked if they exist.

    If none are specified, execution is halted.

    Otherwise, the resulting metadata file is parsed for an open_pdks version,
    which is then returned.
    """
    if version is not None:
        return version

    def pr(*args):
        if console is not None:
            console.log(*args)
        else:
            print(*args)

    import yaml

    if tool_metadata_file_path is None:
        tool_metadata_file_path = os.path.join(".", "tool_metadata.yml")
        if not os.path.isfile(tool_metadata_file_path):
            tool_metadata_file_path = os.path.join(
                ".", "dependencies", "tool_metadata.yml"
            )
            if not os.path.isfile(tool_metadata_file_path):
                pr(
                    "Any of ./tool_metadata.yml or ./dependencies/tool_metadata.yml not found. You'll need to specify the file path or the commits explicitly."
                )
                exit(os.EX_USAGE)

    tool_metadata = yaml.safe_load(open(tool_metadata_file_path).read())

    open_pdks_list = [tool for tool in tool_metadata if tool["name"] == "open_pdks"]

    if len(open_pdks_list) < 1:
        pr("No entry for open_pdks found in tool_metadata.yml")
        exit(os.EX_USAGE)

    version = open_pdks_list[0]["commit"]

    pr(f"Found version {version} in {tool_metadata_file_path}.")

    return version


def get_volare_dir(pdk_root: str) -> str:
    return os.path.join(pdk_root, "volare", "sky130")


def get_versions_dir(pdk_root: str) -> str:
    return os.path.join(get_volare_dir(pdk_root), "versions")


def get_version_dir(pdk_root: str, version: str) -> str:
    return os.path.join(get_versions_dir(pdk_root), version)


def get_link_of(version: str) -> str:
    repo = os.getenv("VOLARE_REPOSITORY") or "https://github.com/efabless/volare"
    return f"{repo}/releases/download/sky130-{version}/default.tar.xz"


SKY130_VARIANTS = ["sky130A", "sky130B"]
