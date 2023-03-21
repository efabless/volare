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
from typing import Callable

import click

from .common import VOLARE_RESOLVED_HOME, VOLARE_REPO_OWNER, VOLARE_REPO_NAME

opt = partial(click.option, show_default=True)


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
        default=VOLARE_RESOLVED_HOME,
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
    function = opt(
        "-r",
        "--use-repo-at",
        default=None,
        multiple=True,
        hidden=True,
        type=str,
        help="Use this repository instead of cloning and checking out, in the format repo_name=/path/to/repo. You can pass it multiple times to replace multiple repos. This feature is intended for volare and PDK developers.",
    )(function)
    function = opt(
        "--build-magic/--use-system-magic",
        default=False,
        help="Whether to attempt to build Magic from source or use Magic from PATH for PDKs that may need Magic.",
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
    function = opt(
        "--pre/--prod", default=False, help="Push as pre-release or production"
    )(function)
    return function
