import os
import uuid
import pathlib
import tarfile
import tempfile
import importlib
import subprocess
from typing import Optional, List

import rich
import click
from rich.progress import Progress

from ..common import (
    mkdirp,
    opt_push,
    opt_build,
    opt_pdk_root,
    check_version,
    get_version_dir,
    VOLARE_REPO_NAME,
    VOLARE_REPO_OWNER,
    get_date_of,
    date_to_iso8601,
)
from ..families import Family


def build(
    pdk_root: str,
    pdk: str,
    version: str,
    jobs: int = 1,
    sram: bool = True,
    clear_build_artifacts: bool = True,
    include_libraries: Optional[List[str]] = None,
    use_repo_at: Optional[List[str]] = None,
):
    use_repos = {}
    if use_repo_at is not None:
        for repo in use_repo_at:
            name, path = repo.split("=")
            use_repos[name] = os.path.abspath(path)

    if Family.by_name[pdk] is None:
        raise Exception(f"Unsupported PDK family '{pdk}'.")

    kwargs = {
        "pdk_root": pdk_root,
        "version": version,
        "jobs": jobs,
        "sram": sram,
        "clear_build_artifacts": clear_build_artifacts,
        "include_libraries": include_libraries,
        "using_repos": use_repos,
    }

    build_module = importlib.import_module(f".{pdk}", package=__name__)
    build_function = build_module.build
    build_function(**kwargs)


@click.command("build")
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
    sram,
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

    version = check_version(version, tool_metadata_file_path, rich.console.Console())
    build(
        pdk_root=pdk_root,
        pdk=pdk,
        version=version,
        jobs=jobs,
        sram=sram,
        clear_build_artifacts=clear_build_artifacts,
        include_libraries=include_libraries,
        use_repo_at=use_repo_at,
    )


def push(
    pdk_root,
    pdk,
    version,
    owner=VOLARE_REPO_OWNER,
    repository=VOLARE_REPO_NAME,
    token=os.getenv("GITHUB_TOKEN"),
    pre=False,
):
    console = rich.console.Console()

    version_directory = get_version_dir(pdk_root, pdk, version)
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

    tag = f"{pdk}-{version}"

    # If someone wants to rewrite this to not use ghr, please, by all means.
    console.log("Starting upload…")

    body = f"{pdk} variants built using volare"
    date = get_date_of(version)
    if date is not None:
        body = f"{pdk} variants built using open_pdks {version} (released on {date_to_iso8601(date)})"
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
@opt_pdk_root
@opt_push
@click.argument("version")
def push_cmd(owner, repository, token, pre, pdk_root, pdk, version):
    """
    For maintainers: Package and release a build to the public.

    Requires ghr: github.com/tcnksm/ghr

    Parameters: <version> (required)
    """
    push(pdk_root, pdk, version, owner, repository, token, pre)
