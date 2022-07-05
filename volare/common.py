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
import json
import pathlib
import requests
from functools import partial
from typing import Optional, Callable, List

import rich
import click


class RepoMetadata(object):
    def __init__(self, repo, default_commit, default_branch="main"):
        self.repo = repo
        self.default_commit = default_commit
        self.default_branch = default_branch


VOLARE_REPO_OWNER = os.getenv("VOLARE_REPO_OWNER") or "efabless"
VOLARE_REPO_NAME = os.getenv("VOLARE_REPO_NAME") or "volare"
VOLARE_REPO_ID = f"{VOLARE_REPO_OWNER}/{VOLARE_REPO_NAME}"
VOLARE_REPO_HTTPS = f"https://github.com/{VOLARE_REPO_ID}"
VOLARE_REPO_API = f"https://api.github.com/repos/{VOLARE_REPO_ID}"
VOLARE_DEFAULT_HOME = os.path.join(os.path.expanduser("~"), ".volare")

opt = partial(click.option, show_default=True)


def mkdirp(path):
    return pathlib.Path(path).mkdir(parents=True, exist_ok=True)


def opt_pdk_root(function: Callable):
    function = click.option(
        "--pdk",
        required=False,
        default=os.getenv("PDK_FAMILY") or "sky130",
        help="The PDK family to install",
        show_default=True,
    )(function)
    function = click.option(
        "--pdk-root",
        required=False,
        default=os.getenv("PDK_ROOT") or VOLARE_DEFAULT_HOME,
        help="Path to the PDK root",
        show_default=True,
    )(function)
    return function


def opt_build(function: Callable):
    function = opt(
        "-l",
        "--include-libraries",
        multiple=True,
        default=None,
        help="Libraries to include in the build. You can use -l multiple times to include multiple libraries. Pass 'all' to include all of them. A default of 'None' uses a default set for the particular PDK.",
    )(function)
    function = opt(
        "-j",
        "--jobs",
        default=1,
        help="Specifies the number of commands to run simultaneously.",
    )(function)
    function = opt("--sram/--no-sram", default=True, help="Enable or disable sram")(
        function
    )
    function = opt(
        "--clear-build-artifacts/--keep-build-artifacts",
        default=False,
        help="Whether or not to remove the build artifacts. Keeping the build artifacts is useful when testing.",
    )(function)
    return function


def opt_push(function: Callable):
    function = opt("-o", "--owner", default=VOLARE_REPO_OWNER, help="Repository Owner")(
        function
    )
    function = opt("-r", "--repository", default=VOLARE_REPO_NAME, help="Repository")(
        function
    )
    function = opt(
        "-t",
        "--token",
        default=os.getenv("GITHUB_TOKEN"),
        help="Github Token",
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


def get_variants(pdk: str) -> List[str]:
    if pdk == "sky130":
        return ["sky130A", "sky130B"]
    if pdk == "asap7":
        return ["asap7"]
    return []


def get_volare_dir(pdk_root: str, pdk: str) -> str:
    return os.path.join(pdk_root, "volare", pdk)


def get_versions_dir(pdk_root: str, pdk: str) -> str:
    return os.path.join(get_volare_dir(pdk_root, pdk), "versions")


def get_version_dir(pdk_root: str, pdk: str, version: str) -> str:
    return os.path.join(get_versions_dir(pdk_root, pdk), version)


def get_link_of(version: str, pdk: str) -> str:
    return f"{VOLARE_REPO_HTTPS}/releases/download/{pdk}-{version}/default.tar.xz"


def get_version_list(pdk: str) -> List[str]:
    response_str = requests.get(f"{VOLARE_REPO_API}/releases").content.decode("utf8")
    releases = json.loads(response_str)
    pdk_versions = [release["tag_name"] for release in releases]
    pdk_versions_by_pdk = {}
    for version in pdk_versions:
        family, hash = version.split("-")
        if pdk_versions_by_pdk.get(family) is None:
            pdk_versions_by_pdk[family] = pdk_versions_by_pdk.get(family) or []
        pdk_versions_by_pdk[family].append(hash)
    return pdk_versions_by_pdk.get(pdk) or []


def get_logs_dir() -> str:
    logs_dir = os.getenv("VOLARE_LOGS") or os.path.join(VOLARE_DEFAULT_HOME, "logs")
    return logs_dir
