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
import tarfile
import pathlib
import requests
import tempfile

import rich
import rich.tree
import click
import rich.progress

from .build.git_multi_clone import mkdirp
from .common import (
    get_link_of,
    get_variants,
    opt,
    opt_build,
    opt_push,
    opt_pdk_root,
    check_version,
    get_versions_dir,
    get_version_dir,
    get_volare_dir,
    get_version_list,
)
from .build import build, push


def get_installed_list(pdk_root, pdk):
    versions_dir = get_versions_dir(pdk_root, pdk)
    mkdirp(versions_dir)
    return os.listdir(versions_dir)


def print_installed_list(pdk_root, pdk, console):
    installed_list = get_installed_list(pdk_root, pdk)
    versions_dir = get_versions_dir(pdk_root, pdk)
    if len(installed_list) == 0:
        console.print("[red]No PDKs installed.")
        return

    version = get_current_version(pdk_root, pdk)

    tree = rich.tree.Tree(f"{versions_dir}")
    for installed in installed_list:
        if installed == version:
            tree.add(f"[green][bold]{installed} (enabled)")
        else:
            tree.add(installed)
    console.print(tree)


def print_remote_list(pdk_root, pdk, console, pdk_list):
    installed_list = get_installed_list(pdk_root, pdk)

    version = get_current_version(pdk_root, pdk)

    tree = rich.tree.Tree(f"Pre-built {pdk} PDK versions")
    for pdk in pdk_list:
        if pdk == version:
            tree.add(f"[green][bold]{pdk} (enabled)")
        elif pdk in installed_list:
            tree.add(f"[green]{pdk} (installed)")
        else:
            tree.add(pdk)
    console.print(tree)


def get_current_version(pdk_root, pdk):
    current_file = os.path.join(get_volare_dir(pdk_root, pdk), "current")
    current_file_dir = os.path.dirname(current_file)
    mkdirp(current_file_dir)
    pathlib.Path(current_file).touch(exist_ok=True)

    return open(current_file).read().strip()


@click.command("output")
@opt_pdk_root
def output_cmd(pdk_root, pdk):
    """(Default) Outputs the currently installed PDK version."""

    if sys.stdout.isatty():
        console = rich.console.Console()
        print_installed_list(pdk_root, pdk, console)
    else:
        version = get_current_version(pdk)
        if version == "":
            exit(1)
        else:
            print(version, end="")


@click.command("list", hidden=True)
@opt_pdk_root
def list_cmd(pdk_root, pdk):
    """Lists PDK versions that are remotely available. JSON if not outputting to a tty."""

    pdk_versions = get_version_list(pdk)

    if sys.stdout.isatty():
        console = rich.console.Console()
        print_remote_list(pdk_root, pdk, console, pdk_versions)
    else:
        print(json.dumps(pdk_versions))


@click.command("path")
@opt_pdk_root
@click.argument("version", required=False)
def path_cmd(pdk_root, pdk, version):
    """Prints the path of a specific pdk version installation."""
    path_to_print = pdk_root
    if version is not None:
        path_to_print = os.path.join(get_versions_dir(pdk_root, pdk), version)
    print(path_to_print, end="")


