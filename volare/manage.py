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
import sys
import json
import shutil
import tarfile
import requests
import tempfile
from typing import Any, List, Optional

import rich
import click
import rich.tree
import rich.progress
import zstandard as zstd
from rich.console import Console

from .build.git_multi_clone import mkdirp
from .common import (
    Version,
    check_version,
    get_release_links,
    get_versions_dir,
    get_volare_dir,
    get_installed_list,
)
from .click_common import (
    opt,
    opt_build,
    opt_push,
    opt_pdk_root,
)
from .build import build, push
from .families import Family


def print_installed_list(
    pdk_root: str, pdk: str, console: Console, installed_list: List[Version]
):
    if len(installed_list) == 0:
        console.print("[red]No PDKs installed.")
        return

    versions = installed_list

    try:
        all_remote_versions = Version._from_github()
        remote_versions = all_remote_versions.get(pdk) or []
        remote_version_dict = {rv.name: rv for rv in remote_versions}
        for installed in installed_list:
            remote_version = remote_version_dict.get(installed.name)
            if remote_version is not None:
                installed.commit_date = remote_version.commit_date
                installed.upload_date = remote_version.upload_date
        versions.sort(reverse=True)
    except requests.exceptions.ConnectionError:
        console.print(
            "[red]You don't appear to be connected to the Internet. Date information may be unavailable."
        )

    versions_dir = get_versions_dir(pdk_root, pdk)
    tree = rich.tree.Tree(f"{versions_dir}")
    for installed in versions:
        day: Optional[str] = None
        if installed.commit_date is not None:
            day = installed.commit_date.strftime("%Y.%m.%d")
        desc = f"{installed.name}"
        if day is not None:
            desc += f" ({day})"
        if installed.is_current(pdk_root):
            tree.add(f"[green][bold]{desc} (enabled)")
        else:
            tree.add(desc)
    console.print(tree)


def print_remote_list(
    pdk_root: str, pdk: str, console: Console, pdk_list: List[Version]
):
    installed_list = get_installed_list(pdk_root, pdk)

    tree = rich.tree.Tree(f"Pre-built {pdk} PDK versions")
    for remote_version in pdk_list:
        name = remote_version.name
        assert (
            remote_version.commit_date is not None
        ), f"Remote version {name} has no commit date"
        day = remote_version.commit_date.strftime("%Y.%m.%d")
        desc = f"[green]{name} ({day})"
        if remote_version.prerelease:
            desc = f"[red]PRE-RELEASE {desc}"
        if remote_version.is_current(pdk_root):
            tree.add(f"[bold]{desc} (enabled)")
        elif name in installed_list:
            tree.add(f"{desc} (installed)")
        else:
            tree.add(desc)
    console.print(tree)


# -- CLI
@click.command("output")
@opt_pdk_root
def output_cmd(pdk_root, pdk):
    """Outputs the currently enabled PDK version.

    If not outputting to a tty, the output is either the version string
    unembellished, or, if no current version is enabled, an empty output with an
    exit code of 1.
    """

    version = Version.get_current(pdk_root, pdk)
    if sys.stdout.isatty():
        if version is None:
            print(f"No version of the PDK {pdk} is currently enabled at {pdk_root}.")
            print(
                "Invoke volare --help for assistance installing and enabling versions."
            )
            exit(1)
        else:
            print(f"Installed: {pdk} v{version.name}")
            print(
                "Invoke volare --help for assistance installing and enabling versions."
            )
    else:
        if version is None:
            exit(1)
        else:
            print(version.name, end="")


@click.command("prune")
@opt_pdk_root
@click.option(
    "--yes",
    is_flag=True,
    callback=lambda c, _, v: not v and c.abort(),
    expose_value=False,
    prompt="Are you sure? This will delete all non-enabled versions of the PDK from your computer.",
)
def prune_cmd(pdk_root, pdk):
    """Removes all PDKs other than, if it exists, the one currently in use."""
    pdk_versions = get_installed_list(pdk_root, pdk)
    for version in pdk_versions:
        if version.is_current(pdk_root):
            continue
        try:
            version.uninstall()
            print(f"Deleted {version}.")
        except Exception as e:
            print(f"Failed to delete {version}: {e}", file=sys.stderr)


