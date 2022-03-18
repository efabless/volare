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
