#!/usr/bin/env python3
# Copyright 2022 Efabless Corporation
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
import venv
import uuid
import shutil
import pathlib
import tarfile
import tempfile
import subprocess
from concurrent.futures import ThreadPoolExecutor

import rich
import click
from rich.progress import Progress

from .git_multi_clone import GitMultiClone, Repository, mkdirp
from .common import (
    opt,
    opt_pdk_root,
    check_version,
    get_version_dir,
    get_volare_dir,
    SKY130_VARIANTS,
)


class RepoMetadata(object):
    def __init__(self, repo, default_commit, default_branch="main"):
        self.repo = repo
        self.default_commit = default_commit
        self.default_branch = default_branch


RepoMetadata.by_name = {
    "open_pdks": RepoMetadata(
        "https://github.com/RTimothyEdwards/open_pdks",
        "34eeb2743e99d44a21c2cedd467675a2e0f3bb91",
        "master",
    ),
    "sky130": RepoMetadata(
        "https://github.com/google/skywater-pdk",
        "f70d8ca46961ff92719d8870a18a076370b85f6c",
        "main",
    ),
    "magic": RepoMetadata(
        "https://github.com/RTimothyEdwards/magic",
        "d98645afc1498a41db7aff4b2e100f27e0b0bd9b",
        "master",
    ),
}


def get_open_pdks(version, build_directory, jobs=1):
    try:
        console = rich.console.Console()

        open_pdks_repo = None

        with Progress() as progress:
            with ThreadPoolExecutor(max_workers=jobs) as executor:
                gmc = GitMultiClone(build_directory, progress)
                open_pdks = RepoMetadata.by_name["open_pdks"]
                open_pdks_future = executor.submit(
                    GitMultiClone.clone,
                    gmc,
                    open_pdks.repo,
                    version,
                    open_pdks.default_branch,
                )
                open_pdks_repo = open_pdks_future.result()

        console.log(f"Done fetching {open_pdks_repo.name}.")

    except subprocess.CalledProcessError as e:
        print(e)
        print(e.stderr)
        exit(os.EX_DATAERR)


def get_sky130(include_libraries, build_directory, jobs=1):
    try:
        all = "all" in include_libraries
        console = rich.console.Console()

        sky130_repo = None
        sky130_submodules = []

        with Progress() as progress:
            with ThreadPoolExecutor(max_workers=jobs) as executor:
                gmc = GitMultiClone(build_directory, progress)
                sky130 = RepoMetadata.by_name["sky130"]
                # TODO: Get sky130 commit from open_pdks
                sky130_fut = executor.submit(
                    GitMultiClone.clone,
                    gmc,
                    sky130.repo,
                    sky130.default_commit,
                    sky130.default_branch,
                )
                sky130_repo = sky130_fut.result()
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
        console.log("Done fetching repositories.")

    except subprocess.CalledProcessError as e:
        print(e)
        print(e.stderr)
        exit(os.EX_DATAERR)


