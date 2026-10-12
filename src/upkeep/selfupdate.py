"""Is there a newer Upkeep? — one anonymous HEAD request at startup.

Deliberately NOT routed through :func:`github.fetch_latest_release`. Upkeep
users already spend the GitHub API budget (60 requests/hour per shared IP) on
every managed app; adding a self-check on top of that makes rate-limit
exhaustion worse for everyone. ``github.com/<repo>/releases/latest`` answers
``302`` with the tag in the ``Location`` header and an empty body, and that
endpoint is not rate-limited like the API is.

``http.client`` is used directly rather than ``urllib.request`` on purpose:
``urlopen`` brings an opener with cookie handling, proxy discovery and an
automatic redirect chain, and every one of those is state we do not want.

Every failure — offline, DNS, TLS, HTTP error — returns ``None`` by design. A
user with no network must not see an error about an optional feature.
"""

from __future__ import annotations

import http.client
import re

HOST = "github.com"
SELF_REPO = "padelle2603/upkeep"
LATEST_PATH = f"/{SELF_REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{SELF_REPO}/releases"

TIMEOUT = 5


def latest_tag(timeout=TIMEOUT):
    """Tag of the newest published release, or ``None`` if there is none.

    A repository with zero releases answers ``302 -> /releases`` with no tag in
    the path. That is not an error, it just means there is nothing to offer.
    """
    try:
        conn = http.client.HTTPSConnection(HOST, timeout=timeout)
        try:
            conn.request("HEAD", LATEST_PATH, headers={"User-Agent": "upkeep"})
            response = conn.getresponse()
            location = response.getheader("location")
        finally:
            conn.close()
    except (OSError, http.client.HTTPException):
        return None

    if not location:
        return None
    tag = location.rsplit("/", 1)[-1].strip()
    if not tag or tag in ("releases", "latest"):
        return None
    return tag.lstrip("vV")


def available_version(current, timeout=TIMEOUT):
    """The version to offer, or ``None``. One request."""
    from .github import newer_than

    remote = latest_tag(timeout)
    return remote if remote and newer_than(current, remote) else None