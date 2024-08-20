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
import io
import json
import shlex
import shutil
import subprocess
from datetime import datetime
from typing import Optional, List, Tuple, Dict
from concurrent.futures import ThreadPoolExecutor

import pcpp
from rich.console import Console
from rich.progress import Progress

from .git_multi_clone import GitMultiClone
from .common import patch_open_pdks
from ..families import Family
from ..github import opdks_repo
from ..common import (
    Version,
    get_volare_dir,
    mkdirp,
)

MAGIC_DEFAULT_TAG = "085131b090cb511d785baf52a10cf6df8a657d44"


def get_open_pdks(
    version, build_directory, jobs=1, repo_path=None
) -> Tuple[str, Optional[str], Optional[str]]:
    try:
        console = Console()

        open_pdks_repo = None
        if repo_path is None:
            with Progress() as progress:
                with ThreadPoolExecutor(max_workers=jobs) as executor:
                    gmc = GitMultiClone(build_directory, progress)
                    open_pdks_future = executor.submit(
                        GitMultiClone.clone,
                        gmc,
                        opdks_repo.link,
                        version,
                        default_branch="master",
                    )
                    open_pdks_repo = open_pdks_future.result()
                    repo_path = open_pdks_repo.path

            console.log(f"Done fetching {open_pdks_repo.name}.")
        else:
            console.log(f"Using open_pdks at {repo_path} unaltered.")

        patch_open_pdks(repo_path)

        try:
            json_raw = open(f"{repo_path}/gf180mcu/gf180mcu.json").read()
            cpp = pcpp.Preprocessor()
            cpp.line_directive = None
            cpp.parse(json_raw)
            json_str = None
            with io.StringIO() as sio:
                cpp.write(sio)
                json_str = sio.getvalue()
            manifest = json.loads(json_str)
            reference_commits = manifest["reference"]
            print(f"Reference commits: {reference_commits}")
        except FileNotFoundError:
            console.log("Warning: Couldn't find open_pdks/sky130 JSON manifest.")
        except json.JSONDecodeError:
            console.log("Warning: Failed to parse open_pdks/sky130 JSON manifest..")
        except KeyError:
            console.log(
                "Warning: Failed to extract reference commits from open_pdks/sky130 JSON manifest."
            )

        return repo_path

    except subprocess.CalledProcessError as e:
        print(e)
        print(e.stderr)
        exit(-1)


LIB_FLAG_MAP = {
    "gf180mcu_fd_pr": "--enable-primitive-gf180mcu",
    "gf180mcu_fd_sc_mcu7t5v0": "--enable-sc-7t5v0-gf180mcu",
    "gf180mcu_fd_sc_mcu9t5v0": "--enable-sc-9t5v0-gf180mcu",
    "gf180mcu_fd_io": "--enable-io-gf180mcu",
    "gf180mcu_fd_ip_sram": "--enable-sram-gf180mcu",
    "gf180mcu_osu_sc_gp12t3v3": "--enable-osu-sc-gf180mcu",
    "gf180mcu_osu_sc_gp9t3v3": "--enable-osu-sc-gf180mcu",
}


def build_variants(
    magic_bin, include_libraries, build_directory, open_pdks_path, log_dir, jobs=1
):
    try:
        pdk_root_abs = os.path.abspath(build_directory)
        console = Console()

        def run_sh(script, log_to):
            output_file = open(log_to, "w")
            try:
                subprocess.check_call(
                    ["sh", "-c", script],
                    cwd=open_pdks_path,
                    stdout=output_file,
                    stderr=output_file,
                    stdin=open(os.devnull),
                )
            except subprocess.CalledProcessError as e:
                console.log(
                    f"An error occurred while building the PDK. Check {log_to} for more information."
                )
                raise e

        library_flags = set([LIB_FLAG_MAP[library] for library in include_libraries])
        library_flags_disable = set(
            [
                LIB_FLAG_MAP[library].replace("enable", "disable")
                for library in LIB_FLAG_MAP
                if library not in include_libraries
            ]
        )
        magic_dirname = os.path.dirname(magic_bin)

        configuration_flags = ["--enable-gf180mcu-pdk", "--with-reference"] + list(
            library_flags.union(library_flags_disable)
        )
        console.log(f"Configuring with flags {shlex.join(configuration_flags)}")

        with console.status("Configuring open_pdks…"):
            run_sh(
                f"""
                    set -e
                    export PATH="{magic_dirname}:$PATH"
                    ./configure {shlex.join(configuration_flags)}
                """,
                log_to=os.path.join(log_dir, "config.log"),
            )
        console.log("Configured open_pdks.")

        with console.status("Building variants using open_pdks…"):
            run_sh(
                f"""
                    set -e
                    export LC_ALL=en_US.UTF-8
                    export PATH="{magic_dirname}:$PATH"
                    make -j{jobs}
                    make 'SHARED_PDKS_PATH={pdk_root_abs}' install
                """,
                log_to=os.path.join(log_dir, "install.log"),
            )
        console.log("Built PDK variants.")
        with console.status("Cleaning build artifacts…"):
            run_sh(
                """
                set -e
                rm -rf sources
                """,
                log_to=os.path.join(log_dir, "clean.log"),
            )
        console.log("Cleaned build artifacts.")

        console.log("Done.")

    except subprocess.CalledProcessError as e:
        print(e)
        print(e.stderr)
        exit(-1)


def install_gf180mcu(build_directory, pdk_root, version):
    console = Console()
    with console.status("Adding build to list of installed versions…"):
        version_directory = Version(version, "gf180mcu").get_dir(pdk_root)
        if (
            os.path.exists(version_directory)
            and len(os.listdir(version_directory)) != 0
        ):
            backup_path = version_directory
            it = 0
            while os.path.exists(backup_path) and len(os.listdir(backup_path)) != 0:
                it += 1
                backup_path = Version(f"{version}.bk{it}", "gf180mcu").get_dir(pdk_root)
            console.log(
                f"Build already found at {version_directory}, moving to {backup_path}…"
            )
            shutil.move(version_directory, backup_path)

        console.log("Copying…")
        mkdirp(version_directory)

        gf180mcu_family = Family.by_name["gf180mcu"]

        for variant in gf180mcu_family.variants:
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
    family = Family.by_name["gf180mcu"]
    library_set = family.resolve_libraries(include_libraries)

    if using_repos is None:
        using_repos = {}

    timestamp = datetime.now().strftime("build_gf180mcu-%Y-%m-%d-%H-%M-%S")
    build_directory = os.path.join(
        get_volare_dir(pdk_root, "gf180mcu"), "build", version
    )
    log_dir = os.path.join(build_directory, "logs", timestamp)
    mkdirp(log_dir)

    console = Console()
    console.log(f"Logging to '{log_dir}'…")

    open_pdks_path = get_open_pdks(
        version, build_directory, jobs, using_repos.get("open_pdks")
    )

    magic_bin = shutil.which("magic")
    if magic_bin is None:
        print("Magic is either not installed or not in PATH.")
        exit(-1)

    build_variants(
        magic_bin,
        library_set,
        build_directory,
        open_pdks_path,
        log_dir,
        jobs,
    )
    install_gf180mcu(build_directory, pdk_root, version)

    if clear_build_artifacts:
        shutil.rmtree(build_directory)
