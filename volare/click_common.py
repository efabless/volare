# Copyright 2022-2023 Efabless Corporation
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
from typing import Callable, Optional

import click

from .common import VOLARE_RESOLVED_HOME
from .github import volare_repo, GitHubSession

opt = partial(click.option, show_default=True)


def opt_pdk_root(function: Callable):
    function = opt(
        "--pdk",
        required=False,
        default=os.getenv("PDK_FAMILY") or "sky130",
        help="The PDK family to install",
    )(function)
    function = opt(
        "--pdk-root",
        required=False,
        default=VOLARE_RESOLVED_HOME,
        help="Path to the PDK root",
    )(function)
    return function


def opt_build(function: Callable):
    function = opt(
        "-l",
        "--include-libraries",
        multiple=True,
        default=None,
        help="Libraries to include. You can use -l multiple times to include multiple libraries. Pass 'all' to include all of them. A default of 'None' uses a default set for the particular PDK.",
    )(function)
    function = opt(
        "-j",
        "--jobs",
        default=1,
        help="Specifies the number of commands to run simultaneously.",
    )(function)
    function = opt(
        "--sram/--no-sram",
        default=True,
        hidden=True,
        expose_value=False,
    )(function)
    function = opt(
        "--clear-build-artifacts/--keep-build-artifacts",
        default=False,
        help="Whether or not to remove the build artifacts. Keeping the build artifacts is useful when testing.",
    )(function)
    function = opt(
        "-r",
        "--use-repo-at",
        default=None,
        multiple=True,
        hidden=True,
        type=str,
        help="Use this repository instead of cloning and checking out, in the format repo_name=/path/to/repo. You can pass it multiple times to replace multiple repos. This feature is intended for volare and PDK developers.",
    )(function)
    return function


def opt_push(function: Callable):
    function = opt("-o", "--owner", default=volare_repo.owner, help="Repository Owner")(
        function
    )
    function = opt("-r", "--repository", default=volare_repo.name, help="Repository")(
        function
    )
    function = opt(
        "--pre/--prod", default=False, help="Push as pre-release or production"
    )(function)
    function = opt(
        "-L",
        "--push-library",
        "push_libraries",
        multiple=True,
        default=None,
        help="Push only libraries in this list. You can use -L multiple times to include multiple libraries. Pass 'None' to push all libraries built.",
    )(function)
    return function


def set_token_cb(
    ctx: click.Context,
    param: click.Parameter,
    value: Optional[str],
):
    GitHubSession.Token.override = value


def opt_token(function: Callable) -> Callable:
    function = opt(
        "-t",
        "--token",
        "session",
        default=None,
        required=False,
        expose_value=False,
        help="Replace the GitHub token used for GitHub requests, which is by default the value of the environment variable GITHUB_TOKEN or None.",
        callback=set_token_cb,
    )(function)
    return function