def enable(
    pdk_root: str,
    pdk: str,
    version: str,
    build_if_not_found=False,
    also_push=False,
    build_kwargs: dict = {},
    push_kwargs: dict = {},
):
    console = rich.console.Console()

    current_file = os.path.join(get_volare_dir(pdk_root, pdk), "current")
    current_file_dir = os.path.dirname(current_file)
    mkdirp(current_file_dir)

    version_directory = get_version_dir(pdk_root, pdk, version)

    variants = get_variants(pdk)

    version_paths = [os.path.join(version_directory, variant) for variant in variants]
    final_paths = [os.path.join(pdk_root, variant) for variant in variants]

    if not os.path.exists(version_directory):
        link = get_link_of(version, pdk)
        status = requests.head(link).status_code
        if status == 404:
            console.print(f"Version {version} not found either locally or remotely.")
            if build_if_not_found:
                console.print("Attempting to build...")
                build(pdk_root=pdk_root, pdk=pdk, version=version, **build_kwargs)
                if also_push:
                    push(pdk_root, version, **push_kwargs)
            else:
                console.print(
                    f"[red]Version {version} not found either locally or remotely.\nTry volare build {version}."
                )
                exit(1)
        else:
            with tempfile.TemporaryDirectory(suffix=".volare") as tarball_directory:
                tarball_path = os.path.join(tarball_directory, f"{version}.tar.xz")
                with requests.get(link, stream=True) as r:
                    with rich.progress.Progress() as p:
                        task = p.add_task(
                            f"Downloading pre-built tarball for {version}…",
                            total=int(r.headers["Content-length"]),
                        )
                        r.raise_for_status()
                        with open(tarball_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                p.advance(task, advance=len(chunk))
                                f.write(chunk)

                        task = p.add_task("Unpacking…")
                        with tarfile.open(tarball_path, mode="r:*") as tf:
                            p.update(task, total=len(tf.getmembers()))
                            for i, file in enumerate(tf.getmembers()):
                                p.update(task, completed=i + 1)
                                final_path = os.path.join(version_directory, file.name)
                                final_dir = os.path.dirname(final_path)
                                mkdirp(final_dir)
                                with tf.extractfile(file) as io:
                                    with open(final_path, "wb") as f:
                                        f.write(io.read())

                        for variant in variants:
                            variant_install_path = os.path.join(
                                version_directory, variant
                            )
                            variant_sources_file = os.path.join(
                                variant_install_path, "SOURCES"
                            )
                            if not os.path.isfile(variant_sources_file):
                                with open(variant_sources_file, "w") as f:
                                    print(f"open_pdks {version}", file=f)

                        os.unlink(tarball_path)

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


@click.command("enable")
@opt_pdk_root
@click.option(
    "-f",
    "--metadata-file",
    "tool_metadata_file_path",
    default=None,
    help="Explicitly define a tool metadata file instead of searching for a metadata file",
)
@click.argument("version", required=False)
def enable_cmd(pdk_root, pdk, tool_metadata_file_path, version):
    """
    Activates a given PDK version.

    Parameters: <version> (Optional)

    If a version is not given, and you run this in the top level directory of
    tools with a tool_metadata.yml file, for example OpenLane or DFFRAM,
    the appropriate version will be enabled automatically.
    """
    console = rich.console.Console()
    version = check_version(version, tool_metadata_file_path, console)
    enable(pdk_root=pdk_root, pdk=pdk, version=version)


@click.command("enable_or_build", hidden=True)
@opt_pdk_root
@opt_push
@opt_build
@opt("--also-push/--dont-push", default=False, help="Also push.")
@click.option(
    "-f",
    "--metadata-file",
    "tool_metadata_file_path",
    default=None,
    help="Explicitly define a tool metadata file instead of searching for a metadata file",
)
@click.argument("version")
def enable_or_build_cmd(
    include_libraries,
    jobs,
    sram,
    pdk_root,
    pdk,
    owner,
    repository,
    token,
    clear_build_artifacts,
    tool_metadata_file_path,
    also_push,
    version,
):
    """
    Attempts to activate a given PDK version. If the version is not found locally or remotely,
    it will instead attempt to build said version.

    Parameters: <version>
    """
    console = rich.console.Console()
    version = check_version(version, tool_metadata_file_path, console)
    enable(
        pdk_root=pdk_root,
        pdk=pdk,
        version=version,
        build_if_not_found=True,
        also_push=also_push,
        build_kwargs={
            "include_libraries": include_libraries,
            "jobs": jobs,
            "sram": sram,
            "clear_build_artifacts": clear_build_artifacts,
        },
        push_kwargs={"owner": owner, "repository": repository, "token": token},
    )
