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
import json
import pathlib
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Union

import requests
from rich.console import Console

# Datetime Helpers
ISO8601_FMT = "%Y-%m-%dT%H:%M:%SZ"


def date_to_iso8601(date: datetime) -> str:
    return date.strftime(ISO8601_FMT)


def date_from_iso8601(string: str) -> datetime:
    return datetime.strptime(string, ISO8601_FMT)


# ---

VOLARE_REPO_OWNER = os.getenv("VOLARE_REPO_OWNER") or "efabless"
VOLARE_REPO_NAME = os.getenv("VOLARE_REPO_NAME") or "volare"
VOLARE_REPO_ID = f"{VOLARE_REPO_OWNER}/{VOLARE_REPO_NAME}"
VOLARE_REPO_HTTPS = f"https://github.com/{VOLARE_REPO_ID}"
VOLARE_REPO_API = f"https://api.github.com/repos/{VOLARE_REPO_ID}"
VOLARE_DEFAULT_HOME = os.path.join(os.path.expanduser("~"), ".volare")


OPDKS_REPO_OWNER = os.getenv("OPDKS_REPO_OWNER") or "RTimothyEdwards"
OPDKS_REPO_NAME = os.getenv("OPDKS_REPO_NAME") or "open_pdks"
OPDKS_REPO_ID = f"{OPDKS_REPO_OWNER}/{OPDKS_REPO_NAME}"
OPDKS_REPO_HTTPS = f"https://github.com/{OPDKS_REPO_ID}"
OPDKS_REPO_API = f"https://api.github.com/repos/{OPDKS_REPO_ID}"

# --
VOLARE_RESOLVED_HOME = os.getenv("PDK_ROOT") or VOLARE_DEFAULT_HOME


def mkdirp(path):
    return pathlib.Path(path).mkdir(parents=True, exist_ok=True)


class RepoMetadata(object):
    def __init__(self, repo, default_commit, default_branch="main"):
        self.repo = repo
        self.default_commit = default_commit
        self.default_branch = default_branch


@dataclass
class Version(object):
    name: str
    pdk: str
    commit_date: Optional[datetime] = None
    upload_date: Optional[datetime] = None
    prerelease: bool = False
    path: Optional[str] = None

    def __lt__(self, rhs: "Version"):
        return (self.commit_date or datetime.min) < (rhs.commit_date or datetime.min)

    def is_current(self, pdk_root: str) -> bool:
        return self.name == get_current_version(pdk_root, self.pdk)

    def __str__(self) -> str:
        return self.name

    @classmethod
    def _from_github(Self) -> Dict[str, List["Version"]]:
        response_str = requests.get(
            f"{VOLARE_REPO_API}/releases", params={"per_page": 100}
        ).content.decode("utf8")

        releases = json.loads(response_str)

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


def check_version(
    version: Optional[str],
    tool_metadata_file_path: Optional[str],
    console: Optional[Console] = None,
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

    def pr(*args):
        if console is not None:
            console.log(*args)
        else:
            print(*args)

    import yaml

    if tool_metadata_file_path is None:
        tool_metadata_file_path = os.path.join(".", "tool_metadata.yml")
        if not os.path.isfile(tool_metadata_file_path):
            tool_metadata_file_path = os.path.join(
                ".", "dependencies", "tool_metadata.yml"
            )
            if not os.path.isfile(tool_metadata_file_path):
                pr(
                    "Any of ./tool_metadata.yml or ./dependencies/tool_metadata.yml not found. You'll need to specify the file path or the commits explicitly."
                )
                exit(os.EX_USAGE)

    tool_metadata = yaml.safe_load(open(tool_metadata_file_path).read())

    open_pdks_list = [tool for tool in tool_metadata if tool["name"] == "open_pdks"]

    if len(open_pdks_list) < 1:
        pr("No entry for open_pdks found in tool_metadata.yml")
        exit(os.EX_USAGE)

    version = open_pdks_list[0]["commit"]

    pr(f"Found version {version} in {tool_metadata_file_path}.")

    return version


def get_volare_home(pdk_root: Optional[str] = None) -> str:
    return pdk_root or VOLARE_RESOLVED_HOME


def get_volare_dir(pdk_root: str, pdk: str) -> str:
    return os.path.join(pdk_root, "volare", pdk)


def get_versions_dir(pdk_root: str, pdk: str) -> str:
    return os.path.join(get_volare_dir(pdk_root, pdk), "versions")


def get_version_dir(pdk_root: str, pdk: str, version: Union[str, Version]) -> str:
    return os.path.join(get_versions_dir(pdk_root, pdk), str(version))


def get_link_of(version: str, pdk: str) -> str:
    return f"{VOLARE_REPO_HTTPS}/releases/download/{pdk}-{version}/default.tar.xz"


def get_logs_dir() -> str:
    if os.getenv("VOLARE_LOGS") is not None:
        return os.environ["VOLARE_LOGS"]
    else:
        return os.path.join(VOLARE_RESOLVED_HOME, "volare", "logs")


def get_date_of(opdks_commit: str) -> Optional[datetime]:
    try:
        request = requests.get(f"{OPDKS_REPO_API}/commits/{opdks_commit}")
        request.raise_for_status()
    except requests.exceptions.ConnectionError:
        return None
    except requests.exceptions.HTTPError:
        return None

    response_str = request.content.decode("utf8")
    response = json.loads(response_str)
    date = response["commit"]["author"]["date"]
    commit_date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
    return commit_date


def get_installed_list(pdk_root: str, pdk: str) -> List[Version]:
    versions_dir = get_versions_dir(pdk_root, pdk)
    mkdirp(versions_dir)
    return [
        Version(
            name=version,
            pdk=pdk,
            path=os.path.join(versions_dir, version),
        )
        for version in os.listdir(versions_dir)
    ]


def get_current_version(pdk_root: str, pdk: str) -> str:
    current_file = os.path.join(get_volare_dir(pdk_root, pdk), "current")
    current_file_dir = os.path.dirname(current_file)
    mkdirp(current_file_dir)
    version = ""
    try:
        version = open(current_file).read().strip()
    except FileNotFoundError:
        pass

    return version
