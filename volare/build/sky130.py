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
import venv
import shutil
import subprocess
from datetime import datetime
from typing import Optional, List, Tuple, Dict
from concurrent.futures import ThreadPoolExecutor

import pcpp
from rich.console import Console
from rich.progress import Progress

from .git_multi_clone import GitMultiClone
from .magic import with_magic
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
        "34eeb2743e99d44a21c2cedd467675a2e0f3bb91",
        "master",
    ),
    "sky130": RepoMetadata(
        "https://github.com/google/skywater-pdk",
        "f70d8ca46961ff92719d8870a18a076370b85f6c",
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

        sky130_tag = None
        magic_tag = None

        try:
            json_raw = open(f"{repo_path}/sky130/sky130.json").read()
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
            sky130_tag = reference_commits["skywater_pdk"]
        except FileNotFoundError:
            console.log(
                "Cannot find open_pdks/sky130 JSON manifest. Default versions for sky130/magic will be used."
            )
        except json.JSONDecodeError:
            console.log(
                "Failed to parse open_pdks/sky130 JSON manifest. Default versions for sky130/magic will be used."
            )
        except KeyError:
            console.log(
                "Failed to extract reference commits from open_pdks/sky130 JSON manifest. Default versions for sky130/magic will be used."
            )

        return (repo_path, sky130_tag, magic_tag)

    except subprocess.CalledProcessError as e:
        print(e)
        print(e.stderr)
        exit(os.EX_DATAERR)


def get_sky130(
    include_libraries, build_directory, commit=None, jobs=1, repo_path=None
) -> str:
    try:
        if repo_path is not None:
            return repo_path

        all = "all" in include_libraries
        console = Console()

        sky130_repo = None
        sky130_submodules = []

        sky130 = repo_metadata["sky130"]
        sky130_commit = commit or sky130.default_commit
        console.log(f"Using sky130 {sky130_commit}…")

        with Progress() as progress:
            with ThreadPoolExecutor(max_workers=jobs) as executor:
                gmc = GitMultiClone(build_directory, progress)
                sky130_fut = executor.submit(
                    GitMultiClone.clone,
                    gmc,
                    sky130.repo,
                    sky130_commit,
                    sky130.default_branch,
                )
                sky130_repo = sky130_fut.result()
                repo_path = sky130_repo.path
                sky130_submodules = (
                    subprocess.check_output(
                        ["find", "libraries", "-type", "d", "-name", "latest"],
                        stderr=subprocess.PIPE,
                        cwd=sky130_repo.path,
                    )
                    .decode("utf8")
                    .strip()
                    .split("\n")
                )
                sky130_submodules_filtered = [
                    sm
                    for sm in sky130_submodules
                    if (sm.split("/")[1] in include_libraries or all)
                ]
                for submodule in sky130_submodules_filtered:
                    executor.submit(
                        GitMultiClone.clone_submodule, gmc, sky130_repo, submodule
                    )
        console.log("Done fetching sky130 repositories.")
        return repo_path

    except subprocess.CalledProcessError as e:
        print(e)
        print(e.stderr)
        exit(os.EX_DATAERR)


def build_sky130_timing(build_directory, sky130_path, log_dir, jobs=1):
    try:
        console = Console()
        sky130_submodules = (
            subprocess.check_output(
                ["find", "./libraries", "-type", "d", "-name", "latest"],
                stderr=subprocess.PIPE,
                cwd=sky130_path,
            )
            .decode("utf8")
            .strip()
            .split("\n")
        )

        venv_path = os.path.join(build_directory, "venv")

        with console.status("Building venv…"):
            venv_builder = venv.EnvBuilder(with_pip=True)
            venv_builder.create(venv_path)
        console.log("Done building venv.")

        with console.status("Installing python-skywater-pdk in venv…"), open(
            f"{log_dir}/venv.log", "w"
        ) as out:
            subprocess.check_call(
                [
                    "bash",
                    "-c",
                    f"""
                        set -e
                        source {venv_path}/bin/activate
                        python3 -m pip install wheel
                        python3 -m pip install {os.path.join(sky130_path, 'scripts', 'python-skywater-pdk')}
                    """,
                ],
                stdout=out,
                stderr=out,
            )
        console.log("Done setting up venv.")

        def do_submodule(submodule: str):
            submodule_cleaned = submodule.strip("/.").replace("/", "_")
            console.log(f"Generating timing files for {submodule}…")
            with open(f"{log_dir}/timing.{submodule_cleaned}.log", "w") as out:
                subprocess.check_call(
                    [
                        "bash",
                        "-c",
                        f"""
                            set -e
                            source {venv_path}/bin/activate
                            cd {sky130_path}
                            python3 -m skywater_pdk.liberty {submodule}
                            python3 -m skywater_pdk.liberty {submodule} all
                            python3 -m skywater_pdk.liberty {submodule} all --ccsnoise
                        """,
                    ],
                    stdout=out,
                    stderr=out,
                )
            console.log(f"Done with {submodule}.")

        with ThreadPoolExecutor(max_workers=jobs) as executor:
            for submodule in sky130_submodules:
                submodule_path = os.path.join(sky130_path, submodule)
                if (
                    not os.path.exists(os.path.join(submodule_path, "cells"))
                    or "_sc" not in submodule
                ):
                    continue
                executor.submit(
                    do_submodule,
                    submodule,
                )
        console.log("Created timing data.")

    except subprocess.CalledProcessError as e:
        print(e)
        print(e.stderr)
        exit(os.EX_DATAERR)


def build_variants(
    magic_bin,
    sram,
    build_directory,
    open_pdks_path,
    sky130_path,
    log_dir,
    jobs=1,
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

        sram_opt = "--enable-sram-sky130" if sram else ""
        magic_dirname = os.path.dirname(magic_bin)

        with console.status("Configuring open_pdks…"):
            run_sh(
                f"""
                    set -e
                    export PATH="{magic_dirname}:$PATH"
                    ./configure --enable-sky130-pdk={sky130_path}/libraries {sram_opt} --with-reference
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


def install_sky130(build_directory, pdk_root, version):
    console = Console()
    with console.status("Adding build to list of installed versions…"):
        version_directory = get_version_dir(pdk_root, "sky130", version)
        if (
            os.path.exists(version_directory)
            and len(os.listdir(version_directory)) != 0
        ):
            backup_path = version_directory
            it = 0
            while os.path.exists(backup_path) and len(os.listdir(backup_path)) != 0:
                it += 1
                backup_path = get_version_dir(pdk_root, "sky130", f"{version}.bk{it}")
            console.log(
                f"Build already found at {version_directory}, moving to {backup_path}…"
            )
            shutil.move(version_directory, backup_path)

        console.log("Copying…")
        mkdirp(version_directory)

        sky130_family = Family.by_name["sky130"]

        for variant in sky130_family.variants:
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
            "sky130_fd_sc_hd",
            "sky130_fd_sc_hvl",
            "sky130_fd_io",
            "sky130_fd_pr",
        ]

    if using_repos is None:
        using_repos = {}

    timestamp = datetime.now().strftime("build_sky130-%Y-%m-%d-%H-%M-%S")
    log_dir = os.path.join(get_logs_dir(), timestamp)
    mkdirp(log_dir)

    console = Console()
    console.log(f"Logging to '{log_dir}'…")

    build_directory = os.path.join(get_volare_dir(pdk_root, "sky130"), "build", version)
    open_pdks_path, sky130_tag, magic_tag = get_open_pdks(
        version, build_directory, jobs, using_repos.get("open_pdks")
    )
    sky130_path = get_sky130(
        include_libraries, build_directory, sky130_tag, jobs, using_repos.get("sky130")
    )
    build_sky130_timing(build_directory, sky130_path, log_dir, jobs)

    with_magic(
        magic_tag,
        lambda magic_bin: build_variants(
            magic_bin,
            sram,
            build_directory,
            open_pdks_path,
            sky130_path,
            log_dir,
            jobs,
        ),
        build_magic=build_magic,
    )
    install_sky130(build_directory, pdk_root, version)

    if clear_build_artifacts:
        shutil.rmtree(build_directory)
