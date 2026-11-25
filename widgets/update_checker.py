"""One-shot, non-blocking GitHub release check (stdlib only, no retries)."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from packaging.version import InvalidVersion, Version


GITHUB_OWNER = "nekooee"
GITHUB_REPO = "PersianCalendarAndNetSpeed"
GITHUB_RELEASES_URL = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
GITHUB_RELEASES_PAGE = (
    f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
# Keep the request short so a dead network never stalls the UI thread.
REQUEST_TIMEOUT_SEC = 3.0
USER_AGENT = f"{GITHUB_REPO}-UpdateCheck/1.0"


class UpdateStatus(Enum):
    UPDATE_AVAILABLE = auto()
    UP_TO_DATE = auto()
    UNAVAILABLE = auto()  # offline, timeout, bad payload — silent on startup


@dataclass(frozen=True, slots=True)
class UpdateCheckResult:
    status: UpdateStatus
    local_version: str = ""
    remote_version: str = ""
    release_url: str = GITHUB_RELEASES_PAGE
    release_name: str = ""


def normalize_version(raw: str) -> str:
    """Strips a leading 'v' / whitespace for comparison."""
    return (raw or "").strip().lstrip("vV")


def is_remote_newer(remote: str, local: str) -> bool:
    """True when remote semantic version is strictly greater than local."""
    try:
        return Version(normalize_version(remote)) > Version(normalize_version(local))
    except InvalidVersion:
        return False


def check_latest_release(local_version: str) -> UpdateCheckResult:
    """Hits GitHub once. Any failure returns UNAVAILABLE (caller must not retry)."""
    local = normalize_version(local_version) or "0"
    request = Request(
        GITHUB_RELEASES_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SEC) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (URLError, HTTPError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return UpdateCheckResult(status=UpdateStatus.UNAVAILABLE, local_version=local)

    tag = str(payload.get("tag_name") or "").strip()
    remote = normalize_version(tag)
    if not remote:
        return UpdateCheckResult(status=UpdateStatus.UNAVAILABLE, local_version=local)

    html_url = str(payload.get("html_url") or "").strip() or GITHUB_RELEASES_PAGE
    name = str(payload.get("name") or tag).strip()

    if is_remote_newer(remote, local):
        return UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            local_version=local,
            remote_version=remote,
            release_url=html_url,
            release_name=name,
        )
    return UpdateCheckResult(
        status=UpdateStatus.UP_TO_DATE,
        local_version=local,
        remote_version=remote,
        release_url=html_url,
        release_name=name,
    )


def check_latest_release_async(
    local_version: str,
    on_finished: Callable[[UpdateCheckResult], None],
) -> threading.Thread:
    """Runs the check on a daemon thread; invokes on_finished from that thread."""

    def _worker():
        try:
            result = check_latest_release(local_version)
        except Exception:
            result = UpdateCheckResult(
                status=UpdateStatus.UNAVAILABLE,
                local_version=normalize_version(local_version),
            )
        try:
            on_finished(result)
        except Exception:
            pass

    thread = threading.Thread(
        target=_worker,
        name="github-update-check",
        daemon=True,
    )
    thread.start()
    return thread
