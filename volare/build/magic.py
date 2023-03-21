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
import tarfile
import tempfile
import platform
import subprocess
from typing import Callable, TypeVar

import requests
from rich.console import Console

from ..common import mkdirp

T = TypeVar("T")


def with_magic(
    magic_tag: str,
    callable: Callable[[str], T],
    build_magic: bool = False,
) -> T:
    if not build_magic:
        magic_bin = shutil.which("magic")
        if magic_bin is not None:
            return callable(magic_bin)
        else:
            raise ValueError("Magic not found in PATH.")
    else:
        if platform.system() != "Linux":
            raise RuntimeError(
                "Building magic is not supported on non-Linux platforms."
            )
    with tempfile.TemporaryDirectory() as d:
        magic_dir = os.path.join(d, "src")
        magic_tgz = os.path.join(d, "magic_src.tgz")
        magic_pfx = os.path.join(d, "pfx")
        magic_bin = os.path.join(magic_pfx, "bin", "magic")

        console = Console()
        console.status("Downloading Magic repo…")
        magic_req = requests.get(
            f"https://github.com/RTimothyEdwards/magic/tarball/{magic_tag}",
            allow_redirects=True,
        )
        with open(magic_tgz, "wb") as f:
            f.write(magic_req.content)
        console.log("Downloaded Magic repo.")

        with tarfile.open(magic_tgz, mode="r:*") as tf:
            for _, file in enumerate(tf.getmembers()):
                if file.isdir():
                    continue
                components = file.name.split(os.path.sep)
                if components[0] == "":
                    components = components[1:]
                components = components[1:]
                final_path = os.path.join(magic_dir, os.path.sep.join(components))
                io = tf.extractfile(file)
                final_dir = os.path.dirname(final_path)
                mkdirp(final_dir)
                with open(final_path, "wb") as f:
                    f.write(io.read())

                os.chmod(final_path, file.mode)

        try:
            with console.status("Building Magic…"):
                subprocess.check_output(
                    ["sh", "./configure", f"--prefix={magic_pfx}"],
                    cwd=magic_dir,
                    stderr=subprocess.STDOUT,
                )

                subprocess.check_output(
                    ["make", "-j", str(os.cpu_count())],
                    cwd=magic_dir,
                    stderr=subprocess.STDOUT,
                )

                subprocess.check_output(
                    ["make", "install"],
                    cwd=magic_dir,
                    stderr=subprocess.STDOUT,
                )

            if not os.path.exists(magic_bin):
                raise RuntimeError("Failed to build Magic.")

            console.log("Done building Magic.")
        except subprocess.SubprocessError as e:
            console.log(e.stdout)

        return callable(magic_bin)