@click.command("rm")
@opt_pdk_root
@click.option(
    "--yes",
    is_flag=True,
    callback=lambda c, _, v: not v and c.abort(),
    expose_value=False,
    prompt="Are you sure? This will delete this version of the PDK from your computer.",
)
@click.argument("version", required=False)
def rm_cmd(pdk_root, pdk, version):
    """Removes the PDK version specified."""
    version_object = Version(version, pdk)
    try:
        version_object.uninstall(pdk_root)
        print(f"Deleted {version}.")
    except Exception as e:
        print(f"Failed to delete: {e}", file=sys.stderr)
        exit(1)


@click.command("ls")
@opt_pdk_root
def list_cmd(pdk_root, pdk):
    """Lists PDK versions that are locally installed. JSON if not outputting to a tty."""

    pdk_versions = get_installed_list(pdk_root, pdk)

    if sys.stdout.isatty():
        console = Console()
        print_installed_list(pdk_root, pdk, console, pdk_versions)
    else:
        print(json.dumps([version.name for version in pdk_versions]), end="")


@click.command("ls-remote")
@opt_pdk_root
def list_remote_cmd(pdk_root, pdk):
    """Lists PDK versions that are remotely available. JSON if not outputting to a tty."""

    try:
        all_versions = Version._from_github()
        pdk_versions = all_versions.get(pdk) or []

        if sys.stdout.isatty():
            console = Console()
            print_remote_list(pdk_root, pdk, console, pdk_versions)
        else:
            print(json.dumps([version.name for version in pdk_versions]), end="")
    except requests.exceptions.ConnectionError:
        if sys.stdout.isatty():
            console = Console()
            console.print(
                "[red]You don't appear to be connected to the Internet. ls-remote cannot be used."
            )
        else:
            print("Failed to connect to remote server", file=sys.stderr)
        sys.exit(-1)


@click.command("path")
@opt_pdk_root
@click.argument("version", required=False)
def path_cmd(pdk_root, pdk, version):
    """Prints the path of a specific pdk version installation."""
    version = Version(version, pdk)
    print(version.get_dir(pdk_root), end="")