def build_sky130_timing(build_directory, jobs=1):
    try:
        console = rich.console.Console()
        sky130_repo = Repository.from_path(
            os.path.join(build_directory, "skywater-pdk")
        )
        sky130_submodules = (
            subprocess.check_output(
                ["find", "./libraries", "-type", "d", "-name", "latest"],
                stderr=subprocess.PIPE,
                cwd=sky130_repo.path,
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

        mkdirp("/tmp/volare/logs")

        with console.status("Installing python-skywater-pdk in venv…"), open(
            "/tmp/volare/logs/venv.stdout", "w"
        ) as so, open("/tmp/volare/logs/venv.stderr", "w") as se:
            subprocess.check_call(
                [
                    "bash",
                    "-c",
                    f"""
                        set -e
                        source {venv_path}/bin/activate
                        python3 -m pip install wheel
                        python3 -m pip install {os.path.join(sky130_repo.path, 'scripts', 'python-skywater-pdk')}
                    """,
                ],
                stdout=so,
                stderr=se,
            )
        console.log("Done setting up venv.")

        def do_submodule(submodule: str):
            submodule_cleaned = submodule.strip("/.").replace("/", "_")
            console.log(f"Processing {submodule}…")
            with open(
                f"/tmp/volare/logs/{submodule_cleaned}.timing.stdout", "w"
            ) as so, open(
                f"/tmp/volare/logs/{submodule_cleaned}.timing.stderr", "w"
            ) as se:
                subprocess.check_call(
                    [
                        "bash",
                        "-c",
                        f"""
                            set -e
                            source {venv_path}/bin/activate
                            cd {sky130_repo.path}
                            python3 -m skywater_pdk.liberty {submodule}
                            python3 -m skywater_pdk.liberty {submodule} all
                            python3 -m skywater_pdk.liberty {submodule} all --ccsnoise
                        """,
                    ],
                    stdout=so,
                    stderr=se,
                )
            console.log(f"Done with {submodule}.")

        with ThreadPoolExecutor(max_workers=jobs) as executor:
            for submodule in sky130_submodules:
                submodule_path = os.path.join(sky130_repo.path, submodule)
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


def build_sky130(sram, build_directory, jobs=1):
    try:
        console = rich.console.Console()

        magic_tag = RepoMetadata.by_name["magic"].default_commit

        # TODO: Get magic version from open_pdks
        magic_image = f"efabless/openlane-tools:magic-{magic_tag}-centos-7"

        subprocess.check_call(["docker", "pull", magic_image])

        docker_ids = set()

        def docker_run(*args):
            nonlocal docker_ids
            container_id = str(uuid.uuid4())
            docker_ids.add(container_id)
            args = list(args)
            pdk_root_abs = os.path.abspath(build_directory)
            subprocess.check_call(
                [
                    "docker",
                    "run",
                    "--name",
                    container_id,
                    "--rm",
                    "-e",
                    f"PDK_ROOT={pdk_root_abs}",
                    "-v",
                    f"{pdk_root_abs}:{pdk_root_abs}",
                    "-w",
                    f"{pdk_root_abs}",
                    magic_image,
                ]
                + args
            )
            docker_ids.remove(container_id)

        sram_opt = "--enable-sram-sky130" if sram else ""

        interrupted = None
        try:
            console.log("Configuring open_pdks…")
            docker_run(
                "sh",
                "-c",
                f"""
                    set +e
                    cd open_pdks
                    ./configure --enable-sky130-pdk=$PDK_ROOT/skywater-pdk/libraries {sram_opt}
                """,
            )
            console.log("Done.")

            console.log("Building prequisites…")
            docker_run(
                "sh",
                "-c",
                f"""
                    set +e
                    cd open_pdks/sky130
                    make -j{jobs} prerequisites
                """,
            )
            console.log("Done.")

            console.log("Building sky130A/B…")
            docker_run(
                "sh",
                "-c",
                f"""
                    set +e
                    cd open_pdks/sky130
                    export LC_ALL=en_US.UTF-8
                    make -j{jobs}
                    make SHARED_PDKS_PATH=$PDK_ROOT install
                """,
            )
        except KeyboardInterrupt as e:
            interrupted = e
            console.log("Stopping on keyboard interrupt…")
            console.log("Killing docker containers…")
            for id in docker_ids:
                subprocess.call(["docker", "kill", id])
        console.log("Attempting to fix ownership…")
        docker_run(
            "sh",
            "-c",
            """
                set +e
                OWNERSHIP="$(stat -c "%u:%g" $PDK_ROOT)"
                chown -R $OWNERSHIP $PDK_ROOT
            """,
        )
        if interrupted is not None:
            raise interrupted
        else:
            console.log("Done.")

    except subprocess.CalledProcessError as e:
        print(e)
        print(e.stderr)
        exit(os.EX_DATAERR)


def install_sky130(build_directory, pdk_root, version):
    console = rich.console.Console()
    with console.status("Adding build to list of installed versions…"):
        version_directory = get_version_dir(pdk_root, version)
        if (
            os.path.exists(version_directory)
            and len(os.listdir(version_directory)) != 0
        ):
            backup_path = version_directory
            it = 0
            while os.path.exists(backup_path) and len(os.listdir(backup_path)) != 0:
                it += 1
                backup_path = get_version_dir(pdk_root, f"{version}.bk{it}")
            console.log(
                f"Build already found at {version_directory}, moving to {backup_path}…"
            )
            shutil.move(version_directory, backup_path)

        console.log("Copying…")
        mkdirp(version_directory)

        for variant in SKY130_VARIANTS:
            variant_build_path = os.path.join(build_directory, variant)
            variant_install_path = os.path.join(version_directory, variant)
            shutil.copytree(variant_build_path, variant_install_path)

    console.log("Done.")


# ---


@click.command()
@opt_pdk_root
@opt(
    "-l",
    "--include-libraries",
    multiple=True,
    default=["sky130_fd_sc_hd", "sky130_fd_sc_hvl", "sky130_fd_io", "sky130_fd_pr"],
    help="Libraries to include in the build. You can use -l multiple times to include multiple libraries. Pass 'all' to include all of them.",
)
@opt(
    "-j",
    "--jobs",
    default=1,
    help="Specifies the number of commands to run simultaneously.",
)
@opt("--sram/--no-sram", default=True, help="Enable or disable sram")
@opt(
    "--clear-build-artifacts/--keep-build-artifacts",
    default=False,
    help="Whether or not to remove the build artifacts. Keeping the build artifacts is useful when testing.",
)
@click.option(
    "-f",
    "--metadata-file",
    "tool_metadata_file_path",
    default=None,
    help="Explicitly define a tool metadata file instead of searching for a metadata file",
)
@click.argument("version", required=False)
def build(
    include_libraries,
    jobs,
    sram,
    pdk_root,
    clear_build_artifacts,
    tool_metadata_file_path,
    version,
):
    """
    Builds the sky130 PDK using open_pdks.

    Parameters: <version> (Optional)

    If a version is not given, and you run this in the top level directory of
    tools with a tool_metadata.yml file, for example OpenLane or DFFRAM,
    the appropriate version will be enabled automatically.
    """

    version = check_version(version, tool_metadata_file_path, rich.console.Console())

    build_directory = os.path.join(get_volare_dir(pdk_root), "build", version)
    get_open_pdks(version, build_directory, jobs)
    get_sky130(include_libraries, build_directory, jobs)
    build_sky130_timing(build_directory, jobs)
    build_sky130(sram, build_directory, jobs)
    install_sky130(build_directory, pdk_root, version)

    if clear_build_artifacts:
        shutil.rmtree(build_directory)


@click.command(hidden=True)
@opt_pdk_root
@opt("-o", "--owner", default="efabless", help="Repository Owner")
@opt("-r", "--repository", default="volare", help="Repository")
@opt(
    "-t",
    "--token",
    required=(os.getenv("GITHUB_TOKEN") is None),
    default=os.getenv("GITHUB_TOKEN"),
    help="Github Token",
)
@click.argument("version")
def push(owner, repository, token, pdk_root, version):
    """
    For maintainers: Package and release a build to the public.

    Requires ghr: github.com/tcnksm/ghr

    Parameters: <version> (required)
    """

    console = rich.console.Console()

    version_directory = get_version_dir(pdk_root, version)
    if not os.path.isdir(version_directory):
        console.print("[red]Version not found.")
        exit(os.EX_NOINPUT)

    tempdir = tempfile.gettempdir()
    tarball_directory = os.path.join(tempdir, "volare", f"{uuid.uuid4()}", version)
    mkdirp(tarball_directory)

    tarball_path = os.path.join(tarball_directory, "default.tar.xz")

    with Progress() as progress:
        path_it = pathlib.Path(version_directory).glob("**/*")
        files = [str(path) for path in path_it if path.is_file()]
        task = progress.add_task("Compressing…", total=len(files))
        with tarfile.open(tarball_path, mode="w:xz") as tf:
            for i, file in enumerate(files):
                progress.update(task, completed=i + 1)
                path_in_tarball = os.path.relpath(file, version_directory)
                tf.add(file, arcname=path_in_tarball)
    console.log(f"Compressed to {tarball_path}.")

    tag = f"sky130-{version}"

    # If someone wants to rewrite this to not use ghr, please, by all means.
    console.log("Starting upload…")
    subprocess.check_call(
        [
            "ghr",
            "-owner",
            owner,
            "-repository",
            repository,
            "-token",
            token,
            "-body",
            f"Volare build of sky130 with Open_PDKs {version}",
            "-commitish",
            "releases",
            tag,
            tarball_path,
        ]
    )
    console.log("Done.")
