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
import warnings
from typing import Iterable, List, Optional, Union

import rich
import httpx
import rich.tree
import rich.progress
import zstandard as zstd
from rich.console import Console

from .build.git_multi_clone import mkdirp
from .github import GitHubSession
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
    pdk_root: str,
    pdk: str,
    *,
    console: Console,
    installed_list: List[Version],
    session: Optional[GitHubSession] = None,
):
    if len(installed_list) == 0:
        console.print("[red]No PDKs installed.")
        return

    versions = installed_list

    try:
        all_remote_versions = Version._from_github(session)
        remote_versions = all_remote_versions.get(pdk) or []
        remote_version_dict = {rv.name: rv for rv in remote_versions}
        for installed in installed_list:
            remote_version = remote_version_dict.get(installed.name)
            if remote_version is not None:
                installed.commit_date = remote_version.commit_date
                installed.upload_date = remote_version.upload_date
        versions.sort(reverse=True)
    except httpx.HTTPError:
        console.print(
            "[red]Failed to connect to GitHub. Date information may be unavailable."
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
    pdk_root: str,
    pdk: str,
    console: Console,
    pdk_list: List[Version],
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


def fetch(
    pdk_root: str,
    pdk: str,
    version: str,
    *,
    build_if_not_found=False,
    also_push=False,
    build_kwargs: dict = {},
    push_kwargs: dict = {},
    include_libraries: Optional[Iterable[str]] = None,
    output: Union[Console, io.TextIOWrapper] = Console(),
    session: Optional[GitHubSession] = None,
) -> Version:
    if session is None:
        session = GitHubSession()

    console = output
    if not isinstance(console, Console):
        console = Console(file=console)

    version_object = Version(version, pdk)

    version_directory = version_object.get_dir(pdk_root)

    pdk_family = Family.by_name.get(pdk)
    if pdk_family is None:
        raise ValueError(f"Unsupported PDK family '{pdk}'.")

    library_set = pdk_family.resolve_libraries(include_libraries)

    variants = pdk_family.variants

    common_missing = False
    missing_libraries = set()
    libs_tech = os.path.join(version_directory, variants[0], "libs.tech")
    if not os.path.isdir(libs_tech):
        common_missing = True

    for library in library_set:
        if library not in pdk_family.all_libraries:
            raise RuntimeError(f"Unknown library {library}.")
        found = False
        for variant in variants:
            lib_path = os.path.join(version_directory, variant, "libs.ref", library)
            if os.path.isdir(lib_path):
                found = True
        if not found:
            missing_libraries.add(library)

    affected_paths = []
    if len(missing_libraries) != 0 or common_missing:
        if common_missing:
            console.print(
                f"Version {version} not found locally, attempting to download…"
            )
            affected_paths.append(version_directory)
        else:
            console.print(f"Libraries {missing_libraries} not found, downloading them…")
            for variant in variants:
                affected_paths.append(
                    os.path.join(version_directory, variant, "libs.ref", library)
                )

        tarball_paths = []
        try:
            release_link_list = version_object.get_release_links(
                missing_libraries,
                include_common=common_missing,
                session=session,
            )
            tarball_directory = tempfile.TemporaryDirectory(suffix=".volare")
            for name, link in release_link_list:
                tarball_path = os.path.join(tarball_directory.name, name)
                tarball_paths.append(tarball_path)
                with session.stream("get", link) as r, rich.progress.Progress(
                    console=console
                ) as p:
                    total_str: Optional[str] = r.headers.get("Content-length", None)
                    total_int: Optional[int] = None
                    if total_str is not None:
                        total_int = int(total_str)
                    task = p.add_task(
                        f"Downloading {name}…",
                        total=total_int,
                    )
                    r.raise_for_status()
                    with open(tarball_path, "wb") as f:
                        for chunk in r.iter_bytes(chunk_size=8192):
                            p.advance(task, advance=len(chunk))
                            f.write(chunk)

                with console.status(f"Unpacking {name}…"):
                    stream = zstd.open(tarball_path, mode="rb")
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
        except httpx.HTTPStatusError as e:
            if e.response is not None and e.response.status_code == 404:
                if not build_if_not_found:
                    raise RuntimeError(f"Version {version} not found remotely.")
                console.print(
                    f"Version {version} not found remotely, attempting to build…"
                )
                build(
                    pdk_root=pdk_root,
                    pdk=pdk,
                    version=version,
                    **build_kwargs,
                )
                if also_push:
                    if push_kwargs["push_libraries"] is None:
                        push_kwargs["push_libraries"] = Family.by_name[
                            pdk
                        ].default_includes.copy()
                    push(
                        pdk_root=pdk_root,
                        pdk=pdk,
                        version=version,
                        session=session,
                        **push_kwargs,
                    )
            else:
                if e.response is not None:
                    raise RuntimeError(
                        f"Failed to obtain {version} remotely: {e.response}."
                    )
                else:
                    raise RuntimeError(f"Failed to request {version} from server: {e}.")
        except KeyboardInterrupt as e:
            console.print("Interrupted.")
            for path in affected_paths:
                shutil.rmtree(path, ignore_errors=True)
            raise e from None
        except Exception as e:
            for path in affected_paths:
                shutil.rmtree(path, ignore_errors=True)
            raise e from None
        finally:
            for path in tarball_paths:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass

        for variant in variants:
            variant_install_path = os.path.join(version_directory, variant)
            if not os.path.isdir(variant_install_path):
                continue
            variant_sources_file = os.path.join(variant_install_path, "SOURCES")
            if not os.path.isfile(variant_sources_file):
                with open(variant_sources_file, "w") as f:
                    print(f"open_pdks {version}", file=f)

    return Version(version, pdk)


def enable(
    pdk_root: str,
    pdk: str,
    version: str,
    *,
    build_if_not_found: bool = False,
    also_push: bool = False,
    build_kwargs: dict = {},
    push_kwargs: dict = {},
    include_libraries: Optional[List[str]] = None,
    output: Union[Console, io.TextIOWrapper] = Console(),
    session: Optional[GitHubSession] = None,
) -> Version:
    if session is None:
        session = GitHubSession()

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

    fetch(
        pdk_root,
        pdk,
        version,
        build_if_not_found=build_if_not_found,
        also_push=also_push,
        build_kwargs=build_kwargs,
        push_kwargs=push_kwargs,
        include_libraries=include_libraries,
        output=output,
        session=session,
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
            if os.path.isdir(vpath):
                os.symlink(src=src, dst=fpath)

        with open(current_file, "w") as f:
            f.write(version)

    console.print(f"Version {version} enabled for the {pdk} PDK.")
    return version_object


def get(*args, **kwargs):
    warnings.warn("get() has been deprecated: use fetch()")
    return fetch(*args, **kwargs)
