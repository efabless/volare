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
import shutil
import subprocess
from datetime import datetime
from typing import Optional, List, Tuple, Dict
from concurrent.futures import ThreadPoolExecutor

import pcpp
from rich.console import Console
from rich.progress import Progress

from .magic import with_magic
from .git_multi_clone import GitMultiClone
from ..common import (
    get_logs_dir,
    get_version_dir,
    get_volare_dir,
    mkdirp,
    RepoMetadata,
    OPDKS_REPO_HTTPS,
)
from ..families import Family

repo_metadata = {
    "open_pdks": RepoMetadata(
        OPDKS_REPO_HTTPS,
        "cc0029b45c68137aa21323912f50d2fc17eeea13",
        "master",
    ),
    "gf180mcu": RepoMetadata(
        "https://github.com/google/gf180mcu-pdk",
        "08c628b77c4683cad8441d7d0c2df1c8ab58cbc2",
        "main",
    ),
}

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
                    open_pdks = repo_metadata["open_pdks"]
                    open_pdks_future = executor.submit(
                        GitMultiClone.clone,
                        gmc,
                        open_pdks.repo,
                        version,
                        open_pdks.default_branch,
                    )
                    open_pdks_repo = open_pdks_future.result()
                    repo_path = open_pdks_repo.path

            console.log(f"Done fetching {open_pdks_repo.name}.")
        else:
            console.log(f"Using open_pdks at {repo_path} unaltered.")

        gf180mcu_tag = None
        magic_tag = None

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
            magic_tag = reference_commits["magic"]
            gf180mcu_tag = reference_commits["gf180mcu_pdk"]
        except FileNotFoundError:
            console.log(
                "Cannot find open_pdks/gf180mcu JSON manifest. Default versions for gf180mcu/magic will be used."
            )
        except json.JSONDecodeError:
            print(json_str)
            console.log(
                "Failed to parse open_pdks/gf180mcu JSON manifest. Default versions for gf180mcu/magic will be used."
            )
        except KeyError:
            console.log(
                "Failed to extract reference commits from open_pdks/gf180mcu JSON manifest. Default versions for gf180mcu/magic will be used."
            )

        return (repo_path, gf180mcu_tag, magic_tag)

    except subprocess.CalledProcessError as e:
        print(e)
        print(e.stderr)
        exit(os.EX_DATAERR)


LIB_FLAG_MAP = {
    "gf180mcu_fd_pr": "--enable-primitive-gf180mcu",
    "gf180mcu_fd_sc_mcu7t5v0": "--enable-sc-7t5v0-gf180mcu",
    "gf180mcu_fd_sc_mcu9t5v0": "--enable-sc-9t5v0-gf180mcu",
    "gf180mcu_fd_io": "--enable-io-gf180mcu",
    "gf180mcu_fd_bd_sram": "--enable-sram-gf180mcu",
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

        library_flags = [LIB_FLAG_MAP[library] for library in include_libraries]
        magic_dirname = os.path.dirname(magic_bin)

        with console.status("Configuring open_pdks…"):
            run_sh(
                f"""
                    set -e
                    export PATH="{magic_dirname}:$PATH"
                    ./configure --enable-gf180mcu-pdk {' '.join(library_flags)} --with-reference
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

        with console.status("Fixing file ownership…"):
            run_sh(
                f"""
                set -e
                OWNERSHIP="$(stat -c "%u:%g" "{pdk_root_abs}")"
                chown -R $OWNERSHIP "{pdk_root_abs}"
                """,
                log_to=os.path.join(log_dir, "ownership.log"),
            )
        console.log("Fixed file ownership.")

        console.log("Done.")

    except subprocess.CalledProcessError as e:
        print(e)
        print(e.stderr)
        exit(os.EX_DATAERR)


def install_gf180mcu(build_directory, pdk_root, version):
    console = Console()
    with console.status("Adding build to list of installed versions…"):
        version_directory = get_version_dir(pdk_root, "gf180mcu", version)
        if (
            os.path.exists(version_directory)
            and len(os.listdir(version_directory)) != 0
        ):
            backup_path = version_directory
            it = 0
            while os.path.exists(backup_path) and len(os.listdir(backup_path)) != 0:
                it += 1
                backup_path = get_version_dir(pdk_root, "gf180mcu", f"{version}.bk{it}")
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
            shutil.copytree(variant_build_path, variant_install_path)

    console.log("Done.")


def build(
    pdk_root: str,
    version: str,
    jobs: int = 1,
    sram: bool = True,
    clear_build_artifacts: bool = True,
    include_libraries: Optional[List[str]] = None,
    using_repos: Optional[Dict[str, str]] = None,
    build_magic: bool = False,
):
    if include_libraries is None or len(include_libraries) == 0:
        include_libraries = [
            "gf180mcu_fd_sc_mcu7t5v0",
            "gf180mcu_fd_sc_mcu9t5v0",
            "gf180mcu_fd_io",
            "gf180mcu_fd_pr",
        ]

    if sram:
        include_libraries.append("gf180mcu_fd_bd_sram")

    if using_repos is None:
        using_repos = {}

    timestamp = datetime.now().strftime("build_gf180mcu-%Y-%m-%d-%H-%M-%S")
    log_dir = os.path.join(get_logs_dir(), timestamp)
    mkdirp(log_dir)

    console = Console()
    console.log(f"Logging to '{log_dir}'…")

    build_directory = os.path.join(
        get_volare_dir(pdk_root, "gf180mcu"), "build", version
    )
    open_pdks_path, _, magic_tag = get_open_pdks(
        version, build_directory, jobs, using_repos.get("open_pdks")
    )
    with_magic(
        magic_tag,
        lambda magic_bin: build_variants(
            magic_bin,
            include_libraries,
            build_directory,
            open_pdks_path,
            log_dir,
            jobs,
        ),
        build_magic=build_magic,
    )
    install_gf180mcu(build_directory, pdk_root, version)

    if clear_build_artifacts:
        shutil.rmtree(build_directory)
