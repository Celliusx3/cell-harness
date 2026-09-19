"""A shared Instagram URL to the one key everything else uses: the shortcode."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

_SHORTCODE = re.compile(
    r"^/(?:(?!share/)[A-Za-z0-9._]+/)?(?:reel|reels|p|tv)/(?P<code>[A-Za-z0-9_-]+)/?$",
)

_SHARE_WRAPPER = re.compile(r"^/share/(?:reel/|p/)?[A-Za-z0-9_-]+/?$")

_HOSTS = frozenset({"instagram.com", "www.instagram.com", "m.instagram.com"})


@dataclass(frozen=True)
class ReelRef:
    """One reel, addressed both ways."""

    url: str
    shortcode: str


class NotAReelUrl(ValueError):
    """The input is not a URL naming a single Instagram post."""


def parse(url: str) -> ReelRef:
    """`url` to a `ReelRef`, or raise `NotAReelUrl` saying why."""
    text = url.strip()
    if not text:
        raise NotAReelUrl("no URL was given")

    if "/" not in text and "." not in text and _is_shortcode(text):
        return ReelRef(url=text, shortcode=text)

    split = urlsplit(text if "//" in text else f"https://{text}")
    if split.hostname is None or split.hostname.lower() not in _HOSTS:
        raise NotAReelUrl(f"not an instagram.com URL: {url!r}")

    path = split.path if split.path.startswith("/") else f"/{split.path}"

    if _SHARE_WRAPPER.match(path):
        raise NotAReelUrl(
            f"{url!r} is an Instagram share-redirect link, which does not contain the post's "
            "shortcode. Open it and copy the link from the post itself, or send the "
            "instagram.com/reel/<code>/ form."
        )

    if match := _SHORTCODE.match(path):
        return ReelRef(url=url, shortcode=match["code"])

    raise NotAReelUrl(
        f"{url!r} is an Instagram URL but does not name a single post — expected "
        "instagram.com/reel/<code>/ or instagram.com/p/<code>/"
    )


def _is_shortcode(text: str) -> bool:
    """8-24 base64url characters."""
    return 8 <= len(text) <= 24 and re.fullmatch(r"[A-Za-z0-9_-]+", text) is not None
