#
#  git.py
#  etl
#

"""
Helpers for working with Git in an ETL flow.
"""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, cast

import sh


CACHE_DIR = Path("~/.owid/git")


class RepoAlreadyExists(Exception):
    pass


@dataclass
class GithubRepo:
    org: str
    repo: str

    @property
    def github_url(self) -> str:
        return f"https://github.com/{self.org}/{self.repo}"

    @property
    def cache_dir(self) -> Path:
        return Path(f"~/.owid/git/{self.org}/{self.repo}").expanduser()

    def ensure_cloned(self, shallow: bool = True) -> None:
        """
        Ensuret that a copy of this repo has been cloned and is up to date.
        """
        dest_dir = self.cache_dir
        if not dest_dir.is_dir():
            dest_dir.parent.mkdir(parents=True, exist_ok=True)
            if shallow:
                sh.git(
                    "clone", "--depth=1", self.github_url, dest_dir.as_posix(), _fg=True
                )
            else:
                sh.git("clone", self.github_url, dest_dir.as_posix(), _fg=True)
        else:
            self.update_and_reset()

    def update_and_reset(self) -> None:
        """
        Fetch new changes from origin and do a hard reset of the repo from
        origin/<current-branch>. The hard reset is to avoid the update breaking if
        there have been force pushes from master.
        """
        if not self.cache_dir.is_dir():
            raise Exception("cannot update repo until repo is cloned")

        self._git("fetch")
        self._git("reset", "--hard", f"origin/{self.branch_name}")

    @property
    def branch_name(self) -> str:
        "Return the current branch name of the checked out repo."
        # in newer versions of git we can do "git branch --show-current"
        # but these aren't available on Ubuntu 18.04 on live
        return self._git("symbolic-ref", "--short", "HEAD")

    @property
    def latest_sha(self) -> str:
        output = self._git("log", "-n", "1", '--format="%H"')
        try:
            (sha,) = re.findall("[0-9a-f]{40}", output)
        except ValueError:
            raise GitError(f"could not get latest sha from repo: {self.cache_dir}")

        return cast(str, sha)

    def _git(self, *args: str, **kwargs: Any) -> str:
        "Execute a git command in the context of this repo."
        return cast(
            str,
            sh.git("--no-pager", *args, _cwd=self.cache_dir.as_posix(), **kwargs)
            .stdout.decode("utf8")
            .strip(),
        )

    def is_up_to_date(self) -> bool:
        "Returns true if remote has no new changes, false otherwise."
        # XXX over-sensitive, triggers if other remote branches have changes
        if not self.cache_dir.is_dir():
            return False

        available_updates = self._git(
            "fetch",
            "--dry-run",
            # special TTY settings required otherwise git-fetch will operate silently
            _tty_in=True,
            _unify_ttys=True,
        )

        return not available_updates


class GitError(Exception):
    pass
