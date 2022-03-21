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

import rich
import click

opt = partial(click.option, show_default=True)


def opt_pdk_root(function):
    function = click.option(
        "--pdk-root",
        required=(os.getenv("PDK_ROOT") is None),
        default=os.getenv("PDK_ROOT"),
        help="Path to the PDK root [required if environment variable PDK_ROOT is not set]",
    )(function)
    return function


def check_version(
    version: Optional[str],
    tool_metadata_file_path: Optional[str],
    console: Optional[rich.console.Console] = None
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
