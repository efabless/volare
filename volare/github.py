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
from dataclasses import dataclass
import os
import json
import requests
from datetime import datetime
from typing import Any, List, Mapping, Optional


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


@dataclass
class GitHubCredentials:
    username: Optional[str] = os.getenv("VOLARE_GH_USERNAME") or None
    token: Optional[str] = (
        os.getenv("VOLARE_GH_TOKEN") or os.getenv("GITHUB_TOKEN") or None
    )

    def get_session(self) -> requests.Session:
        session = requests.Session()
        if None not in [self.username, self.token]:
            session.auth = (self.username, self.token)
        return session


def get_open_pdks_commit_date(commit: str) -> Optional[datetime]:
    try:
        request = requests.get(f"{OPDKS_REPO_API}/commits/{commit}")
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
    req = requests.get(f"{VOLARE_REPO_API}/releases", params={"per_page": 100})
    req.raise_for_status()

    return req.json()


def get_release_links(release: str) -> Mapping[str, Any]:
    release_api_link = f"{VOLARE_REPO_API}/releases/tags/{release}"
    req = requests.get(release_api_link, json=True)
    req.raise_for_status()

    return req.json()
