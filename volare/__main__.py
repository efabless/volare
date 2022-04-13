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
import click
from click_default_group import DefaultGroup

from . import __version__
from .build import build_cmd, push_cmd
from .manage import output_cmd, path_cmd, list_cmd, enable_cmd, enable_or_build_cmd


@click.group(
    cls=DefaultGroup,
    default="output",
    default_if_no_args=True,
)
@click.version_option(__version__)
def cli():
    pass


cli.add_command(output_cmd)
cli.add_command(build_cmd)
cli.add_command(push_cmd)
cli.add_command(path_cmd)
cli.add_command(list_cmd)
cli.add_command(enable_cmd)
cli.add_command(enable_or_build_cmd)


if __name__ == "__main__":
    cli()
