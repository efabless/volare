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
import sys
from datetime import datetime
from dataclasses import dataclass
from typing import Any, ClassVar, List, Literal, Mapping, Optional

import yaml
import httpx
import ssl
from .__version__ import __version__


@dataclass
class RepoInfo:
    owner: str
    name: str

    @property
    def id(self):
        return f"{self.owner}/{self.name}"

    @property
    def link(self):
        return f"https://github.com/{self.id}"

    @property
    def api(self):
        return f"https://api.github.com/repos/{self.id}"


volare_repo = RepoInfo(
    os.getenv("VOLARE_REPO_OWNER") or "efabless",
    os.getenv("VOLARE_REPO_NAME") or "volare",
)

opdks_repo = RepoInfo(
    os.getenv("OPDKS_REPO_OWNER") or "RTimothyEdwards",
    os.getenv("OPDKS_REPO_NAME") or "open_pdks",
)


class Token:
    override: ClassVar[Optional[str]] = None

    @classmethod
    def set_override_token(Self, override: str):
        Self.override = override


class GitHubSession(httpx.Client):
    class Token(object):
        override: ClassVar[Optional[str]] = None

        @classmethod
        def get_gh_token(Self) -> Optional[str]:
            token = None

            # 0. Lowest priority: ghcli's hosts.yml
            ghcli_file = os.path.join(os.path.expanduser("~/.config/gh/hosts.yml"))
            if os.path.exists(ghcli_file):
                hosts = yaml.safe_load(open(ghcli_file))
                gh_host = hosts.get("github.com")
                if gh_host is not None:
                    oauth_token = gh_host.get("oauth_token")
                    if oauth_token is not None:
                        token = str(oauth_token)

            # 1. Higher priority: environment GITHUB_TOKEN
            env_token = os.getenv("GITHUB_TOKEN")
            if env_token is not None and env_token.strip() != "":
                token = env_token

            # 2. Highest priority: the -t flag
            if override := Self.override:
                token = override

            return token

    def __init__(
        self,
        *,
        follow_redirects: bool = True,
        github_token: Optional[str] = None,
        ssl_context=None,
        **kwargs,
    ):
        if ssl_context is None:
            try:
                import truststore

                ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            except ImportError:
                pass

        try:
            super().__init__(
                follow_redirects=follow_redirects,
                verify=ssl_context,
                **kwargs,
            )
        except ValueError as e:
            if "Unknown scheme for proxy URL" in e.args[0] and "socks://" in e.args[0]:
                print(
                    f"Invalid SOCKS proxy: Volare only supports http://, https:// and socks5:// schemes: {e.args[0]}",
                    file=sys.stderr,
                )
                exit(-1)
            else:
                raise e from None
        raw_headers = {
            "User-Agent": type(self).get_user_agent(),
        }
        if github_token is not None:
            raw_headers["Authorization"] = f"Bearer {github_token}"
        self.headers = httpx.Headers(raw_headers)
        if github_token is None:
            github_token = GitHubSession.Token.get_gh_token()
        self.github_token = github_token

    def api(
        self,
        repo: RepoInfo,
        endpoint: str,
        method: Literal["get"],
        *args,
        **kwargs,
    ) -> Any:
        url = repo.api + endpoint
        req = self.request(method, url, *args, **kwargs)
        req.raise_for_status()
        return req.json()

    @classmethod
    def get_user_agent(Self) -> str:
        return f"volare/{__version__}"


def get_open_pdks_commit_date(
    commit: str, session: Optional[GitHubSession] = None
) -> Optional[datetime]:
    if session is None:
        session = GitHubSession()

    try:
        response = session.api(opdks_repo, f"/commits/{commit}", "get")
    except httpx.HTTPError:
        return None

    date = response["commit"]["author"]["date"]
    commit_date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
    return commit_date


def get_releases(session: Optional[GitHubSession] = None) -> List[Mapping[str, Any]]:
    if session is None:
        session = GitHubSession()

    return session.api(volare_repo, "/releases", "get", params={"per_page": 100})


def get_release_links(
    release: str, session: Optional[GitHubSession] = None
) -> Mapping[str, Any]:
    if session is None:
        session = GitHubSession()

    return session.api(volare_repo, f"/releases/tags/{release}", "get")
