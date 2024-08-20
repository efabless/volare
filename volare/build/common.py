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

from volare.github import GitHubSession


def open_pdks_fix_makefile(at_path: str):
    backup_path = f"{at_path}.bak"
    shutil.move(at_path, backup_path)

    fix_fi = False

    with open(backup_path, "r") as file_in, open(at_path, "w") as file_out:
        for line in file_in:
            if "_COMMIT = `" in line:
                line = line.replace("_COMMIT = ", "_COMMIT=")
            if fix_fi:
                file_out.write(line.replace("fi", "fi ; \\"))
                fix_fi = False
            else:
                file_out.write(line)
            if "_COMMIT=`" in line:
                fix_fi = True


def patch_open_pdks(at_path: str):
    """
    This functions applies various patches based on the current version of
    open_pdks in use.
    """
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=at_path, encoding="utf8"
    ).strip()

    def is_ancestor(commit: str):
        nonlocal head, at_path
        return (
            subprocess.call(
                ["git", "merge-base", "--is-ancestor", commit, head],
                stdout=open(os.devnull, "w"),
                stderr=open(os.devnull, "w"),
                cwd=at_path,
            )
            == 0
        )

    can_build = is_ancestor(
        "c74daac794c83327e54b91cbaf426f722574665c"
    )  # First one with --with-reference
    if not can_build:
        print(
            f"Commit {head} cannot be built using Volare: the minimum version of open_pdks buildable with Volare is 1.0.381."
        )
        exit(-1)

    gf180mcu_sources_ok = is_ancestor(
        "c1e2118846fd216b2c065a216950e75d2d67ccb8"
    )  # gf180mcu sources fix
    if not gf180mcu_sources_ok:
        print(
            "Patching gf180mcu Makefile.in…",
        )
        open_pdks_fix_makefile(os.path.join(at_path, "gf180mcu", "Makefile.in"))

    download_script_ok = is_ancestor(
        "ebffedd16788db327af050ac01c3fb1558ebffd1"
    )  # download script fix
    if download_script_ok:
        print("Replacing download.sh…")
        session = GitHubSession()
        r = session.get(
            "https://raw.githubusercontent.com/RTimothyEdwards/open_pdks/ebffedd16788db327af050ac01c3fb1558ebffd1/scripts/download.sh"
        )
        with open(os.path.join(at_path, "scripts", "download.sh"), "wb") as f:
            f.write(r.content)

    sky130_sources_ok = is_ancestor(
        "274040274a7dfb5fd2c69e0e9c643f80507df3fe"
    )  # sky130 sources fix
    if not sky130_sources_ok:
        print(
            "Patching sky130 Makefile.in…",
        )
        open_pdks_fix_makefile(os.path.join(at_path, "sky130", "Makefile.in"))
