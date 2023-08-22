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
import io
import os
import shutil
import tarfile
import tempfile
from typing import Any, List, Optional, Union

import rich
import requests
import rich.tree
import rich.progress
import zstandard as zstd
from rich.console import Console

from .build.git_multi_clone import mkdirp
from .common import (
    Version,
    get_versions_dir,
    get_volare_dir,
)
from .build import build, push
from .families import Family


class VersionNotFound(Exception):
    pass


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
    tree = rich.tree.Tree(f"In {versions_dir}:")
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
    installed_list = Version.get_all_installed(pdk_root, pdk)

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


def get(
    pdk_root: str,
    pdk: str,
    version: str,
    build_if_not_found=False,
    also_push=False,
    build_kwargs: dict = {},
    push_kwargs: dict = {},
    include_libraries: Optional[List[str]] = None,
    output: Union[Console, io.TextIOWrapper] = Console(),
):
    console = output
    if not isinstance(console, Console):
        console = Console(file=console)

    version_object = Version(version, pdk)

    version_directory = version_object.get_dir(pdk_root)

    pdk_family = Family.by_name.get(pdk)
    if pdk_family is None:
        raise ValueError(f"Unsupported PDK family '{pdk}'.")

    variants = pdk_family.variants

    if not os.path.exists(version_directory):
        console.print(f"Version {version} not found locally, attempting to download…")
        tarball_paths = []
        try:
            release_link_list = version_object.get_release_links(include_libraries)
            tarball_directory = tempfile.TemporaryDirectory(suffix=".volare")
            for name, link in release_link_list:
                tarball_path = os.path.join(tarball_directory.name, name)
                tarball_paths.append(tarball_path)
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
                                raise IOError(
                                    f"Failed to unpack file in {name}'s tarball: {file.name}."
                                )
                            with open(final_path, "wb") as f:
                                f.write(io.read())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                if build_if_not_found:
                    console.print(
                        f"Version {version} not found remotely, attempting to build…"
                    )
                    build(pdk_root=pdk_root, pdk=pdk, version=version, **build_kwargs)
                    if also_push:
                        if push_kwargs["push_libraries"] is None:
                            push_kwargs["push_libraries"] = Family.by_name[
                                pdk
                            ].default_includes.copy()
                        push(pdk_root=pdk_root, pdk=pdk, version=version, **push_kwargs)
                else:
                    raise RuntimeError(f"Version {version} not found remotely.")
            else:
                raise RuntimeError(
                    f"Failed to obtain {version} remotely: {e.response}."
                )
        except KeyboardInterrupt as e:
            console.print("Interrupted.")
            shutil.rmtree(version_directory, ignore_errors=True)
            raise e from None
        except Exception as e:
            shutil.rmtree(version_directory, ignore_errors=True)
            raise e from None
        finally:
            for path in tarball_paths:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass

        for variant in variants:
            variant_install_path = os.path.join(version_directory, variant)
            variant_sources_file = os.path.join(variant_install_path, "SOURCES")
            if not os.path.isfile(variant_sources_file):
                with open(variant_sources_file, "w") as f:
                    print(f"open_pdks {version}", file=f)


def enable(
    pdk_root: str,
    pdk: str,
    version: str,
    build_if_not_found=False,
    also_push=False,
    build_kwargs: dict = {},
    push_kwargs: dict = {},
    include_libraries: Optional[List[str]] = None,
    output: Union[Console, io.TextIOWrapper] = Console(),
):
    console = output
    if not isinstance(console, Console):
        console = Console(file=console)

    version_object = Version(version, pdk)
    version_directory = version_object.get_dir(pdk_root)

    pdk_family = Family.by_name.get(pdk)
    if pdk_family is None:
        raise ValueError(f"Unsupported PDK family '{pdk}'.")

    variants = pdk_family.variants
    version_paths = [os.path.join(version_directory, variant) for variant in variants]
    final_paths = [os.path.join(pdk_root, variant) for variant in variants]

    get(
        pdk_root,
        pdk,
        version,
        build_if_not_found,
        also_push,
        build_kwargs,
        push_kwargs,
        include_libraries,
        output=output,
    )

    current_file = os.path.join(get_volare_dir(pdk_root, pdk), "current")
    current_file_dir = os.path.dirname(current_file)
    mkdirp(current_file_dir)

    with console.status(f"Enabling version {version}…"):
        for path in final_paths:
            if os.path.exists(path):
                if os.path.islink(path):
                    os.unlink(path)
                else:
                    raise FileExistsError(
                        f"{path} exists, and not as a symlink. Remove it then try re-enabling."
                    )

        for vpath, fpath in zip(version_paths, final_paths):
            src = os.path.relpath(vpath, pdk_root)
            os.symlink(src=src, dst=fpath)

        with open(current_file, "w") as f:
            f.write(version)

    console.print(f"Version {version} enabled for the {pdk} PDK.")


def root_for(
    pdk_root: str,
    pdk: str,
    version: str,
) -> str:
    """
    Deprecated: use ``Version().get_dir()``
    """
    return Version(version, pdk).get_dir(pdk_root)
