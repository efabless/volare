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
import shutil
import subprocess
from datetime import datetime
from typing import Optional, List, Tuple, Dict
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console
from rich.progress import Progress

from .git_multi_clone import GitMultiClone
from ..families import Family
from ..github import ihp_repo
from ..common import (
    Version,
    get_volare_dir,
    mkdirp,
)


def get_ihp(
    version, build_directory, jobs=1, repo_path=None
) -> Tuple[str, Optional[str], Optional[str]]:
    try:
        console = Console()

        if repo_path is None:
            with Progress() as progress:
                with ThreadPoolExecutor(max_workers=jobs) as executor:
                    gmc = GitMultiClone(build_directory, progress)
                    ihp_future = executor.submit(
                        GitMultiClone.clone,
                        gmc,
                        ihp_repo.link,
                        version,
                    )
                    repo_path = ihp_future.result().path

            console.log(f"Done fetching {ihp_repo.name}.")
        else:
            console.log(f"Using IHP-Open-PDK at {repo_path} unaltered.")

        return repo_path

    except subprocess.CalledProcessError as e:
        print(e)
        print(e.stderr)
        exit(-1)


def build_ihp(build_directory, ihp_path):
    # """Build"""
    try:
        shutil.rmtree(os.path.join(build_directory, "ihp-sg13g2"))
    except FileNotFoundError:
        pass
    shutil.copytree(
        os.path.join(ihp_path, "ihp-sg13g2"),
        os.path.join(build_directory, "ihp-sg13g2"),
    )


def install_ihp(build_directory, pdk_root, version):
    console = Console()
    with console.status("Adding build to list of installed versions…"):
        ihp_sg13g2_family = Family.by_name["ihp-sg13g2"]

        version_directory = Version(version, "ihp-sg13g2").get_dir(pdk_root)
        if (
            os.path.exists(version_directory)
            and len(os.listdir(version_directory)) != 0
        ):
            backup_path = version_directory
            it = 0
            while os.path.exists(backup_path) and len(os.listdir(backup_path)) != 0:
                it += 1
                backup_path = Version(f"{version}.bk{it}", "ihp-sg13g2").get_dir(
                    pdk_root
                )
            console.log(
                f"Build already found at {version_directory}, moving to {backup_path}…"
            )
            shutil.move(version_directory, backup_path)

        console.log("Copying…")
        mkdirp(version_directory)

        for variant in ihp_sg13g2_family.variants:
            variant_build_path = os.path.join(build_directory, variant)
            variant_install_path = os.path.join(version_directory, variant)
            if os.path.isdir(variant_build_path):
                shutil.copytree(variant_build_path, variant_install_path)

    console.log("Done.")


def build(
    pdk_root: str,
    version: str,
    jobs: int = 1,
    clear_build_artifacts: bool = True,
    include_libraries: Optional[List[str]] = None,
    using_repos: Optional[Dict[str, str]] = None,
):
    console = Console()
    if include_libraries is not None:
        console.log(
            "Note: all libraries will be acquired as part of the trivial PDK build."
        )

    if using_repos is None:
        using_repos = {}

    build_directory = os.path.join(
        get_volare_dir(pdk_root, "ihp-sg13g2"), "build", version
    )
    timestamp = datetime.now().strftime("build_ihp-sg13g2-%Y-%m-%d-%H-%M-%S")
    log_dir = os.path.join(build_directory, "logs", timestamp)
    mkdirp(log_dir)

    console.log(f"Logging to '{log_dir}'…")

    ihp_path = get_ihp(version, build_directory, jobs, using_repos.get("ihp"))
    build_ihp(build_directory, ihp_path)
    install_ihp(build_directory, pdk_root, version)

    if clear_build_artifacts:
        shutil.rmtree(build_directory)