def enable(
    pdk_root: str,
    pdk: str,
    version: str,
    build_if_not_found=False,
    also_push=False,
    build_kwargs: dict = {},
    push_kwargs: dict = {},
    include_libraries: Optional[List[str]] = None,
):
    console = Console()

    current_file = os.path.join(get_volare_dir(pdk_root, pdk), "current")
    current_file_dir = os.path.dirname(current_file)
    mkdirp(current_file_dir)

    version_object = Version(version, pdk)

    version_directory = version_object.get_dir(pdk_root)

    pdk_family = Family.by_name.get(pdk)
    if pdk_family is None:
        print(f"Unsupported PDK family '{pdk}'.", file=sys.stderr)
        exit(os.EX_USAGE)

    variants = pdk_family.variants

    version_paths = [os.path.join(version_directory, variant) for variant in variants]
    final_paths = [os.path.join(pdk_root, variant) for variant in variants]

    if not os.path.exists(version_directory):
        release_link_list = get_release_links(version, pdk, include_libraries)

        if release_link_list is None:
            if build_if_not_found:
                console.print(f"Version {version} not found, attempting to build…")
                build(pdk_root=pdk_root, pdk=pdk, version=version, **build_kwargs)
                if also_push:
                    push(pdk_root=pdk_root, pdk=pdk, version=version, **push_kwargs)
            else:
                console.print(
                    f"[red]Version {version} not found either locally or remotely.\nTry volare build {version}."
                )
                exit(1)
        else:
            try:
                tarball_directory = tempfile.TemporaryDirectory(suffix=".volare")
                for name, link in release_link_list:
                    tarball_path = os.path.join(tarball_directory.name, name)
                    r = requests.get(link, stream=True)
                    with rich.progress.Progress(console=console) as p:
                        task = p.add_task(
                            f"Downloading {name}…",
                            total=int(r.headers["Content-length"]),
                        )
                        r.raise_for_status()
                        with open(tarball_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                p.advance(task, advance=len(chunk))
                                f.write(chunk)

                    with console.status(f"Unpacking {name}…"):
                        stream: Any = None
                        if name.endswith(".tar.zst"):
                            stream = zstd.open(tarball_path, mode="rb")
                        else:
                            try:
                                import lzma

                                stream = lzma.open(tarball_path, mode="rb")
                            except ImportError:
                                raise OSError(
                                    "Your Python installation does not support xz compression. Either reinstall Python or try a newer PDK version."
                                )
                        with tarfile.TarFile(fileobj=stream, mode="r") as tf:
                            for file in tf:
                                if file.isdir():
                                    continue
                                final_path = os.path.join(version_directory, file.name)
                                final_dir = os.path.dirname(final_path)
                                mkdirp(final_dir)
                                io = tf.extractfile(file)
                                if io is None:
                                    raise ValueError(
                                        f"Failed to unpack tarball for {name}."
                                    )
                                with open(final_path, "wb") as f:
                                    f.write(io.read())
            except Exception as e:
                shutil.rmtree(version_directory, ignore_errors=True)
                console.print(f"[red]Error: {e}")
                exit(-1)
            except KeyboardInterrupt:
                console.print("Interrupted.")
                shutil.rmtree(version_directory, ignore_errors=True)
                exit(-1)

            for variant in variants:
                variant_install_path = os.path.join(version_directory, variant)
                variant_sources_file = os.path.join(variant_install_path, "SOURCES")
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

    console.print(f"Version {version} enabled for the {pdk} PDK.")


@click.command("enable")
@opt_pdk_root
@click.option(
    "-f",
    "--metadata-file",
    "tool_metadata_file_path",
    default=None,
    help="Explicitly define a tool metadata file instead of searching for a metadata file",
)
@click.option(
    "-l",
    "--include-libraries",
    multiple=True,
    default=None,
    help="Libraries to include. You can use -l multiple times to include multiple libraries. Pass 'all' to include all of them. A default of 'None' uses a default set for the particular PDK.",
)
@click.argument("version", required=False)
def enable_cmd(pdk_root, pdk, tool_metadata_file_path, version, include_libraries):
    """
    Activates a given installed PDK version.

    Parameters: <version> (Optional)

    If a version is not given, and you run this in the top level directory of
    tools with a tool_metadata.yml file, for example OpenLane or DFFRAM,
    the appropriate version will be enabled automatically.
    """
    if include_libraries == ():
        include_libraries = None

    console = Console()
    version = check_version(version, tool_metadata_file_path, console)
    enable(
        pdk_root=pdk_root,
        pdk=pdk,
        version=version,
        include_libraries=include_libraries,
    )


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
    pdk_root,
    pdk,
    owner,
    repository,
    token,
    pre,
    clear_build_artifacts,
    tool_metadata_file_path,
    also_push,
    version,
    use_repo_at,
    build_magic,
):
    """
    Attempts to activate a given PDK version. If the version is not found locally or remotely,
    it will instead attempt to build said version.

    Parameters: <version>
    """
    if include_libraries == ():
        include_libraries = None

    console = Console()
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
            "clear_build_artifacts": clear_build_artifacts,
            "use_repo_at": use_repo_at,
            "build_magic": build_magic,
        },
        push_kwargs={
            "owner": owner,
            "repository": repository,
            "token": token,
            "pre": pre,
        },
        include_libraries=include_libraries,
    )
