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
import uuid
import pathlib
import tarfile
import tempfile
import importlib
import subprocess
from typing import Optional, List, Dict

import click
import zstandard as zstd
from rich.console import Console
from rich.progress import Progress

from ..github import (
    GitHubSession,
    get_open_pdks_commit_date,
    volare_repo,
)
from ..common import (
    Version,
    mkdirp,
    resolve_version,
    date_to_iso8601,
)
from ..click_common import (
    opt_push,
    opt_build,
    opt_pdk_root,
    opt_token,
)
from ..families import Family


def build(
    pdk_root: str,
    pdk: str,
    version: str,
    jobs: int = 1,
    sram: bool = True,  # Deprecated
    clear_build_artifacts: bool = True,
    include_libraries: Optional[List[str]] = None,
    use_repo_at: Optional[List[str]] = None,
):
    use_repos = {}
    if use_repo_at is not None:
        for repo in use_repo_at:
            name, path = repo.split("=")
            use_repos[name] = os.path.abspath(path)

    if pdk not in Family.by_name:
        raise Exception(f"Unsupported PDK family '{pdk}'.")

    kwargs = {
        "pdk_root": pdk_root,
        "version": version,
        "jobs": jobs,
        "clear_build_artifacts": clear_build_artifacts,
        "include_libraries": include_libraries,
        "using_repos": use_repos,
    }

    build_module = importlib.import_module(f".{pdk}", package=__name__)
    build_function = build_module.build
    build_function(**kwargs)


@click.command("build")
@opt_token
@opt_pdk_root
@opt_build
@click.option(
    "-f",
    "--metadata-file",
    "tool_metadata_file_path",
    default=None,
    help="Explicitly define a tool metadata file instead of searching for a metadata file",
)
@click.argument("version", required=False)
def build_cmd(
    include_libraries,
    jobs,
    pdk_root,
    pdk,
    clear_build_artifacts,
    tool_metadata_file_path,
    version,
    use_repo_at,
):
    """
    Builds the requested PDK.

    Parameters: <version> (Optional)

    If a version is not given, and you run this in the top level directory of
    tools with a tool_metadata.yml file, for example OpenLane or DFFRAM,
    the appropriate version will be enabled automatically.
    """
    if include_libraries == ():
        include_libraries = None

    console = Console()
    try:
        version = resolve_version(version, tool_metadata_file_path)
    except Exception as e:
        console.print(f"Could not determine open_pdks version: {e}")
        exit(-1)

    build(
        pdk_root=pdk_root,
        pdk=pdk,
        version=version,
        jobs=jobs,
        clear_build_artifacts=clear_build_artifacts,
        include_libraries=include_libraries,
        use_repo_at=use_repo_at,
    )


def push(
    pdk_root,
    pdk,
    version,
    *,
    owner=volare_repo.owner,
    repository=volare_repo.name,
    pre=False,
    push_libraries=None,
    session: Optional[GitHubSession] = None,
):
    if session is None:
        session = GitHubSession()
    if session.github_token is None:
        raise TypeError("No GitHub token was provided.")

    console = Console()

    if push_libraries is None or len(push_libraries) == 0:
        push_libraries = Family.by_name[pdk].all_libraries
    library_list = set(push_libraries)

    version_object = Version(version, pdk)
    version_directory = version_object.get_dir(pdk_root)
    if not os.path.isdir(version_directory):
        raise FileNotFoundError(f"Version {version} not found.")

    tempdir = tempfile.gettempdir()
    tarball_directory = os.path.join(tempdir, "volare", f"{uuid.uuid4()}", version)
    mkdirp(tarball_directory)

    final_tarballs = []

    with Progress() as progress:
        collections: Dict[str, List[str]] = {"common": []}
        path_it = pathlib.Path(version_directory).glob("**/*")
        for path in path_it:
            if not path.is_file():
                continue
            relative = os.path.relpath(path, version_directory)
            path_components = relative.split(os.sep)
            if path_components[1] == "libs.ref":
                lib = path_components[2]
                if lib not in library_list:
                    continue
                collections[lib] = collections.get(lib) or []
                collections[lib].append(str(path))
            else:
                collections["common"].append(str(path))

        for name, files in collections.items():
            tarball_path = os.path.join(tarball_directory, f"{name}.tar.zst")
            task = progress.add_task(f"Compressing {name}…", total=len(files))
            with zstd.open(tarball_path, mode="wb") as stream:
                with tarfile.TarFile(fileobj=stream, mode="w") as tf:
                    for i, file in enumerate(files):
                        progress.update(task, completed=i + 1)
                        path_in_tarball = os.path.relpath(file, version_directory)
                        tf.add(file, arcname=path_in_tarball)
            console.log(f"\nCompressed to {tarball_path}.")
            progress.remove_task(task)
            final_tarballs.append(tarball_path)

    tag = f"{pdk}-{version}"

    # If someone wants to rewrite this to not use ghr, please, by all means.
    console.log("Starting upload…")

    body = f"{pdk} variants built using volare"
    date = get_open_pdks_commit_date(version, session)
    if date is not None:
        body = f"{pdk} variants built using open_pdks {version} (released on {date_to_iso8601(date)})"

    for tarball_path in final_tarballs:
        subprocess.check_call(
            [
                "ghr",
                "-owner",
                owner,
                "-repository",
                repository,
                "-token",
                session.github_token,
                "-body",
                body,
                "-commitish",
                "releases",
                "-replace",
            ]
            + (["-prerelease"] if pre else [])
            + [
                tag,
                tarball_path,
            ]
        )
    console.log("Done.")


@click.command("push", hidden=True)
@opt_token
@opt_pdk_root
@opt_push
@click.argument("version")
def push_cmd(
    owner,
    repository,
    pre,
    pdk_root,
    pdk,
    version,
    push_libraries,
):
    """
    For maintainers: Package and release a build to the public.

    Requires ghr: github.com/tcnksm/ghr

    Parameters: <version> (required)
    """
    console = Console()
    try:
        push(
            pdk_root,
            pdk,
            version,
            owner=owner,
            repository=repository,
            pre=pre,
            push_libraries=push_libraries,
        )
    except Exception as e:
        console.print(f"[red]Failed to push version: {e}")
        exit(-1)
