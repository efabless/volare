import os
import io
import json
import uuid
import shutil
import subprocess
from datetime import datetime
from typing import Optional, List, Tuple, Dict
from concurrent.futures import ThreadPoolExecutor

import pcpp
import rich
from rich.progress import Progress

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
        console = rich.console.Console()

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


def get_gf180mcu(
    include_libraries, build_directory, commit=None, jobs=1, repo_path=None
) -> str:
    try:
        if repo_path is not None:
            return repo_path

        all = "all" in include_libraries
        console = rich.console.Console()

        gf180mcu_repo = None
        gf180mcu_submodules = []

        gf180mcu = repo_metadata["gf180mcu"]
        gf180mcu_commit = commit or gf180mcu.default_commit
        console.log(f"Using gf180mcu {gf180mcu_commit}…")

        with Progress() as progress:
            with ThreadPoolExecutor(max_workers=jobs) as executor:
                gmc = GitMultiClone(build_directory, progress)
                gf180mcu_fut = executor.submit(
                    GitMultiClone.clone,
                    gmc,
                    gf180mcu.repo,
                    gf180mcu_commit,
                    gf180mcu.default_branch,
                )
                gf180mcu_repo = gf180mcu_fut.result()
                repo_path = gf180mcu_repo.path
                gf180mcu_submodules = (
                    subprocess.check_output(
                        ["find", "libraries", "-type", "d", "-name", "latest"],
                        stderr=subprocess.PIPE,
                        cwd=gf180mcu_repo.path,
                    )
                    .decode("utf8")
                    .strip()
                    .split("\n")
                )
                gf180mcu_submodules_filtered = [
                    sm
                    for sm in gf180mcu_submodules
                    if (sm.split("/")[1] in include_libraries or all)
                ]
                for submodule in gf180mcu_submodules_filtered:
                    executor.submit(
                        GitMultiClone.clone_submodule, gmc, gf180mcu_repo, submodule
                    )
        console.log("Done fetching gf180mcu repositories.")
        return repo_path

    except subprocess.CalledProcessError as e:
        print(e)
        print(e.stderr)
        exit(os.EX_DATAERR)


def build_variants(
    sram, build_directory, open_pdks_path, gf180mcu_path, magic_tag, log_dir, jobs=1
):
    try:
        console = rich.console.Console()

        magic_tag = magic_tag or MAGIC_DEFAULT_TAG

        console.log(f"Using magic {magic_tag}…")

        magic_image = f"efabless/openlane-tools:magic-{magic_tag}-centos-7"

        subprocess.check_call(["docker", "pull", magic_image])

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
                        "-e",
                        f"GF180MCU_PATH={gf180mcu_path}",
                        "-v",
                        f"{gf180mcu_path}:{gf180mcu_path}",
                        "-e",
                        f"OPEN_PDKS_PATH={open_pdks_path}",
                        "-v",
                        f"{open_pdks_path}:{open_pdks_path}",
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

        sram_opt = "--enable-sram-gf180mcu" if sram else ""

        interrupted = None
        try:
            console.log("Configuring open_pdks…")
            docker_run_sh(
                f"""
                    set +e
                    cd $OPEN_PDKS_PATH
                    ./configure --enable-gf180mcu-pdk=$GF180MCU_PATH/libraries {sram_opt}
                """,
                log_to=os.path.join(log_dir, "config.log"),
            )
            console.log("Done.")

            console.log("Building variants using open_pdks…")
            docker_run_sh(
                f"""
                    set +e
                    cd $OPEN_PDKS_PATH
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


def install_gf180mcu(build_directory, pdk_root, version):
    console = rich.console.Console()
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
    using_repos: Dict[str, str] = None,
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

    timestamp = datetime.now().strftime("build_gf180mcu-%Y-%m-%d-%H-%M-%S")
    log_dir = os.path.join(get_logs_dir(), timestamp)
    mkdirp(log_dir)

    console = rich.console.Console()
    console.log(f"Logging to '{log_dir}'…")

    build_directory = os.path.join(
        get_volare_dir(pdk_root, "gf180mcu"), "build", version
    )
    open_pdks_path, gf180mcu_tag, magic_tag = get_open_pdks(
        version, build_directory, jobs, using_repos.get("open_pdks")
    )
    gf180mcu_path = get_gf180mcu(
        include_libraries,
        build_directory,
        gf180mcu_tag,
        jobs,
        using_repos.get("gf180mcu"),
    )
    build_variants(
        sram, build_directory, open_pdks_path, gf180mcu_path, magic_tag, log_dir, jobs
    )
    install_gf180mcu(build_directory, pdk_root, version)

    if clear_build_artifacts:
        shutil.rmtree(build_directory)
