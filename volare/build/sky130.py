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
        exit(-1)


LIB_FLAG_MAP = {
    "sky130_fd_io": "--enable-io-sky130",
    "sky130_fd_pr": "--enable-primitive-sky130",
    "sky130_ml_xx_hd": "--enable-alpha-sky130",
    "sky130_fd_sc_hd": "--enable-sc-hd-sky130",
    "sky130_fd_sc_hdll": "--enable-sc-hdll-sky130",
    "sky130_fd_sc_lp": "--enable-sc-lp-sky130",
    "sky130_fd_sc_hvl": "--enable-sc-hvl-sky130",
    "sky130_fd_sc_ls": "--enable-sc-ls-sky130",
    "sky130_fd_sc_ms": "--enable-sc-ms-sky130",
    "sky130_fd_sc_hs": "--enable-sc-hs-sky130",
    "sky130_sram_macros": "--enable-sram-sky130",
    "sky130_fd_pr_reram": "--enable-reram-sky130",
}


def build_variants(
    magic_bin,
    build_directory,
    open_pdks_path,
    include_libraries,
    log_dir,
    jobs=1,
):
    try:
        pdk_root_abs = os.path.abspath(build_directory)
        console = Console()

        def run_sh(script, log_to):
            output_file = open(log_to, "w")
            output_file.write(script + "\n")
            output_file.write("---\n")
            output_file.flush()
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

        magic_dirname = os.path.dirname(magic_bin)
        library_flags = set([LIB_FLAG_MAP[library] for library in include_libraries])
        library_flags_disable = set(
            [
                LIB_FLAG_MAP[library].replace("enable", "disable")
                for library in LIB_FLAG_MAP
                if library not in include_libraries
            ]
        )

        configuration_flags = ["--enable-sky130-pdk", "--with-reference"] + list(
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


def install_sky130(build_directory, pdk_root, version):
    console = Console()
    with console.status("Adding build to list of installed versions…"):
        version_directory = Version("sky130", version).get_dir(pdk_root)
        if (
            os.path.exists(version_directory)
            and len(os.listdir(version_directory)) != 0
        ):
            backup_path = version_directory
            it = 0
            while os.path.exists(backup_path) and len(os.listdir(backup_path)) != 0:
                it += 1
                backup_path = Version(f"{version}.bk{it}", version).get_dir(pdk_root)
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
    family = Family.by_name["sky130"]
    library_set = family.resolve_libraries(include_libraries)

    if using_repos is None:
        using_repos = {}

    build_directory = os.path.join(get_volare_dir(pdk_root, "sky130"), "build", version)
    timestamp = datetime.now().strftime("build_sky130-%Y-%m-%d-%H-%M-%S")
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
        build_directory,
        open_pdks_path,
        library_set,
        log_dir,
        jobs,
    ),
    install_sky130(build_directory, pdk_root, version)

    if clear_build_artifacts:
        shutil.rmtree(build_directory)
