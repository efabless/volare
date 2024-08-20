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
import re
import shutil
import pathlib
from datetime import datetime
from dataclasses import dataclass
from typing import Iterable, Optional, List, Dict, Tuple

from . import github
from .families import Family

# -- Assorted Helper Functions
ISO8601_FMT = "%Y-%m-%dT%H:%M:%SZ"


def date_to_iso8601(date: datetime) -> str:
    return date.strftime(ISO8601_FMT)


def date_from_iso8601(string: str) -> datetime:
    return datetime.strptime(string, ISO8601_FMT)


def mkdirp(path):
    return pathlib.Path(path).mkdir(parents=True, exist_ok=True)


# -- API Variables

# -- PDK Root Management
VOLARE_DEFAULT_HOME = os.path.join(os.path.expanduser("~"), ".volare")
VOLARE_RESOLVED_HOME = os.getenv("PDK_ROOT") or VOLARE_DEFAULT_HOME


def _get_current_version(pdk_root: str, pdk: str) -> Optional[str]:
    current_file = os.path.join(get_volare_dir(pdk_root, pdk), "current")
    current_file_dir = os.path.dirname(current_file)
    mkdirp(current_file_dir)
    version = None
    try:
        version = open(current_file).read().strip()
    except FileNotFoundError:
        pass

    return version


def get_volare_home(pdk_root: Optional[str] = None) -> str:
    return pdk_root or VOLARE_RESOLVED_HOME


def get_volare_dir(pdk_root: str, pdk: str) -> str:
    return os.path.join(pdk_root, "volare", pdk)


def get_versions_dir(pdk_root: str, pdk: str) -> str:
    return os.path.join(get_volare_dir(pdk_root, pdk), "versions")


@dataclass
class Version(object):
    name: str
    pdk: str
    commit_date: Optional[datetime] = None
    upload_date: Optional[datetime] = None
    prerelease: bool = False

    def __lt__(self, rhs: "Version"):
        return (self.commit_date or datetime.min) < (rhs.commit_date or datetime.min)

    def __str__(self) -> str:
        return self.name

    def is_installed(self, pdk_root: str) -> bool:
        version_dir = self.get_dir(pdk_root)
        return os.path.isdir(version_dir)

    def is_current(self, pdk_root: str) -> bool:
        return self.name == _get_current_version(pdk_root, self.pdk)

    def get_dir(self, pdk_root: str) -> str:
        return os.path.join(get_versions_dir(pdk_root, self.pdk), self.name)

    def unset_current(self, pdk_root: str):
        if not self.is_installed(pdk_root):
            return
        if not self.is_current(pdk_root):
            return

        for variant in Family.by_name[self.pdk].variants:
            try:
                os.unlink(os.path.join(pdk_root, variant))
            except FileNotFoundError:
                pass

        current_file = os.path.join(get_volare_dir(pdk_root, self.pdk), "current")
        os.unlink(current_file)

    def uninstall(self, pdk_root: str):
        if not self.is_installed(pdk_root):
            raise ValueError(
                f"Version {self.name} of the {self.pdk} PDK is not installed."
            )

        self.unset_current(pdk_root)

        version_dir = self.get_dir(pdk_root)

        shutil.rmtree(version_dir)

    @classmethod
    def get_current(Self, pdk_root: str, pdk: str) -> Optional["Version"]:
        current_version = _get_current_version(pdk_root, pdk)
        if current_version is None:
            return None

        return Version(current_version, pdk)

    @classmethod
    def get_all_installed(Self, pdk_root: str, pdk: str) -> List["Version"]:
        versions_dir = get_versions_dir(pdk_root, pdk)
        mkdirp(versions_dir)
        return [
            Version(
                name=version,
                pdk=pdk,
            )
            for version in os.listdir(versions_dir)
            if os.path.isdir(os.path.join(versions_dir, version))
        ]

    @classmethod
    def _from_github(
        Self,
        session: Optional[github.GitHubSession] = None,
    ) -> Dict[str, List["Version"]]:
        releases = github.get_releases(session)

        rvs_by_pdk: Dict[str, List["Version"]] = {}

        commit_rx = re.compile(r"released on ([\d\-\:TZ]+)")

        for release in releases:
            if release["draft"]:
                continue
            family, hash = release["tag_name"].split("-")

            upload_date = date_from_iso8601(release["published_at"])
            commit_date = None

            commit_date_match = commit_rx.search(release["body"])
            if commit_date_match is not None:
                commit_date = date_from_iso8601(commit_date_match[1])

            remote_version = Self(
                name=hash,
                pdk=family,
                commit_date=commit_date,
                upload_date=upload_date,
                prerelease=release["prerelease"],
            )

            if rvs_by_pdk.get(family) is None:
                rvs_by_pdk[family] = rvs_by_pdk.get(family) or []

            rvs_by_pdk[family].append(remote_version)

        for family in rvs_by_pdk.keys():
            rvs_by_pdk[family].sort(reverse=True)

        return rvs_by_pdk

    def get_release_links(
        self,
        scl_filter: Iterable[str],
        include_common: bool,
        session: Optional[github.GitHubSession] = None,
    ) -> List[Tuple[str, str]]:
        release = github.get_release_links(f"{self.pdk}-{self.name}", session)

        assets = release["assets"]
        zst_files = []
        for asset in assets:
            if asset["name"].endswith(".tar.zst"):
                asset_scl = asset["name"][:-8]
                if (
                    asset_scl == "common" and include_common
                ) or asset_scl in scl_filter:
                    zst_files.append((asset["name"], asset["browser_download_url"]))

        if len(zst_files) == 0:
            raise ValueError(
                f"No files found for standard cell libraries: {scl_filter}."
            )

        return zst_files


def resolve_version(
    version: Optional[str],
    tool_metadata_file_path: Optional[str],
) -> str:
    """
    Takes an optional version and tool_metadata_file_path.

    If version is set, it is returned.

    If not, tool_metadata_file_path is checked if it exists.

    If not specified, ./tool_metadata.yml and ./dependencies/tool_metadata.yml
    are both checked if they exist.

    If none are specified, execution is halted.

    Otherwise, the resulting metadata file is parsed for an open_pdks version,
    which is then returned.
    """
    if version is not None:
        return version

    import yaml

    if tool_metadata_file_path is None:
        tool_metadata_file_path = os.path.join(".", "tool_metadata.yml")
        if not os.path.isfile(tool_metadata_file_path):
            tool_metadata_file_path = os.path.join(
                ".", "dependencies", "tool_metadata.yml"
            )
            if not os.path.isfile(tool_metadata_file_path):
                raise FileNotFoundError(
                    "Any of ./tool_metadata.yml or ./dependencies/tool_metadata.yml not found. You'll need to specify the file path or the commits explicitly."
                )

    tool_metadata = yaml.safe_load(open(tool_metadata_file_path).read())

    open_pdks_list = [tool for tool in tool_metadata if tool["name"] == "open_pdks"]

    if len(open_pdks_list) < 1:
        raise ValueError("No entry for open_pdks found in tool_metadata.yml")

    version = open_pdks_list[0]["commit"]

    return version
