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
import json
import yaml
import requests
from datetime import datetime
from dataclasses import dataclass
from typing import Any, List, Mapping, Optional

from .__version__ import __version__


VOLARE_REPO_OWNER = os.getenv("VOLARE_REPO_OWNER") or "efabless"
VOLARE_REPO_NAME = os.getenv("VOLARE_REPO_NAME") or "volare"
VOLARE_REPO_ID = f"{VOLARE_REPO_OWNER}/{VOLARE_REPO_NAME}"
VOLARE_REPO_HTTPS = f"https://github.com/{VOLARE_REPO_ID}"
VOLARE_REPO_API = f"https://api.github.com/repos/{VOLARE_REPO_ID}"


OPDKS_REPO_OWNER = os.getenv("OPDKS_REPO_OWNER") or "RTimothyEdwards"
OPDKS_REPO_NAME = os.getenv("OPDKS_REPO_NAME") or "open_pdks"
OPDKS_REPO_ID = f"{OPDKS_REPO_OWNER}/{OPDKS_REPO_NAME}"
OPDKS_REPO_HTTPS = f"https://github.com/{OPDKS_REPO_ID}"
OPDKS_REPO_API = f"https://api.github.com/repos/{OPDKS_REPO_ID}"


def _get_gh_token() -> Optional[str]:
    token = None

    # 0. Lowest priority: ghcli's hosts.yml
    ghcli_file = os.path.join(os.path.expanduser("~/.config/gh/hosts.yml"))
    if os.path.exists(ghcli_file):
        hosts = yaml.safe_load(open(ghcli_file))
        token = str(hosts["github.com"]["oauth_token"])

    # 1. Higher priority: environment GITHUB_TOKEN
    env_token = os.getenv("GITHUB_TOKEN")
    if env_token is not None and env_token.strip() != "":
        token = env_token

    # 2. Highest priority: the -t flag (set using a callback to the CLI)

    return token


@dataclass
class GitHubCredentials:
    token: Optional[str] = _get_gh_token()

    def get_session(self) -> requests.Session:
        session = requests.Session()
        if self.token is not None:
            session.headers = {
                "Authorization": f"token {self.token}",
                "User-Agent": f"volare/{__version__}",
            }
        return session


credentials = GitHubCredentials()


def get_open_pdks_commit_date(commit: str) -> Optional[datetime]:
    try:
        request = credentials.get_session().get(f"{OPDKS_REPO_API}/commits/{commit}")
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


def get_releases() -> List[Mapping[str, Any]]:
    req = credentials.get_session().get(
        f"{VOLARE_REPO_API}/releases", params={"per_page": 100}
    )
    req.raise_for_status()

    return req.json()


def get_release_links(release: str) -> Mapping[str, Any]:
    release_api_link = f"{VOLARE_REPO_API}/releases/tags/{release}"
    req = credentials.get_session().get(release_api_link, json=True)
    req.raise_for_status()

    return req.json()
