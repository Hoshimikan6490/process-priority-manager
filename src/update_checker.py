"""Check GitHub Releases for a newer version of the application."""

import json
import re
import urllib.request
from importlib import metadata

REPO = "Hoshimikan6490/process-priority-manager"
LATEST_API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
CHECK_INTERVAL_MS = 24 * 60 * 60 * 1000  # 24 hours


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


def check_for_update(timeout=10):
    """Query GitHub Releases.

    Returns:
        (tag, url) when a newer release exists, otherwise None.
        Network/parse errors are swallowed and reported as None.
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
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
        tag = str(data.get("tag_name", ""))
        url = str(data.get("html_url", f"https://github.com/{REPO}/releases"))
    except (OSError, ValueError, AttributeError):
        return None
    if _is_newer(tag, current):
        return tag, url
    return None
