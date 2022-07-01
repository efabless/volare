import os
import venv
import uuid
import shutil
import subprocess
from datetime import datetime
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor

import rich
from rich.progress import Progress

from .git_multi_clone import GitMultiClone, Repository
from ..common import (
    get_logs_dir,
    get_version_dir,
    get_volare_dir,
    get_variants,
    mkdirp,
    RepoMetadata,
)


repo_metadata = {
    "open_pdks": RepoMetadata(
        "https://github.com/efabless/open_pdks",
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
        "085131b090cb511d785baf52a10cf6df8a657d44",
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
                open_pdks = repo_metadata["open_pdks"]
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
                sky130 = repo_metadata["sky130"]
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

        timestamp = datetime.now().strftime("timing-%Y-%m-%d-%H-%M-%S")
        log_dir = os.path.join(get_logs_dir(), timestamp)
        mkdirp(log_dir)

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
                        python3 -m pip install {os.path.join(sky130_repo.path, 'scripts', 'python-skywater-pdk')}
                    """,
                ],
                stdout=out,
                stderr=out,
            )
        console.log("Done setting up venv.")

        def do_submodule(submodule: str):
            submodule_cleaned = submodule.strip("/.").replace("/", "_")
            console.log(f"Processing {submodule}…")
            with open(f"{log_dir}/timing.{submodule_cleaned}.log", "w") as out:
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
                    stdout=out,
                    stderr=out,
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


def build_variants(sram, build_directory, jobs=1):
    try:
        console = rich.console.Console()

        magic_tag = repo_metadata["magic"].default_commit

        # TODO: Get magic version from open_pdks
        magic_image = f"efabless/openlane-tools:magic-{magic_tag}-centos-7"

        subprocess.check_call(["docker", "pull", magic_image])

        timestamp = datetime.now().strftime("open_pdks-%Y-%m-%d-%H-%M-%S")
        log_dir = os.path.join(get_logs_dir(), timestamp)
        mkdirp(log_dir)

        docker_ids = set()

        def docker_run_sh(*args, log_to):
            nonlocal docker_ids
            output_file = open(log_to, "w")
            container_id = str(uuid.uuid4())
            docker_ids.add(container_id)
            args = list(args)
            pdk_root_abs = os.path.abspath(build_directory)
            try:
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
                        "sh",
                        "-c",
                    ]
                    + args,
                    stdout=output_file,
                    stderr=output_file,
                )
            except subprocess.CalledProcessError as e:
                console.log(
                    f"An error occurred while building the PDK. Check {log_to} for more information."
                )
                docker_ids.remove(container_id)
                raise e
            docker_ids.remove(container_id)

        sram_opt = "--enable-sram-sky130" if sram else ""

        interrupted = None
        try:
            console.log("Configuring open_pdks…")
            docker_run_sh(
                f"""
                    set +e
                    cd open_pdks
                    ./configure --enable-sky130-pdk=$PDK_ROOT/skywater-pdk/libraries {sram_opt}
                """,
                log_to=os.path.join(log_dir, "config.log"),
            )
            console.log("Done.")

            console.log("Building variants using open_pdks…")
            docker_run_sh(
                f"""
                    set +e
                    cd open_pdks
                    export LC_ALL=en_US.UTF-8
                    make -j{jobs}
                    make SHARED_PDKS_PATH=$PDK_ROOT install
                """,
                log_to=os.path.join(log_dir, "install.log"),
            )
        except KeyboardInterrupt as e:
            interrupted = e
            console.log("Stopping on keyboard interrupt…")
            console.log("Killing docker containers…")
            for id in docker_ids:
                subprocess.call(["docker", "kill", id])

        console.log("Fixing file ownership…")
        docker_run_sh(
            """
                set +e
                OWNERSHIP="$(stat -c "%u:%g" $PDK_ROOT)"
                chown -R $OWNERSHIP $PDK_ROOT
            """,
            log_to=os.path.join(log_dir, "ownership.log"),
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

        for variant in get_variants("sky130"):
            variant_build_path = os.path.join(build_directory, variant)
            variant_install_path = os.path.join(version_directory, variant)
            shutil.copytree(variant_build_path, variant_install_path)

    console.log("Done.")


def build_sky130(
    pdk_root: str,
    version: str,
    jobs: int = 1,
    sram: bool = True,
    clear_build_artifacts: bool = True,
    include_libraries: Optional[List[str]] = None,
):
    if include_libraries is None or len(include_libraries) == 0:
        include_libraries = [
            "sky130_fd_sc_hd",
            "sky130_fd_sc_hvl",
            "sky130_fd_io",
            "sky130_fd_pr",
        ]

    build_directory = os.path.join(get_volare_dir(pdk_root, "sky130"), "build", version)
    get_open_pdks(version, build_directory, jobs)
    get_sky130(include_libraries, build_directory, jobs)
    build_sky130_timing(build_directory, jobs)
    build_variants(sram, build_directory, jobs)
    install_sky130(build_directory, pdk_root, version)

    if clear_build_artifacts:
        shutil.rmtree(build_directory)
