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
import re
import shutil
import subprocess

from rich.progress import Progress

from ..common import mkdirp


class Repository(object):
    @classmethod
    def from_path(Self, path):
        name = os.path.basename(path)
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], stderr=subprocess.PIPE
        ).strip()

        remote_branch_info = open(
            os.path.join(path, ".git", "refs", "remotes", "origin", "HEAD")
        ).read()
        remote_branch = os.path.basename(remote_branch_info)

        return Self(name, url, path, remote_branch)

    def __init__(self, name, url, path, default_branch="main"):
        path = os.path.abspath(path)

        self.name = name
        self.url = url
        self.path = path
        self.default_branch = default_branch

    def clone_if_not_exist(self, callback=None):
        if os.path.exists(self.path):
            self.pristine()
            self.pull(callback)
        else:
            self.clone(callback)

    def clone(self, callback=None):
        try:
            shutil.rmtree(self.path)
        except FileNotFoundError:
            pass

        callback(0, f"Cloning {self.name} to {self.path}…")

        process = subprocess.Popen(
            ["git", "clone", "--progress", self.url, self.path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stderr is not None

        ro_rx = re.compile(r"Receiving objects:\s*(\d+)%")

        # Python Moment
        buffer = ""
        while True:
            bytes_read = process.stderr.read(1)
            if len(bytes_read) == 0:
                break
            char_read = bytes_read.decode("utf8")
            if char_read in ["\n", "\r"]:
                match = ro_rx.search(buffer)
                if match is not None:
                    if callback is not None:
                        callback(int(match[1]))
                buffer = ""
            else:
                buffer += char_read

        process.wait()

        subprocess.check_output(
            ["git", "submodule", "init"], stderr=subprocess.PIPE, cwd=self.path
        )

    def pristine(self):
        subprocess.check_output(
            ["git", "clean", "-fdX"], cwd=self.path, stderr=subprocess.PIPE
        )

        subprocess.check_output(
            ["git", "reset", "--hard", "HEAD"], cwd=self.path, stderr=subprocess.PIPE
        )

    def pull(self, callback=None):
        subprocess.check_output(
            ["git", "checkout", "-f", self.default_branch],
            cwd=self.path,
            stderr=subprocess.PIPE,
        )
        process = subprocess.Popen(
            ["git", "pull", "--no-recurse-submodules", "--progress"],
            cwd=self.path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert process.stderr is not None
        callback(0, f"Updating {self.name} at {self.path}…")

        ro_rx = re.compile(r"Receiving objects:\s*(\d+)%")

        # Python Moment #2
        buffer = ""
        while True:
            bytes_read = process.stderr.read(1)
            if len(bytes_read) == 0:
                break
            char_read = bytes_read.decode("utf8")
            if char_read in ["\n", "\r"]:
                match = ro_rx.search(buffer)
                if match is not None:
                    if callback is not None:
                        callback(int(match[1]))
                buffer = ""
            else:
                buffer += char_read

        process.wait()
        if callback is not None:
            callback(100)
        subprocess.check_output(
            ["git", "submodule", "init"], stderr=subprocess.PIPE, cwd=self.path
        )

    def checkout_commit(self, commit: str):
        subprocess.check_output(
            ["git", "checkout", "-f", self.default_branch],
            cwd=self.path,
            stderr=subprocess.PIPE,
        )
        try:
            subprocess.check_output(
                ["git", "branch", "-f", "-D", "current"],
                cwd=self.path,
                stderr=subprocess.PIPE,
            )
        except Exception:
            pass
        subprocess.check_output(
            ["git", "checkout", "-f", "-b", "current", commit],
            cwd=self.path,
            stderr=subprocess.PIPE,
        )

    def init_submodule_if_not_exist(self, submodule: str, callback=None):
        submodule_git_path = os.path.join(self.path, submodule, ".git")
        if os.path.exists(submodule_git_path):
            subprocess.check_output(
                ["git", "submodule", "update", "--remote", submodule],
                cwd=self.path,
                stderr=subprocess.PIPE,
            )
            if callback is not None:
                callback(100)
        else:
            self.init_submodule(submodule, callback)

    def init_submodule(self, submodule: str, callback=None):
        process = subprocess.Popen(
            ["git", "submodule", "update", "--progress", submodule, submodule],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.path,
        )

        ro_rx = re.compile(r"Receiving objects:\s*(\d+)%")

        assert process.stderr is not None, "Process doesn't have a stderr channel"

        # Python Moment #3
        buffer = ""
        while True:
            bytes_read = process.stderr.read(1)
            if len(bytes_read) == 0:
                break
            char_read = bytes_read.decode("utf8")
            if char_read in ["\n", "\r"]:
                match = ro_rx.search(buffer)
                if match is not None:
                    if callback is not None:
                        callback(int(match[1]))
                buffer = ""
            else:
                buffer += char_read

        process.wait()


class GitMultiClone(object):
    progress: Progress

    def __init__(self, folder, progress):
        super().__init__()
        self.folder = os.path.abspath(folder)
        mkdirp(self.folder)
        self.progress = progress

    def clone(
        self, repo_url: str, commit: str, default_branch: str = "main"
    ) -> Repository:
        current_task = self.progress.add_task("", total=100)
        name = os.path.basename(repo_url)
        path = os.path.join(self.folder, name)
        r = Repository(name, repo_url, path, default_branch=default_branch)
        r.clone_if_not_exist(
            lambda x, y=None: self.progress.update(
                current_task, completed=x, description=y
            )
        )
        r.checkout_commit(commit)
        return r

    def clone_submodule(self, repo: Repository, submodule: str):
        current_task = self.progress.add_task(
            f"Updating submodule {submodule}…", total=100
        )
        repo.init_submodule_if_not_exist(
            submodule, lambda x: self.progress.update(current_task, completed=x)
        )
