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
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console
from rich.progress import Progress

from .common import RepoMetadata
from .git_multi_clone import GitMultiClone
from ..common import (
    get_version_dir,
    get_volare_dir,
    mkdirp,
)
from ..families import Family

repo_metadata = {
    "orfs": RepoMetadata(
        "https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts",
        "b541139f4da34687340bf2e55528707e76fce233",
        "master",
    )
}


def get_orfs(version, build_directory, jobs=1):
    try:
        console = Console()

        orfs_repo = None

        with Progress() as progress:
            with ThreadPoolExecutor(max_workers=jobs) as executor:
                gmc = GitMultiClone(build_directory, progress)
                orfs = repo_metadata["orfs"]
                orfs_future = executor.submit(
                    GitMultiClone.clone,
                    gmc,
                    orfs.repo,
                    version,
                    orfs.default_branch,
                )
                orfs_repo = orfs_future.result()

        console.log(f"Done fetching {orfs_repo.name}.")

    except subprocess.CalledProcessError as e:
        print(e)
        print(e.stderr)
        exit(-1)


def build_variants(build_directory, jobs):
    PDK_LINKER_SCRIPT = "https://raw.githubusercontent.com/The-OpenROAD-Project/OpenLane/01e951092150ee8619286b0807ee263198b5ea6d/scripts/pdk-linker.py"

    subprocess.check_call(
        [
            "sed",
            "-i",
            "s/grid_strategy-M2-M5-M7.cfg/grid_strategy-M2-M5-M7.tcl/",
            "./OpenROAD-flow-scripts/flow/platforms/asap7/openlane/mapping.json",
        ],
        cwd=build_directory,
    )
    subprocess.check_call(
        [
            "sed",
            "-i",
            "s/grid_strategy-M2-M5-M7.cfg/grid_strategy-M2-M5-M7.tcl/",
            "./OpenROAD-flow-scripts/flow/platforms/asap7/openlane/asap7sc7p5t/config.tcl",
        ],
        cwd=build_directory,
    )

    subprocess.check_call(["curl", "-LO", PDK_LINKER_SCRIPT], cwd=build_directory)

    subprocess.check_call(
        [
            "python3",
            "./pdk-linker.py",
            "-s",
            "OpenROAD-flow-scripts",
            "-d",
            "asap7",
            "-m",
            "./OpenROAD-flow-scripts/flow/platforms/asap7/openlane/mapping.json",
        ],
        cwd=build_directory,
    )


def install_asap7(build_directory, pdk_root, version):
    console = Console()
    with console.status("Adding build to list of installed versions…"):
        version_directory = get_version_dir(pdk_root, "asap7", version)
        print(version_directory)
        if (
            os.path.exists(version_directory)
            and len(os.listdir(version_directory)) != 0
        ):
            backup_path = version_directory
            it = 0
            while os.path.exists(backup_path) and len(os.listdir(backup_path)) != 0:
                it += 1
                backup_path = get_version_dir(pdk_root, "asap7", f"{version}.bk{it}")
            console.log(
                f"Build already found at {version_directory}, moving to {backup_path}…"
            )
            shutil.move(version_directory, backup_path)

        console.log("Copying…")
        mkdirp(version_directory)

        asap7_family = Family.by_name["asap7"]

        for variant in asap7_family.variants:
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
    build_magic: bool = False,
):
    if using_repos is None:
        using_repos = {}

    # TODO: Support using_repos
    build_directory = os.path.join(get_volare_dir(pdk_root, "asap7"), "build", version)

    get_orfs(version, build_directory, jobs)
    build_variants(build_directory, jobs)
    install_asap7(build_directory, pdk_root, version)
