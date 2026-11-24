"""Check GitHub Releases for a newer version of the application."""

import hashlib
import json
import os
import re
import ssl
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from importlib import metadata
from pathlib import Path
from typing import NamedTuple

REPO = "Hoshimikan6490/process-priority-manager"
LATEST_API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000  # 24 hours
DOWNLOAD_URL_PREFIX = f"https://github.com/{REPO}/releases/download/"


class UpdateCheckError(Exception):
    """The release information could not be fetched or parsed."""


class UpdateInfo(NamedTuple):
    tag: str
    page_url: str
    msi_url: str | None  # None when the release has no installer asset
    sha256: str | None


def _urlopen(request, timeout):
    """urlopen using the Windows certificate store, falling back to certifi's CA bundle.

    The system store can lack an intermediate certificate (CERTIFICATE_VERIFY_FAILED:
    unable to get issuer certificate); certifi's bundle covers GitHub's chain.
    """
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.URLError as e:
        if not isinstance(e.reason, ssl.SSLCertVerificationError):
            raise
        try:
            import certifi
        except ImportError:
            raise e from None
        context = ssl.create_default_context(cafile=certifi.where())
        return urllib.request.urlopen(request, timeout=timeout, context=context)


def get_current_version():
    """Return the installed app version, or None when running from source."""
    try:
        return metadata.version("process-priority-manager")
    except metadata.PackageNotFoundError:
        return None


def _parse_version(text):
    """Turn 'v1.2.3' into (1, 2, 3); None when no numeric version is found."""
    match = re.search(r"\d+(?:\.\d+)*", str(text))
    if not match:
        return None
    return tuple(int(part) for part in match.group(0).split("."))


def _is_newer(latest, current):
    latest_t, current_t = _parse_version(latest), _parse_version(current)
    if latest_t is None or current_t is None:
        return False
    width = max(len(latest_t), len(current_t))

    def pad(t):
        return t + (0,) * (width - len(t))

    return pad(latest_t) > pad(current_t)


def _find_msi_asset(data):
    """Return (url, sha256) of the release's .msi asset, or (None, None)."""
    for asset in data.get("assets") or []:
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", ""))
        if name.lower().endswith(".msi") and url.startswith(DOWNLOAD_URL_PREFIX):
            digest = str(asset.get("digest") or "")
            sha = digest.split(":", 1)[1].lower() if digest.startswith("sha256:") else None
            return url, sha
    return None, None


def check_for_update(timeout=10):
    """Query GitHub Releases.

    Returns:
        UpdateInfo when a newer release exists, otherwise None.

    Raises:
        UpdateCheckError when GitHub could not be reached or answered badly.
    """
    current = get_current_version()
    if current is None:
        return None
    request = urllib.request.Request(
        LATEST_API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "process-priority-manager-update-check",
        },
    )
    try:
        with _urlopen(request, timeout) as response:
            data = json.load(response)
        tag = str(data.get("tag_name", ""))
        page_url = str(data.get("html_url", f"https://github.com/{REPO}/releases"))
        msi_url, sha256 = _find_msi_asset(data)
    except (OSError, ValueError, AttributeError) as e:
        raise UpdateCheckError(str(e)) from e
    if _is_newer(tag, current):
        return UpdateInfo(tag, page_url, msi_url, sha256)
    return None


def download_installer(info, timeout=60):
    """Download the release MSI to a temp folder and return its path.

    Raises:
        OSError / ValueError when the download fails or the checksum mismatches.
    """
    if not info.msi_url or not info.msi_url.startswith(DOWNLOAD_URL_PREFIX):
        raise ValueError("no installer asset available")
    dest = Path(tempfile.mkdtemp(prefix="ppm-update-")) / info.msi_url.rsplit("/", 1)[-1]
    request = urllib.request.Request(
        info.msi_url, headers={"User-Agent": "process-priority-manager-update-check"}
    )
    digest = hashlib.sha256()
    with _urlopen(request, timeout) as response, open(dest, "wb") as f:
        while chunk := response.read(1024 * 256):
            digest.update(chunk)
            f.write(chunk)
    if info.sha256 and digest.hexdigest().lower() != info.sha256:
        dest.unlink(missing_ok=True)
        raise ValueError("checksum mismatch")
    return dest


def launch_installer(msi_path):
    """Start the Windows Installer UI for the downloaded MSI.

    The app exits right after this call, and a plain child msiexec dies with it
    (the installer never shows). Handing the MSI to the running Explorer shell makes
    Explorer the parent instead. The explorer.exe launched here is only a client that
    forwards the request and exits, so wait for it before the caller quits.
    """
    explorer = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "explorer.exe"
    proc = subprocess.Popen([str(explorer), str(msi_path)])
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass
    time.sleep(1.5)  # let the shell spawn msiexec before the caller exits
